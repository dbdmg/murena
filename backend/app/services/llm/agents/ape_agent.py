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
from app.services.llm.agents.schema import ApeAgentResult, PromptRecord, ApeResponse
from app.core.constants import APE_AGENT_COLUMNS, APE_SCORE_LEGEND
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage
from app.utils.json_parser import safe_extract_json


class ApeAgentOutput(ApeResponse):
    """Schema di output strutturato per l'APE Agent (eredita da ApeResponse)."""
    pass


class ApeAgent(BaseAgent):
    name = "ape-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("ape_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        self.system_prompt = get_system_prompt("ape_agent")
        self.user_template = get_user_template("ape_agent")

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )
        self.structured_llm = self.llm.with_structured_output(ApeAgentOutput, method="json_mode")
        self.chain = self.prompt_template | self.structured_llm

    @log_llm_usage
    def run(
        self,
        *,
        query: str = None,
        mode: str = "filtering",
        **kwargs
    ) -> Union[ApeAgentResult, pd.DataFrame]:
        """
        Esegue l'agente in due modalità:
        - filtering: Suggerisce filtri SQL basati sulla query (LLM).
        - ranking: Calcola uno score 0-100 basato sulle colonne APE (Deterministico).
        """
        if mode == "filtering":
            return self._run_filtering(
                query=query,
                statistics=kwargs.get("statistics"),
                score_legend=kwargs.get("score_legend")
            )
        elif mode == "ranking":
            return self._run_ranking(
                df=kwargs.get("df"),
                requirements=kwargs.get("requirements"),
                global_stats=kwargs.get("global_stats")
            )
        else:
            raise ValueError(f"Modalità '{mode}' non supportata dall'ApeAgent.")

    def _run_filtering(
        self,
        query: str,
        statistics: dict = None,
        score_legend: str = "",
    ) -> ApeAgentResult:
        if not statistics and not query:
            return ApeAgentResult(raw_text="Dati APE non disponibili.", prompt=None)

        stats_str = json.dumps(statistics, indent=2, ensure_ascii=False) if statistics else "N/D"
        
        # Format specific columns list
        columns_str = "\n".join([f"- `{col}`" for col in APE_AGENT_COLUMNS])

        prompt_inputs = {
            "query": query,
            "statistics": stats_str,
            "score_legend": score_legend or APE_SCORE_LEGEND,
            "reference_columns": columns_str
        }

        # Format prompts with variables
        rendered_system_prompt = self.render_template(self.system_prompt, **prompt_inputs).strip()
        user_text = self.render_template(self.user_template, **prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{rendered_system_prompt}\n\n[USER]\n{user_text}"

        try:
            # We explicitly pass the system/user split as expected by Langchain call or prompt_template
            model_inputs = {
                "system_content": rendered_system_prompt,
                "user_content": user_text
            }
            structured_response: ApeAgentOutput = invoke_with_langfuse(self.chain, model_inputs)
            has_filters = structured_response.found

            return ApeAgentResult(
                raw_text=json.dumps(structured_response.model_dump(), ensure_ascii=False),
                has_filters=has_filters,
                prompt=PromptRecord(
                    system=rendered_system_prompt,
                    user=user_text,
                    full_text=full_text,
                ),
            )
        except Exception as e:
            return ApeAgentResult(
                raw_text=json.dumps({"error": str(e), "found": False, "requisiti": []}),
                prompt=None,
            )

    def _run_ranking(self, *, df: pd.DataFrame, requirements: List[Dict[str, Any]] = None, global_stats: Dict[str, Any] = None) -> pd.DataFrame:
        """Modalità ranking: calcolo score 0-100 basato su requisiti LLM o logica deterministica."""
        if df is None or df.empty:
            if df is not None:
                df["ape_score"] = 0
            return df

        df_ranked = df.copy()
        
        # 1. Se abbiamo requisiti dinamici dall'LLM (filtering), usiamoli per calcolare lo score
        if requirements:
            total_scores = pd.Series(0.0, index=df_ranked.index)
            valid_req_count = 0
            used_columns = set()
            transparency_cols = []

            for req in requirements:
                col = req.get("colonna_target")
                target_val = req.get("valore")
                op = str(req.get("operatore", "==")).upper()

                if not col or col not in df_ranked.columns or target_val is None:
                    continue

                valid_req_count += 1
                used_columns.add(col)
                
                # Special handling for energy class (categorical)
                if col == "classe_energetica_ape":
                    # Definitive ranking map: Class -> (Score, Rank)
                    # A4 is best (Rank 1), G is worst (Rank 10)
                    # Score decays linearly from 100 to 0
                    classes_order = ["A4", "A3", "A2", "A1", "B", "C", "D", "E", "F", "G"]
                    n_classes = len(classes_order)
                    ranking_map = {}
                    
                    for i, cls_name in enumerate(classes_order):
                        # Linear decay: 100 at index 0, 0 at index n-1
                        # Formula: 100 * (1 - i / (n-1))
                        score = round(100.0 * (1 - i / (n_classes - 1)), 1)
                        ranking_map[cls_name] = (score, i + 1)
                    
                    vals = df_ranked[col].astype(str).str.upper().str.strip()
                    
                    # Helper to extract score and rank safe
                    def get_class_details(c_val):
                        if c_val in ranking_map:
                            return ranking_map[c_val]
                        return (0.0, "N/A") # fallback

                    details = vals.apply(get_class_details)
                    
                    req_score = details.apply(lambda x: x[0])
                    rank_pos = details.apply(lambda x: x[1])
                    
                    # Save transparency metadata
                    pos_col = f"ape_rank_position_{col}"
                    
                    df_ranked[pos_col] = rank_pos
                    
                    # Store partial score for this categorical requirement
                    # req_score is already calculated above as details.apply(lambda x: x[0])
                    df_ranked[f"ape_partial_score_{col}"] = req_score
                    
                    transparency_cols.extend([pos_col, f"ape_partial_score_{col}"])
                    
                else:
                    # Generic numeric handling
                    vals_raw = pd.to_numeric(df_ranked[col], errors="coerce")
                    is_missing = vals_raw.isna()
                    vals = vals_raw.fillna(0)
                    
                    # Global vs Local Normalization
                    col_stats = global_stats.get(col) if global_stats else None
                    if col_stats and isinstance(col_stats, dict) and "min" in col_stats and "max" in col_stats:
                        min_val = float(col_stats["min"])
                        max_val = float(col_stats["max"])
                    else:
                        min_val = vals.min()
                        max_val = vals.max()
                    
                    if max_val == min_val:
                         req_score = pd.Series(100.0, index=df_ranked.index)
                    else:
                        # Helper per gestire valori che potrebbero essere liste (es. [10] invece di 10)
                        def safe_float(v):
                            if isinstance(v, list):
                                return float(v[0]) if v else 0.0
                            try:
                                return float(v)
                            except (ValueError, TypeError):
                                return 0.0

                        exclusive = req.get("exclusive", False)
                        if op in [">=", ">"]:
                            # Linear growth with threshold T and cap at 2T
                            T = safe_float(target_val)
                            if T > 0:
                                req_score = ((vals - T) / T * 100).clip(0, 100)
                                if exclusive:
                                    req_score = req_score.mask(vals <= T, 0.0)
                                
                                # Ensure minimum 0.1 if vals >= T (but not if missing or exclusive failure)
                                req_score = req_score.mask((req_score == 0) & (vals >= T) & (~is_missing) & (~exclusive), 0.1)
                            else:
                                req_score = pd.Series(100.0, index=df_ranked.index)
                        elif op in ["<=", "<"]:
                            # Linear decay with threshold T and cap at T/2
                            T = safe_float(target_val)
                            if T > 0:
                                req_score = ((T - vals) / (T / 2) * 100).clip(0, 100)
                                if exclusive:
                                    req_score = req_score.mask(vals >= T, 0.0)
                                    
                                # Ensure minimum 0.1 if vals <= T
                                req_score = req_score.mask((req_score == 0) & (vals <= T) & (~is_missing) & (~exclusive), 0.1)
                            else:
                                req_score = pd.Series(0.0, index=df_ranked.index)
                        else: # == or IN (fallback)
                            # For equality, we stick to distance from target as 'relative' is ambiguous without a target
                            target_num = safe_float(target_val)
                            diff = np.abs(vals - target_num)
                            
                            # Normalizzazione relativa (la distanza massima è definita dal range del dataset)
                            # Se usiamo global_stats, il denominatore è (max_val - min_val)
                            # Altrimenti usiamo il diff massimo locale
                            range_val = (max_val - min_val) if max_val != min_val else 0
                            if range_val > 0:
                                req_score = (100 - (diff / range_val * 100)).clip(0, 100)
                            else:
                                max_diff = diff.max()
                                min_diff = diff.min()
                                if max_diff == min_diff:
                                    req_score = pd.Series(100.0, index=df_ranked.index)
                                else:
                                    req_score = ((max_diff - diff) / (max_diff - min_diff) * 100).clip(0, 100)
                    
                    # Set score to 0 for rows with missing values
                    req_score = req_score.where(~is_missing, 0)
                
                # Store partial score for this requirement
                df_ranked[f"ape_partial_score_{col}"] = req_score.round(1)
                transparency_cols.append(f"ape_partial_score_{col}")
                
                total_scores += req_score

            if valid_req_count > 0:
                df_ranked["ape_score"] = (total_scores / valid_req_count).round(1)
                
                # Add transparency: weight per column
                weight = round(1.0 / valid_req_count, 3)
                for col in used_columns:
                    df_ranked[f"ape_weight_{col}"] = weight
            else:
                df_ranked["ape_score"] = 0.0
                
            cols_to_return = ["id", "ape_score"] + list(used_columns)
            weight_cols = [f"ape_weight_{c}" for c in used_columns]
            
            # Combine all requested columns and deduplicate while preserving order
            all_requested_cols = cols_to_return + weight_cols + transparency_cols
            unique_cols = []
            for c in all_requested_cols:
                if c not in unique_cols and c in df_ranked.columns:
                    unique_cols.append(c)
            
            return df_ranked[unique_cols]

        # 2. Logica Fallback (Deterministica standard)
        # Se non ci sono requisiti specifici, assegniamo 0 anziché punteggi medi
        # per non "sporcare" il ranking se l'utente non ha chiesto esplicitamente APE.
        used_col = None
        if "ape_total_points" in df_ranked.columns and not df_ranked["ape_total_points"].isna().all():
            used_col = "ape_total_points"
        elif "ape_score_total" in df_ranked.columns and not df_ranked["ape_score_total"].isna().all():
            used_col = "ape_score_total"

        if used_col:
            points_raw = pd.to_numeric(df_ranked[used_col], errors="coerce")
            is_missing = points_raw.isna()
            points = points_raw.fillna(0)
            
            col_stats = global_stats.get(used_col) if global_stats else None
            if col_stats and isinstance(col_stats, dict) and "min" in col_stats and "max" in col_stats:
                p_min = float(col_stats["min"])
                p_max = float(col_stats["max"])
            else:
                p_min = points.min()
                p_max = points.max()
            
            if p_max == p_min:
                partial_score = pd.Series(100.0, index=df_ranked.index)
            else:
                partial_score = ((points - p_min) / (p_max - p_min) * 100).clip(0, 100)
            
            # Set score to 0 for rows with missing values
            partial_score = partial_score.where(~is_missing, 0)
                
            df_ranked["ape_score"] = partial_score
            df_ranked[f"ape_partial_score_{used_col}"] = df_ranked["ape_score"]
            df_ranked["ape_score"] = df_ranked["ape_score"].round(1)
            
            cols_to_return = ["id", "ape_score", used_col]
            df_ranked[f"ape_weight_{used_col}"] = 1.0
            cols_to_return.append(f"ape_weight_{used_col}")
            cols_to_return.append(f"ape_partial_score_{used_col}")
            return df_ranked[cols_to_return]
        else:
            df_ranked["ape_score"] = 0.0
            return df_ranked[["id", "ape_score"]]

