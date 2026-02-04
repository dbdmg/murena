from typing import Any, List, Optional
import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import RankingAgentResult, RankingWeights, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json

AGENT_MODELS = settings.agent_models

class RankingAgent(BaseAgent):
    """
    Agente responsabile di definire i pesi (coefficienti) per il sistema di ranking finale
    basandosi sull'analisi della query utente.
    """
    name = "ranking-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("ranking_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        self.system_prompt = get_system_prompt("ranking_agent")
        self.user_template = get_user_template("ranking_agent")

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", self.user_template),
            ]
        )
        # Use structured output for deterministic weights
        self.structured_llm = self.llm.with_structured_output(RankingWeights, method="function_calling")
        self.chain = self.prompt_template | self.structured_llm

    @log_llm_usage
    @handle_agent_error(
        fallback_value=RankingAgentResult(
            raw_text="{}", weights=RankingWeights(), prompt=None
        )
    )
    def run(self, *, query: str) -> RankingAgentResult:
        if not query:
            return RankingAgentResult(raw_text="{}", weights=RankingWeights(), prompt=None)

        system_content = self.system_prompt
        prompt_inputs = {"system_content": system_content, "query": query}
        user_text = self.render_template(self.user_template, query=query).strip()
        full_text = f"[SYSTEM]\n{system_content}\n\n[USER]\n{user_text}"

        try:
            weights: RankingWeights = invoke_with_langfuse(self.chain, prompt_inputs)
            
            # Normalizzare se necessario (anche se l'LLM dovrebbe farlo bene)
            total = weights.location + weights.normative + weights.ape + weights.typology + weights.poi
            if total > 0:
                weights.location /= total
                weights.normative /= total
                weights.ape /= total
                weights.typology /= total
                weights.poi /= total

            return RankingAgentResult(
                raw_text=json.dumps(weights.model_dump(), ensure_ascii=False),
                weights=weights,
                prompt=PromptRecord(
                    system=system_content,
                    user=user_text,
                    full_text=full_text,
                ),
            )
        except Exception as e:
            return RankingAgentResult(
                raw_text=json.dumps({"error": str(e)}),
                weights=RankingWeights(),
                prompt=None,
            )
