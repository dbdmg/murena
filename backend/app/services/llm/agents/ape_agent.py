from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import ApeAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage
from app.utils.json_parser import safe_extract_json


class ApeAgentOutput(BaseModel):
    """Schema di output strutturato per l'APE Agent."""
    answer: str = Field(..., description="Spiegazione della strategia energetica")
    suggested_filters: List[str] = Field(default_factory=list, description="Filtri APE suggeriti (es. 'ape_score_total >= 4')")


class ApeAgent(BaseAgent):
    name = "ape-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("ape_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("ape_agent")
        self.user_template = get_user_template("ape_agent")

        # Create ChatPromptTemplate with system/user separation
        # Note: We construct the chain dynamically in run() because system prompt changes with stats
        from langchain_core.prompts import ChatPromptTemplate

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", self.user_template),
            ]
        )
        # Use with_structured_output for guaranteed structured responses
        self.structured_llm = self.llm.with_structured_output(ApeAgentOutput)
        self.chain = self.prompt_template | self.structured_llm

    @log_llm_usage
    def run(
        self,
        query: str,
        columns: list[str] = None,
        statistics: dict = None,
        score_legend: str = "",
    ) -> ApeAgentResult:
        if not statistics and not columns:
            # Fallback legacy behavior or graceful exit
            return ApeAgentResult(
                raw_text="Dati APE non disponibili.",
                prompt=None,
            )

        # Format statistics string
        stats_str = "Nessuna statistica disponibile."
        if statistics:
            import json

            stats_str = json.dumps(statistics, indent=2, ensure_ascii=False)
        elif columns:
            stats_str = "Colonne disponibili: " + ", ".join(columns)

        # Prepare system prompt content
        # We manually inject variables into the system string before passing to LLM
        # This is because get_system_prompt returns a string that expects formatting
        system_content = self.render_template(
            self.system_prompt,
            statistics=stats_str,
            score_legend=score_legend or "Nessuna legenda disponibile.",
        )

        prompt_inputs = {"system_content": system_content, "query": query}

        # User text for record keeping
        user_text = self.render_template(self.user_template, query=query).strip()
        full_text = f"[SYSTEM]\n{system_content}\n\n[USER]\n{user_text}"

        try:
            # Use invoke_with_langfuse to get structured output
            structured_response: ApeAgentOutput = invoke_with_langfuse(self.chain, prompt_inputs)

            import json
            raw_json = json.dumps(structured_response.model_dump(), ensure_ascii=False)

            return ApeAgentResult(
                raw_text=raw_json,
                prompt=PromptRecord(
                    system=system_content,
                    user=user_text,
                    full_text=full_text,
                ),
            )

        except Exception as e:
            print(f"Errore ApeAgent: {e}")
            return ApeAgentResult(
                raw_text=json.dumps({"error": str(e), "answer": "Si è verificato un errore nell'analisi energetica.", "suggested_filters": []}),
                prompt=None,
            )
