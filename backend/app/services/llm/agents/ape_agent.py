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
                ("user", self.user_template),
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
            return self._run_ranking(**kwargs)
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
        
        system_content = self.render_template(
            self.system_prompt,
            score_legend=score_legend or "Nessuna legenda disponibile.",
        )

        prompt_inputs = {
            "system_content": system_content, 
            "query": query,
            "statistics": stats_str
        }
        user_text = self.render_template(self.user_template, query=query, statistics=stats_str).strip()
        full_text = f"[SYSTEM]\n{system_content}\n\n[USER]\n{user_text}"

        try:
            structured_response: ApeAgentOutput = invoke_with_langfuse(self.chain, prompt_inputs)
            has_filters = structured_response.found

            return ApeAgentResult(
                raw_text=json.dumps(structured_response.model_dump(), ensure_ascii=False),
                has_filters=has_filters,
                prompt=PromptRecord(
                    system=system_content,
                    user=user_text,
                    full_text=full_text,
                ),
            )
        except Exception as e:
            return ApeAgentResult(
                raw_text=json.dumps({"error": str(e), "found": False, "suggested_filters": []}),
                prompt=None,
            )

    def _run_ranking(self, *, df: pd.DataFrame, requirements: List[Dict[str, Any]] = None) -> pd.DataFrame:
        """Modalità ranking: calcolo score 0-100 basato su requisiti LLM o logica deterministica."""
        if df is None or df.empty:
            if df is not None:
                df["ape_score"] = 0
            return df

        df_ranked = df.copy()
        
        # 1. Se abbiamo requisiti dinamici dall'LLM (filtering), usiamoli per calcolare lo score
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
                    # A4 is best (Rank 1)
                    ranking_map = {
                        "A4": (100, 1), "A3": (95, 2), "A2": (90, 3), "A1": (85, 4),
                        "B": (75, 5), "C": (65, 6), "D": (50, 7), "E": (35, 8),
                        "F": (20, 9), "G": (5, 10)
                    }
                    
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
                    mult_col = f"ape_multiplier_{col}"
                    
                    df_ranked[pos_col] = rank_pos
                    df_ranked[mult_col] = (req_score / 100.0).round(2)
                    
                    transparency_cols.extend([pos_col, mult_col])
                    
                else:
                    # Generic numeric handling
                    vals = pd.to_numeric(df_ranked[col], errors="coerce").fillna(0)
                    target_num = float(target_val)
                    if op == ">=":
                        max_val = vals.max() or 1.0
                        req_score = np.where(vals >= target_num, 100, (vals / (target_num + 1e-6)) * 80)
                    elif op == "<=":
                        req_score = np.where(vals <= target_num, 100, (target_num / (vals + 1e-6)) * 80)
                    else: # ==
                        req_score = (vals == target_num).astype(float) * 100
                
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
            
            # Combine: Base + Weights + Categorical Transparency
            return df_ranked[cols_to_return + weight_cols + transparency_cols]

        # 2. Logica Fallback (Deterministica standard)
        # Here weight is 1.0 for the single source column used
        used_col = None
        if "ape_total_points" in df_ranked.columns:
            points = pd.to_numeric(df_ranked["ape_total_points"], errors="coerce").fillna(6)
            df_ranked["ape_score"] = (100 * (points - 6) / (20 - 6)).clip(0, 100)
            used_col = "ape_total_points"
        elif "ape_score_total" in df_ranked.columns:
            score = pd.to_numeric(df_ranked["ape_score_total"], errors="coerce").fillna(1)
            df_ranked["ape_score"] = ((score - 1) * 25).clip(0, 100)
            used_col = "ape_score_total"
        else:
            df_ranked["ape_score"] = 0
            
        df_ranked["ape_score"] = df_ranked["ape_score"].round(1)
        
        cols_to_return = ["id", "ape_score"]
        if used_col:
            cols_to_return.append(used_col)
            df_ranked[f"ape_weight_{used_col}"] = 1.0
            cols_to_return.append(f"ape_weight_{used_col}")
                
        return df_ranked[cols_to_return]
