import json
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
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
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

        # Broker prompt (system/user separated)
        broker_system = get_system_prompt("broker_agent")
        broker_user = get_user_template("broker_agent")
        self.broker_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )

        # Store templates for PromptRecord
        self._system_with_format = system_with_format
        self._broker_system = broker_system
        self._broker_user = broker_user

        # Se il modello supporta structured output nativo (es. Gemini/OpenAI), usiamolo
        if hasattr(self.llm, "with_structured_output"):
            self.chain = self.prompt | self.llm.with_structured_output(EvaluationList, method="function_calling")
        else:
            self.chain = self.prompt | self.llm | self.parser

        # Broker chain (pure text)
        self.broker_chain = self.broker_prompt | self.llm

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
        # If query is empty, use original_query for the prompt
        if not query:
            query = original_query

        # Add original query context to use_case if available and different
        if original_query and query != use_case:
            query_context = f"""
RICORDA: La richiesta originale dell'utente era:
"{original_query}"

Assicurati che la tua valutazione sia allineata con i requisiti specifici sopra menzionati.
"""
            use_case = query_context + "\n\n" + use_case

        # Format user prompt with variables
        user_text = self.render_template(
            self.user_template,
            query=query,
            use_case=use_case,
            estates_data=estates_data,
        ).strip()
        full_text = f"[SYSTEM]\n{self._system_with_format}\n\n[USER]\n{user_text}"

        # Conteggio immobili in input per verifica output (retry logic)
        try:
            input_estates = json.loads(estates_data)
            expected_count = len(input_estates) if isinstance(input_estates, list) else 0
        except Exception:
            expected_count = 0

        max_retries = 3
        result = None
        raw_text = ""
        
        for attempt in range(max_retries):
            try:
                result = invoke_with_langfuse(
                    self.chain,
                    {
                        "system_content": self._system_with_format,
                        "query": query,
                        "use_case": use_case,
                        "estates_data": estates_data,
                    },
                )

                # Gestione differenziata in base al tipo di output (oggetto Pydantic o altro)
                if isinstance(result, EvaluationList):
                    results = result.evaluations
                    raw_text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
                    
                    # Se abbiamo ricevuto almeno tanti record quanti ne abbiamo inviati, usciamo dal loop
                    if len(results) >= expected_count:
                        break
                    else:
                        logger.warning(f"L'EvaluationAgent ha restituito {len(results)} record su {expected_count} attesi (tentativo {attempt + 1}/{max_retries}). Rieseguo...")
                else:
                    # Fallback se la catena restituisce qualcos'altro
                    raw_text = str(result)
                    if expected_count > 0:
                         logger.warning(f"L'EvaluationAgent non ha restituito una EvaluationList (tentativo {attempt + 1}/{max_retries}). Rieseguo...")
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

        return EvaluationAgentResponse(
            prompt=prompt_record, raw_text=raw_text
        )

    @log_llm_usage
    def run_synthesis(self, *, query: str, candidates_data: str) -> str:
        """Genera una sintesi comparativa (Broker Review)."""
        try:
            res = invoke_with_langfuse(
                self.broker_chain,
                {
                    "system_content": self._broker_system,
                    "user_content": self.render_template(
                        self._broker_user,
                        query=query,
                        candidates_data=candidates_data,
                    ),
                },
            )
            # Handle standard langchain response objects (content vs str)
            return res.content if hasattr(res, "content") else str(res)
        except Exception as e:
            return f"Impossibile generare sintesi: {e}"
