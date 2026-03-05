import json
import os
from datetime import datetime
from typing import List
from app.utils.logger import logger

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.core.constants import SCORE_LEGEND
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import (
    EvaluationAgentResponse,
    EvaluationResult,
    EvaluationList,
    PromptRecord,
)
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse, is_oss_model
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage


class EvaluationAgent(BaseAgent):
    name = "evaluation-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("evaluation_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("evaluation_agent")
        self.user_template = get_user_template("evaluation_agent")

        self.parser = PydanticOutputParser(pydantic_object=EvaluationList)

        # Inject format_instructions and score_legend into system prompt
        system_with_format = self.system_prompt.replace(
            "{format_instructions}", self.parser.get_format_instructions()
        ).replace("{score_legend}", SCORE_LEGEND)

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", self.user_template),
            ]
        )


        # Store templates for PromptRecord
        self._system_with_format = system_with_format

        # Detect if we should use structured output (avoid for OSS models via custom API base)
        # Often these models claim to support it but fail at runtime or return text instead of tool calls.
        if hasattr(self.llm, "with_structured_output") and not is_oss_model(resolved_model):
            self.structured_chain = self.prompt | self.llm.with_structured_output(EvaluationList, method="function_calling")
        else:
            self.structured_chain = None

        # raw chain (fallback or default for OSS)
        from langchain_core.output_parsers import StrOutputParser
        self.raw_chain = self.prompt | self.llm | StrOutputParser()
        
        # Default chain for legacy calls (if any)
        self.chain = self.structured_chain or (self.prompt | self.llm | self.parser)


    @log_llm_usage
    def run(
        self,
        *,
        use_case: str,
        estates_data: str,
        query: str = "",  # Kept for backward compat
        original_query: str = "",  # NEW: original user query for context
        score_legend: str = "",
    ) -> EvaluationAgentResponse:
        # Se query è vuota, usa original_query per il prompt
        if not query:
            query = original_query

        # Conteggio immobili in input per verifica output (retry logic)
        try:
            input_estates = json.loads(estates_data or "[]")
            expected_count = len(input_estates) if isinstance(input_estates, list) else 0
        except Exception:
            input_estates = []
            expected_count = 0

        logger.info(f"EvaluationAgent in esecuzione su {expected_count} immobili.")

        # Format user prompt with variables
        user_text = self.render_template(
            self.user_template,
            query=query,
            use_case=use_case,
            estates_data=estates_data,
            expected_count=expected_count,
        ).strip()
        full_text = f"[SYSTEM]\n{self._system_with_format}\n\n[USER]\n{user_text}"

        max_retries = 3
        result = None
        raw_text = ""
        
        for attempt in range(max_retries):
            try:
                # Decide which chain to use (structured if available, otherwise raw)
                active_chain = self.structured_chain if (self.structured_chain and attempt == 0) else self.raw_chain
                
                result = invoke_with_langfuse(
                    active_chain,
                    {
                        "system_content": self._system_with_format,
                        "query": query,
                        "use_case": use_case,
                        "estates_data": estates_data,
                        "expected_count": expected_count,
                    },
                )

                # Gestione dell'output grezzo per il record finale
                if hasattr(result, "content"):
                    raw_text = result.content
                elif hasattr(result, "model_dump_json"):
                    raw_text = result.model_dump_json()
                else:
                    raw_text = str(result)

                eval_list = None
                if isinstance(result, EvaluationList):
                    eval_list = result
                elif isinstance(result, dict):
                    try:
                        eval_list = EvaluationList(**result)
                    except:
                        # Se è un dict con la chiave 'evaluations', prova a estrarla
                        if "evaluations" in result:
                            eval_list = EvaluationList(evaluations=result["evaluations"])
                
                if not eval_list:
                    # Se non abbiamo un EvaluationList/dict, proviamo ad estrarlo dal testo grezzo
                    # Questo è fondamentale per modelli OSS che non supportano bene function_calling
                    from app.utils.json_parser import safe_extract_json
                    text_to_parse = ""
                    if hasattr(result, "content"): # Se è un messaggio (BaseMessage)
                        text_to_parse = result.content
                    elif isinstance(result, str):
                        text_to_parse = result
                    
                    if text_to_parse:
                        eval_list = safe_extract_json(text_to_parse, schema=EvaluationList)
                
                if eval_list:
                    results = eval_list.evaluations
                    
                    # Verifica quantitativa: abbiamo ricevuto tutti i record attesi?
                    is_complete = len(results) >= expected_count
                    
                    # Verifica qualitativa: se abbiamo record, sono effettivamente compilati?
                    # Spesso gli LLM restituiscono JSON validi ma con stringhe vuote o liste vuote in caso di errore silente.
                    if is_complete and expected_count > 0:
                        # Controlliamo la qualità di ogni record (l'agente di solito lavora in batch da 1)
                        for eval_item in results:
                            # Se mancano testo di valutazione o i punti chiave, consideriamo il record incompleto
                            if not eval_item.evaluation_text or len(eval_item.pros) == 0 or len(eval_item.cons) == 0:
                                is_complete = False
                                logger.warning(f"L'EvaluationAgent ha restituito record con dati mancanti per ID {eval_item.id} (tentativo {attempt + 1}/{max_retries}).")
                                break
                    
                    if is_complete:
                        result = eval_list # Assicuriamo che 'result' sia l'oggetto validato per il prosieguo
                        break
                    elif len(results) < expected_count:
                        logger.warning(f"L'EvaluationAgent ha restituito solo {len(results)} record su {expected_count} attesi (tentativo {attempt + 1}/{max_retries}).")
                else:
                    if expected_count > 0:
                         logger.warning(f"L'EvaluationAgent non ha restituito una struttura valida (tentativo {attempt + 1}/{max_retries}).")
                    else:
                        break

            except Exception as e:
                logger.error(f"Errore nel parsing della valutazione (tentativo {attempt + 1}/{max_retries}): {e}")
                raw_text = json.dumps({"error": str(e), "evaluations": []})
                # Continua il loop per il retry

        prompt_record = PromptRecord(
            system=self._system_with_format.strip(),
            user=user_text,
            full_text=full_text,
        )

        # Monitor - JSON export is handled by the orchestrator if enabled


        return EvaluationAgentResponse(
            prompt=prompt_record, raw_text=raw_text
        )

