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
        from app.services.llm.agents.schema import RankingRanking
        self.structured_llm = self.llm.with_structured_output(RankingRanking, method="function_calling")
        self.chain = self.prompt_template | self.structured_llm

    @log_llm_usage
    @handle_agent_error(
        fallback_value=RankingAgentResult(
            raw_text="{}", weights=RankingWeights(), prompt=None
        )
    )
    def run(self, *, query: str = None, mode: str = "ranking", db_metadata: dict = None) -> RankingAgentResult:
        """
        Esegue l'agente per definire i pesi.
        Il RankingAgent opera esclusivamente in modalità 'ranking'.
        """
        if mode != "ranking":
            raise ValueError(f"RankingAgent non supporta la modalità '{mode}'.")
            
        if not query:
            return RankingAgentResult(raw_text="{}", weights=RankingWeights(), prompt=None)

        system_content = self.system_prompt
        
        # Prepare metadata string if available
        metadata_str = ""
        if db_metadata:
             metadata_str = json.dumps(db_metadata, ensure_ascii=False)

        prompt_inputs = {"system_content": system_content, "query": query, "db_metadata": metadata_str}
        user_text = self.render_template(self.user_template, query=query, db_metadata=metadata_str).strip()
        full_text = f"[SYSTEM]\n{system_content}\n\n[USER]\n{user_text}"

        try:
            ranking_data: RankingRanking = invoke_with_langfuse(self.chain, prompt_inputs)
            
            # Calculate weights based on ranking: 1, 1/2, 1/3, 1/4, 1/5
            # Similar to PoiAgent logic requested by user
            ordered_agents = ranking_data.ranking
            
            # Ensure all agents are present (fallback to defaults if LLM missed some)
            all_agents = ["location", "normative", "ape", "typology", "poi"]
            for agent in all_agents:
                if agent not in ordered_agents:
                    ordered_agents.append(agent)
            
            # Keep only first 5
            ordered_agents = ordered_agents[:5]
            
            raw_weights = {}
            for i, agent in enumerate(ordered_agents):
                raw_weights[agent] = 1.0 / (i + 1)
            
            # Normalize to sum = 1.0
            total_sum = sum(raw_weights.values())
            normalized_weights = {k: round(v / total_sum, 1) for k, v in raw_weights.items()}
            
            # Ensure sum is exactly 1.0 (rounding adjustments)
            current_sum = sum(normalized_weights.values())
            diff = round(1.0 - current_sum, 1)
            if diff != 0:
                # Adjust the top agent
                top_agent = ordered_agents[0]
                normalized_weights[top_agent] = round(normalized_weights[top_agent] + diff, 1)
            
            weights = RankingWeights(
                location=normalized_weights.get("location", 0.2),
                normative=normalized_weights.get("normative", 0.2),
                ape=normalized_weights.get("ape", 0.2),
                typology=normalized_weights.get("typology", 0.2),
                poi=normalized_weights.get("poi", 0.2)
            )

            return RankingAgentResult(
                raw_text=json.dumps({"ranking": ordered_agents, "weights": weights.model_dump()}, ensure_ascii=False),
                weights=weights,
                ranking=ranking_data,
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
