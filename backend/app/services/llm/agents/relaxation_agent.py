from typing import Any, List, Dict, Optional
import json

from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings, AGENT_MODELS
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, RelaxationAgentResult, RelaxationProposal
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage
from app.utils.json_parser import safe_extract_json
from app.utils.logger import logger

class RelaxationAgent(BaseAgent):
    """Agente responsabile del rilassamento dei criteri di ricerca quando i risultati sono insufficienti."""
    
    name = "relaxation-agent"

    def __init__(self, model_name: str = None):
        """Inizializza l'agente con il modello specificato o quello di default."""
        resolved_model = (
            model_name or AGENT_MODELS.get("relaxation_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(
            model_name=resolved_model, temperature=settings.AGENT_TEMPERATURE
        )

        # Caricamento system e user prompts
        self.system_prompt = get_system_prompt("relaxation_agent")
        self.user_template = get_user_template("relaxation_agent")

    def _invoke(
        self, system: str, user_template: str, variables: dict
    ) -> tuple[str, PromptRecord]:
        """Esegue l'invocazione del modello LLM."""
        user_text = self.render_template(user_template, **variables).strip()
        full_text = f"[SYSTEM]\n{system}\n\n[USER]\n{user_text}"

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )
        chain = prompt | self.llm
        response = invoke_with_langfuse(
            chain, {"system_content": system, "user_content": user_text}
        )
        raw_text = getattr(response, "content", str(response))

        prompt_record = PromptRecord(
            system=system.strip(),
            user=user_text,
            full_text=full_text,
        )
        return raw_text, prompt_record

    @log_llm_usage
    def run(
        self,
        *,
        where_conditions: str,
        statistics: str,
        min_threshold: int = 10,
        current_results_count: int = 0,
    ) -> RelaxationAgentResult:
        """
        Analizza le condizioni SQL e propone strategie di rilassamento.
        
        Args:
            where_conditions: La clausola WHERE attuale o i criteri estratti
            statistics: Statistiche sulla distribuzione dei dati per supportare il rilassamento
            min_threshold: Numero minimo di risultati desiderati
            current_results_count: Numero attuale di risultati trovati
            
        Returns:
            RelaxationAgentResult contenente le proposte di rilassamento strutturate
        """
        variables = {
            "where_conditions": where_conditions,
            "statistics": statistics,
            "min_threshold": min_threshold,
            "current_results_count": current_results_count,
        }

        raw_text, prompt_record = self._invoke(
            self.system_prompt, self.user_template, variables
        )

        # Estrazione JSON dei rilassamenti
        data = safe_extract_json(raw_text)
        proposals = []
        
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "proposals" in data:
                items = data["proposals"]
            else:
                # Caso singolo oggetto proposta
                items = [data]
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            try:
                # Validazione strutturata
                p = RelaxationProposal.model_validate(item)
                proposals.append(p)
            except Exception as e:
                logger.warning(f"Salto proposta di rilassamento non valida o incompleta: {e}")
                continue

        return RelaxationAgentResult(
            raw_text=raw_text,
            prompt=prompt_record,
            proposals=proposals
        )
