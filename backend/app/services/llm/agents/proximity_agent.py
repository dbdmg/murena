import json
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import numpy as np

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings, AGENT_MODELS
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import ProximityAgentResult, PromptRecord, CategoryResponse
from app.core.constants import PROXIMITY_AGENT_COLUMNS
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse, is_oss_model
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage, handle_agent_error
from app.utils.json_parser import safe_extract_json
from app.utils.scoring import calculate_continuous_score


class ProximityAgentOutput(BaseModel):
    """Structured output schema for the Proximity Agent."""
    found: bool = Field(default=False, description="True if POI-related needs were identified in the user query")
    requirements: List[Dict[str, Any]] = Field(default_factory=list, description="List of structured requirements with operator and value.")


class ProximityAgent(BaseAgent):
    name = "proximity-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("proximity_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        self.system_prompt = get_system_prompt("proximity_agent")
        self.user_template = get_user_template("proximity_agent")

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )
        # Detect if we should use structured output (avoid for OSS models)
        if hasattr(self.llm, "with_structured_output") and not is_oss_model(resolved_model):
            # Usiamo json_mode per garantire che il modello restituisca correttamente i nuovi campi (percentili_minimi)
            self.structured_llm = self.llm.with_structured_output(ProximityAgentOutput, method="json_mode")
            self.chain = self.prompt_template | self.structured_llm
        else:
            from langchain_core.output_parsers import StrOutputParser
            self.chain = self.prompt_template | self.llm | StrOutputParser()

    @log_llm_usage
    def run(
        self,
        *,
        query: str = None,
        mode: str = "filtering",
        **kwargs
    ) -> Union[ProximityAgentResult, pd.DataFrame]:
        """
        Executes the agent in two modes:
        - filtering: Identifies categories and minimum thresholds (LLM).
        - ranking: Calculates a deterministic score based on positional weights.
        """
        if mode == "filtering":
            return self._run_filtering(
                query=query,
                statistics=kwargs.get("statistics")
            )
        elif mode == "ranking":
            try:
                return self._run_ranking(
                    df=kwargs.get("df"),
                    requirements=kwargs.get("requirements"),
                    global_stats=kwargs.get("global_stats")
                )
            except Exception as e:
                # Fallback sicuro per ranking: restituisci DF originale con score 0
                df = kwargs.get("df")
                if df is not None:
                    if "proximity_score" not in df.columns:
                        df["proximity_score"] = 0.0
                    return df
                return pd.DataFrame()
        else:
            raise ValueError(f"Mode '{mode}' not supported by ProximityAgent.")

    def _run_filtering(
        self,
        query: str,
        statistics: dict = None,
    ) -> ProximityAgentResult:
        if not statistics and not query:
            return ProximityAgentResult(raw_text="{}", prompt=None)

        stats_str = json.dumps(statistics, indent=2, ensure_ascii=False) if statistics else "N/D"
        
        # Format specific columns list with descriptions from PROXIMITY_CATEGORIES
        from app.core.constants import PROXIMITY_CATEGORIES
        columns_str = "\n".join([f"- `{col}`: {PROXIMITY_CATEGORIES.get(col, '')}" for col in PROXIMITY_AGENT_COLUMNS])

        prompt_inputs = {
            "query": query,
            "statistics": stats_str,
            "reference_columns": columns_str
        }

        # Format prompts with variables
        rendered_system_prompt = self.render_template(self.system_prompt, **prompt_inputs).strip()
        user_text = self.render_template(self.user_template, **prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{rendered_system_prompt}\n\n[USER]\n{user_text}"

        try:
            model_inputs = {
                "system_content": rendered_system_prompt,
                "user_content": user_text
            }
            structured_response = invoke_with_langfuse(self.chain, model_inputs)
            
            # If the output is a string (fallback mode), we need to extract JSON manually
            if isinstance(structured_response, str) or hasattr(structured_response, 'content'):
                text_to_parse = structured_response.content if hasattr(structured_response, 'content') else structured_response
                structured_response = safe_extract_json(text_to_parse, schema=ProximityAgentOutput)
            
            if not structured_response:
                raise ValueError("Could not parse proximity requirements from LLM response")
                
            has_pois = structured_response.found

            return ProximityAgentResult(
                raw_text=json.dumps(structured_response.model_dump(), ensure_ascii=False),
                has_pois=has_pois,
                requirements=structured_response.requisiti,
                prompt=PromptRecord(
                    system=rendered_system_prompt,
                    user=user_text,
                    full_text=full_text,
                ),
            )
        except Exception as e:
            return ProximityAgentResult(
                raw_text=json.dumps({"error": str(e), "found": False, "requirements": []}),
                prompt=None,
            )

    def _run_ranking(self, *, df: pd.DataFrame, requirements: List[Dict[str, Any]] = None, global_stats: Dict[str, Any] = None) -> pd.DataFrame:
        """Ranking mode: 0-100 score calculation based on requirements (proximity categories)."""
        if df is None or df.empty or not requirements:
            if df is not None:
                if "proximity_score" not in df.columns:
                    df["proximity_score"] = 0
            return df

        df_ranked = df.copy()
        
        # Assign equal weight to all identified requirements
        valid_reqs = [r for r in requirements if isinstance(r, dict) and r.get("target_column") and r.get("target_column") in df_ranked.columns]
        
        if not valid_reqs:
            df_ranked["proximity_score"] = 0.0
            return df_ranked[["id", "proximity_score"]]

        # Calcolo pesi armonici basati sulla posizione nel ranking
        # (1.0, 0.5, 0.33, ...) normalizzati per somma = 1.0
        n_reqs = len(valid_reqs)
        harmonic_weights = [1.0 / (i + 1) for i in range(n_reqs)]
        total_harmonic_sum = sum(harmonic_weights)
        norm_weights = [w / total_harmonic_sum for w in harmonic_weights]
            
        # 3. Calcola lo score pesato per ogni riga e salva i partial scores
        # Refactoring to vectorized operations for partial scores
        total_score_series = pd.Series(0.0, index=df_ranked.index)
        
        cols_to_return = ["id", "proximity_score"]
        weight_cols = []
        partial_score_cols = []
        used_cats = [r.get("target_column") for r in valid_reqs]
        for i, cat in enumerate(used_cats):
            weight = norm_weights[i]
            
            # Get values and handle NaNs
            vals = pd.to_numeric(df_ranked[cat], errors="coerce")
            na_mask = vals.isna()
            vals = vals.fillna(0)
            
            # Global vs Local Normalization
            col_stats = global_stats.get(cat) if global_stats else None
            if col_stats and isinstance(col_stats, dict) and "min" in col_stats and "max" in col_stats:
                min_val = float(col_stats["min"])
                max_val = float(col_stats["max"])
            else:
                min_val = vals.min()
                max_val = vals.max()
            
            if pd.isna(min_val) or min_val == max_val:
                # If all NaNs or single value
                if pd.isna(min_val):
                     norm_vals = np.zeros(len(vals))
                else:
                     norm_vals = np.ones(len(vals))
            else:
                 norm_vals = (vals - min_val) / (max_val - min_val)
                 # Handle NaN result from operation
                 norm_vals = norm_vals.fillna(0).to_numpy()
            
            # CLIP AND APPLY THRESHOLD
            # If there's a requirement for this category, enforce it in the score too
            req = next((r for r in requirements if r.get("target_column") == cat), None)
            if req and isinstance(req, dict):
                op = req.get("operator", ">=")
                target_val = req.get("value")
                if target_val is not None:
                    try:
                        exclusive = req.get("exclusive", False)
                        # Use centralized utility for continuous variables
                        req_score = calculate_continuous_score(vals, target_val, op, exclusive)
                        norm_vals = req_score.to_numpy() / 100.0
                    except:
                        pass

            # Clip to be safe (0-1)
            norm_vals = norm_vals.clip(0, 1)
            
            # Where it was NaN, score is 0
            norm_vals[na_mask] = 0.0
            
            # Partial score (0-100) for this category
            partial_score = norm_vals * 100.0
            col_partial_name = f"proximity_partial_score_{cat}"
            # Handle duplicate names if multiple requirements exist for the same column
            if col_partial_name in df_ranked.columns:
                idx = 1
                while f"{col_partial_name}_{idx}" in df_ranked.columns:
                    idx += 1
                col_partial_name = f"{col_partial_name}_{idx}"
            
            df_ranked[col_partial_name] = partial_score.round(1)
            partial_score_cols.append(col_partial_name)
            
            # Add to total weighted score
            total_score_series += partial_score * weight
            
            # Store weight column
            col_weight_name = f"proximity_weight_{cat}"
            if col_weight_name in df_ranked.columns:
                idx = 1
                while f"{col_weight_name}_{idx}" in df_ranked.columns:
                    idx += 1
                col_weight_name = f"{col_weight_name}_{idx}"

            df_ranked[col_weight_name] = round(weight, 3)
            weight_cols.append(col_weight_name)

        df_ranked["proximity_score"] = total_score_series.round(1)
        
        all_requested_cols = cols_to_return + list(used_cats) + weight_cols + partial_score_cols
        unique_cols = []
        for c in all_requested_cols:
            if c not in unique_cols and c in df_ranked.columns:
                unique_cols.append(c)
                
        return df_ranked[unique_cols]

