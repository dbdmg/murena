import pandas as pd
from typing import Union
import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.config import settings, AGENT_MODELS
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import RankingAgentResult, RankingWeights, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse, is_oss_model
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json
from app.services.llm.agents.schema import RankingRanking


from app.utils.logger import logger

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
        # Detect if we should use structured output (avoid for OSS models)
        if hasattr(self.llm, "with_structured_output") and not is_oss_model(resolved_model):
            self.structured_llm = self.llm.with_structured_output(RankingRanking, method="function_calling")
            self.chain = self.prompt_template | self.structured_llm
        else:
            from langchain_core.output_parsers import StrOutputParser
            self.chain = self.prompt_template | self.llm | StrOutputParser()

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
            ranking_data = invoke_with_langfuse(self.chain, prompt_inputs)
            
            # If the output is a string (fallback mode), we need to extract JSON manually
            if isinstance(ranking_data, str) or hasattr(ranking_data, 'content'):
                text_to_parse = ranking_data.content if hasattr(ranking_data, 'content') else ranking_data
                from app.services.llm.agents.schema import RankingRanking
                ranking_data = safe_extract_json(text_to_parse, schema=RankingRanking)
            
            if not ranking_data:
                raise ValueError("Could not parse ranking weights from LLM response")

            # Calculate weights based on ranking: 1/rank
            # This allows ex-aequo (same rank = same weight)
            ranked_agents_list = ranking_data.ranking
            
            # Ensure at least one agent is present for safety
            if not ranked_agents_list:
                 # Fallback: PropertyTechnical default
                 from app.services.llm.agents.schema import RankedAgent
                 ranked_agents_list = [RankedAgent(agent_name="property_technical", rank=1)]
            
            # Normalize agent names to support both old and new naming conventions
            name_mapping = {
                "normative": "regulatory",
                "ape": "energy",
                "property_technical": "building",
                "poi": "proximity"
            }
            for agent_obj in ranked_agents_list:
                if agent_obj.agent_name in name_mapping:
                    agent_obj.agent_name = name_mapping[agent_obj.agent_name]

            # Limit to available agents
            all_supported = ["location", "regulatory", "energy", "building", "proximity"]
            valid_agents = [a for a in ranked_agents_list if a.agent_name in all_supported]

            if not valid_agents:
                logger.warning("No valid agents found in LLM ranking response. Falling back to uniform weights.")
                weights = RankingWeights()  # Default 0.2 each
            else:
                # Calculate raw weights: 1.0 / rank (e.g. Rank 1 -> 1.0, Rank 2 -> 0.5)
                raw_weights = {}
                for agent_obj in valid_agents:
                    # Safety against rank 0 or negative
                    rank_val = max(1, agent_obj.rank)   
                    raw_weights[agent_obj.agent_name] = 1.0 / rank_val
                
                # Normalize to sum = 1.0 across SELECTED agents
                total_sum = sum(raw_weights.values())
                normalized_weights = {}
                
                if total_sum > 0:
                    normalized_weights = {k: round(v / total_sum, 2) for k, v in raw_weights.items()}
                
                # Ensure sum is exactly 1.0 (rounding adjustments)
                current_sum = sum(normalized_weights.values())
                diff = round(1.0 - current_sum, 2)
                if diff != 0 and valid_agents:
                    # Adjust the agent with the highest weight (to minimize relative error)
                    best_agent = max(normalized_weights, key=normalized_weights.get)
                    normalized_weights[best_agent] = round(normalized_weights[best_agent] + diff, 2)
                
                weights = RankingWeights(
                    location=normalized_weights.get("location", 0.0),
                    regulatory=normalized_weights.get("regulatory", 0.0),
                    energy=normalized_weights.get("energy", 0.0),
                    building=normalized_weights.get("building", 0.0),
                    proximity=normalized_weights.get("proximity", 0.0)
                )

            # Reconstruct simple list of names for backward compatibility if needed in UI/Logs
            ordered_names = [a.agent_name for a in sorted(valid_agents, key=lambda x: x.rank)]

            return RankingAgentResult(
                raw_text=json.dumps({
                    "ranking": [a.model_dump() for a in valid_agents], 
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
        df_ranked["ranking_weight_regulatory"] = weights.regulatory
        df_ranked["ranking_weight_energy"] = weights.energy
        df_ranked["ranking_weight_building"] = weights.building
        df_ranked["ranking_weight_proximity"] = weights.proximity

        # Calcolo score pesato finale
        # Componenti pesati secondo la posizione nel ranking (già riflesso nei pesi)
        df_ranked["final_ranking_score"] = (
            df_ranked["ranking_weight_location"] * df_ranked.get("location_score", 0.0) +
            df_ranked["ranking_weight_regulatory"] * df_ranked.get("regulatory_score", 0.0) +
            df_ranked["ranking_weight_energy"] * df_ranked.get("energy_score", 0.0) +
            df_ranked["ranking_weight_building"] * df_ranked.get("building_score", 0.0) +
            df_ranked["ranking_weight_proximity"] * df_ranked.get("proximity_score", 0.0)
        )
        
        # Create explicit formula column for each property
        def build_formula(row):
            components = []
            
            # Add each component if weight > 0
            if weights.location > 0 and "location_score" in df_ranked.columns:
                loc_score = row.get("location_score", 0.0)
                components.append(f"{weights.location}*location({loc_score})")
            
            if weights.regulatory > 0 and "regulatory_score" in df_ranked.columns:
                reg_score = row.get("regulatory_score", 0.0)
                components.append(f"{weights.regulatory}*regulatory({reg_score})")
            
            if weights.energy > 0 and "energy_score" in df_ranked.columns:
                eng_score = row.get("energy_score", 0.0)
                components.append(f"{weights.energy}*energy({eng_score})")
            
            if weights.building > 0 and "building_score" in df_ranked.columns:
                bld_score = row.get("building_score", 0.0)
                components.append(f"{weights.building}*building({bld_score})")
            
            if weights.proximity > 0 and "proximity_score" in df_ranked.columns:
                prox_score = row.get("proximity_score", 0.0)
                components.append(f"{weights.proximity}*proximity({prox_score})")
            
            if components:
                formula = " + ".join(components) + f" = {row['final_ranking_score']:.1f}"
            else:
                formula = f"{row['final_ranking_score']:.1f}"
            
            return formula
        
        df_ranked["ranking_formula"] = df_ranked.apply(build_formula, axis=1)
        
        # Return full dataframe to preserve all columns (is_match, is_evaluated, etc.)
        return df_ranked
