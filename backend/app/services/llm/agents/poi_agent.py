import json
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import numpy as np

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PoiAgentResult, PromptRecord, CategoryResponse
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage, handle_agent_error
from app.utils.json_parser import safe_extract_json


class PoiAgentOutput(BaseModel):
    """Schema di output strutturato per il Poi Agent."""
    found: bool = Field(default=False, description="True se sono state identificate necessità relative ai POI nella query dell'utente")
    requisiti: List[Dict[str, Any]] = Field(default_factory=list, description="Lista di requisiti strutturati con operatore e valore.")


class PoiAgent(BaseAgent):
    name = "poi-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("poi_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        self.system_prompt = get_system_prompt("poi_agent")
        self.user_template = get_user_template("poi_agent")

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", self.user_template),
            ]
        )
        # Usiamo json_mode per garantire che il modello restituisca correttamente i nuovi campi (percentili_minimi)
        self.structured_llm = self.llm.with_structured_output(PoiAgentOutput, method="json_mode")
        self.chain = self.prompt_template | self.structured_llm

    @log_llm_usage
    def run(
        self,
        *,
        query: str = None,
        mode: str = "filtering",
        **kwargs
    ) -> Union[PoiAgentResult, pd.DataFrame]:
        """
        Esegue l'agente in due modalità:
        - filtering: Identifica categorie e soglie minime (LLM).
        - ranking: Calcola un punteggio deterministico basato sui pesi posizionali.
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
                    # Assicurati che non modifichi l'originale se possibile, ma qui stiamo recuperando da errore
                    if "poi_score" not in df.columns:
                        df["poi_score"] = 0.0
                    return df
                return pd.DataFrame()
        else:
            raise ValueError(f"Modalità '{mode}' non supportata dal PoiAgent.")

    def _run_filtering(
        self,
        query: str,
        statistics: dict = None,
    ) -> PoiAgentResult:
        if not statistics and not query:
            return PoiAgentResult(raw_text="{}", prompt=None)

        stats_str = json.dumps(statistics, indent=2, ensure_ascii=False) if statistics else "N/D"
        
        system_content = self.render_template(
            self.system_prompt
        )

        prompt_inputs = {"system_content": system_content, "query": query, "statistics": stats_str}
        user_text = self.render_template(self.user_template, query=query, statistics=stats_str).strip()
        full_text = f"[SYSTEM]\n{system_content}\n\n[USER]\n{user_text}"

        try:
            structured_response: PoiAgentOutput = invoke_with_langfuse(self.chain, prompt_inputs)
            has_pois = structured_response.found

            return PoiAgentResult(
                raw_text=json.dumps(structured_response.model_dump(), ensure_ascii=False),
                has_pois=has_pois,
                requisiti=structured_response.requisiti,
                prompt=PromptRecord(
                    system=system_content,
                    user=user_text,
                    full_text=full_text,
                ),
            )
        except Exception as e:
            return PoiAgentResult(
                raw_text=json.dumps({"error": str(e), "found": False, "requisiti": []}),
                prompt=None,
            )

    def _run_ranking(self, *, df: pd.DataFrame, requirements: List[Dict[str, Any]] = None, global_stats: Dict[str, Any] = None) -> pd.DataFrame:
        """Modalità ranking: calcolo score 0-100 basato sui requisiti (POI categories)."""
        if df is None or df.empty or not requirements:
            if df is not None:
                if "poi_score" not in df.columns:
                    df["poi_score"] = 0
            return df

        df_ranked = df.copy()
        
        # In questa modalità, estraiamo le categorie dai requisiti.
        # Poiché l'utente ha chiesto di non avere più un ranking (lista ordinata), 
        # assegniamo un peso uguale a tutti i requisiti identificati.
        valid_reqs = [r for r in requirements if isinstance(r, dict) and r.get("colonna_target") and r.get("colonna_target") in df_ranked.columns]
        
        if not valid_reqs:
            df_ranked["poi_score"] = 0.0
            return df_ranked[["id", "poi_score"]]

        # Calcolo pesi armonici basati sulla posizione nel ranking
        # (1.0, 0.5, 0.33, ...) normalizzati per somma = 1.0
        n_reqs = len(valid_reqs)
        harmonic_weights = [1.0 / (i + 1) for i in range(n_reqs)]
        total_harmonic_sum = sum(harmonic_weights)
        norm_weights = [w / total_harmonic_sum for w in harmonic_weights]
            
        # 3. Calcola lo score pesato per ogni riga e salva i partial scores
        # Refactoring to vectorized operations for partial scores
        total_score_series = pd.Series(0.0, index=df_ranked.index)
        
        cols_to_return = ["id", "poi_score"]
        weight_cols = []
        partial_score_cols = []
        used_cats = [r.get("colonna_target") for r in valid_reqs]
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
            req = next((r for r in requirements if r.get("colonna_target") == cat), None)
            if req and isinstance(req, dict):
                op = req.get("operatore", ">=")
                target_val = req.get("valore")
                if target_val is not None:
                    try:
                        T = float(target_val)
                        if op in [">=", ">"]:
                            # Linear growth with threshold T and cap at 2T
                            # Score 0 below T, 100 at 2T
                            req_score = ((vals - T) / T * 100).clip(0, 100)
                        elif op in ["<=", "<"]:
                            # Linear decay with threshold T and cap at T/2
                            # Score 0 above T, 100 at T/2
                            req_score = ((T - vals) / (T / 2) * 100).clip(0, 100)
                        
                        norm_vals = req_score.to_numpy() / 100.0
                    except:
                        pass

            # Clip to be safe (0-1)
            norm_vals = norm_vals.clip(0, 1)
            
            # Where it was NaN, score is 0
            norm_vals[na_mask] = 0.0
            
            # Partial score (0-100) for this category
            partial_score = norm_vals * 100.0
            col_partial_name = f"poi_partial_score_{cat}"
            df_ranked[col_partial_name] = partial_score.round(1)
            partial_score_cols.append(col_partial_name)
            
            # Add to total weighted score
            total_score_series += partial_score * weight
            
            # Store weight column
            col_weight_name = f"poi_weight_{cat}"
            df_ranked[col_weight_name] = round(weight, 3)
            weight_cols.append(col_weight_name)

        df_ranked["poi_score"] = total_score_series.round(1)
        
        all_requested_cols = cols_to_return + list(used_cats) + weight_cols + partial_score_cols
        unique_cols = []
        for c in all_requested_cols:
            if c not in unique_cols and c in df_ranked.columns:
                unique_cols.append(c)
                
        return df_ranked[unique_cols]

