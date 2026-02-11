import pandas as pd
from typing import Union
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
    def run(self, *, query: str = None, mode: str = "filtering", **kwargs) -> Union[RankingAgentResult, pd.DataFrame]:
        """
        Esegue l'agente per definire i pesi o calcolare il ranking finale.
        """
        if mode == "filtering":
            return self._run_filtering(query=query)
        elif mode == "ranking":
            return self._run_ranking(**kwargs)
        else:
            raise ValueError(f"Modalità '{mode}' non supportata dal RankingAgent.")

    def _run_filtering(self, query: str) -> RankingAgentResult:
        if not query:
            return RankingAgentResult(raw_text="{}", weights=RankingWeights(), prompt=None)

        system_content = self.system_prompt
        
        prompt_inputs = {"system_content": system_content, "query": query}
        user_text = self.render_template(self.user_template, query=query).strip()
        full_text = f"[SYSTEM]\n{system_content}\n\n[USER]\n{user_text}"

        try:
            ranking_data: RankingRanking = invoke_with_langfuse(self.chain, prompt_inputs)
            
            # Calculate weights based on ranking: 1, 1/2, 1/3, 1/4, 1/5
            # Similar to PoiAgent logic requested by user
            ordered_agents = ranking_data.ranking
            
            # Use ONLY agents returned by LLM
            ordered_agents = ranking_data.ranking
            
            # Ensure at least one agent is present for safety
            if not ordered_agents:
                 ordered_agents = ["typology"] # Fallback
            
            # Limit to available agents
            all_supported = ["location", "normative", "ape", "typology", "poi"]
            ordered_agents = [a for a in ordered_agents if a in all_supported]

            # Calculate weights based on ranking: 1, 1/2, 1/3, 1/4...
            raw_weights = {}
            for i, agent in enumerate(ordered_agents):
                raw_weights[agent] = 1.0 / (i + 1)
            
            # Normalize to sum = 1.0 across SELECTED agents
            total_sum = sum(raw_weights.values())
            normalized_weights = {k: round(v / total_sum, 1) for k, v in raw_weights.items()}
            
            # Ensure sum is exactly 1.0 (rounding adjustments)
            current_sum = sum(normalized_weights.values())
            diff = round(1.0 - current_sum, 1)
            if diff != 0 and ordered_agents:
                # Adjust the top agent
                top_agent = ordered_agents[0]
                normalized_weights[top_agent] = round(normalized_weights[top_agent] + diff, 1)
            
            weights = RankingWeights(
                location=normalized_weights.get("location", 0.0),
                normative=normalized_weights.get("normative", 0.0),
                ape=normalized_weights.get("ape", 0.0),
                typology=normalized_weights.get("typology", 0.0),
                poi=normalized_weights.get("poi", 0.0)
            )

            return RankingAgentResult(
                raw_text=json.dumps({
                    "ranking": ordered_agents, 
                    "weights": weights.model_dump(),
                    "reasoning": ranking_data.reasoning
                }, ensure_ascii=False),
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

    def _run_ranking(self, *, df: pd.DataFrame, weights: RankingWeights) -> pd.DataFrame:
        """
        Calcola il final_ranking_score pesando i punteggi degli altri agenti.
        """
        if df is None or df.empty:
            return df
        
        df_ranked = df.copy()
        
        # Store ranking weights in DF for logging transparency
        df_ranked["ranking_weight_location"] = weights.location
        df_ranked["ranking_weight_normative"] = weights.normative
        df_ranked["ranking_weight_ape"] = weights.ape
        df_ranked["ranking_weight_typology"] = weights.typology
        df_ranked["ranking_weight_poi"] = weights.poi

        # Calcolo score pesato finale
        # Componenti pesati secondo la posizione nel ranking (già riflesso nei pesi)
        df_ranked["final_ranking_score"] = (
            df_ranked["ranking_weight_location"] * df_ranked.get("location_score", 0.0) +
            df_ranked["ranking_weight_normative"] * df_ranked.get("normative_score", 0.0) +
            df_ranked["ranking_weight_ape"] * df_ranked.get("ape_score", 0.0) +
            df_ranked["ranking_weight_typology"] * df_ranked.get("typology_score", 0.0) +
            df_ranked["ranking_weight_poi"] * df_ranked.get("poi_score", 0.0)
        )
        
        # Create explicit formula column for each property
        def build_formula(row):
            components = []
            
            # Add each component if weight > 0
            if weights.location > 0 and "location_score" in df_ranked.columns:
                loc_score = row.get("location_score", 0.0)
                components.append(f"{weights.location}*location({loc_score})")
            
            if weights.normative > 0 and "normative_score" in df_ranked.columns:
                norm_score = row.get("normative_score", 0.0)
                components.append(f"{weights.normative}*normative({norm_score})")
            
            if weights.ape > 0 and "ape_score" in df_ranked.columns:
                ape_score = row.get("ape_score", 0.0)
                components.append(f"{weights.ape}*ape({ape_score})")
            
            if weights.typology > 0 and "typology_score" in df_ranked.columns:
                typ_score = row.get("typology_score", 0.0)
                components.append(f"{weights.typology}*typology({typ_score})")
            
            if weights.poi > 0 and "poi_score" in df_ranked.columns:
                poi_score = row.get("poi_score", 0.0)
                components.append(f"{weights.poi}*poi({poi_score})")
            
            if components:
                formula = " + ".join(components) + f" = {row['final_ranking_score']:.1f}"
            else:
                formula = f"{row['final_ranking_score']:.1f}"
            
            return formula
        
        df_ranked["ranking_formula"] = df_ranked.apply(build_formula, axis=1)
        
        # Return only essential columns: id, final score, and formula
        return df_ranked[["id", "final_ranking_score", "ranking_formula"]]
