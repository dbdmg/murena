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
from app.utils.decorators import log_llm_usage
from app.utils.json_parser import safe_extract_json


class PoiAgentOutput(BaseModel):
    """Schema di output strutturato per il Poi Agent."""
    found: bool = Field(default=False, description="True se sono state identificate necessità relative ai POI nella query dell'utente")
    categories: List[str] = Field(default_factory=list, description="Lista delle categorie selezionate e ordinate per importanza. Includi SOLO le categorie strettamente pertinenti alla query.")
    punteggi_minimi: Dict[str, float] = Field(description="Mappatura categoria -> punteggio minimo richiesto (scala 1-5). Deve contenere una chiave per ogni categoria presente in 'categories'.")


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
            return self._run_ranking(**kwargs)
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
                categories=structured_response.categories,
                punteggi_minimi=structured_response.punteggi_minimi,
                prompt=PromptRecord(
                    system=system_content,
                    user=user_text,
                    full_text=full_text,
                ),
            )
        except Exception as e:
            return PoiAgentResult(
                raw_text=json.dumps({"error": str(e), "found": False, "categories": [], "punteggi_minimi": {}}),
                prompt=None,
            )

    def _run_ranking(self, *, df: pd.DataFrame, ranked_categories: List[str]) -> pd.DataFrame:
        """
        Modalità ranking: calcolo punteggio deterministico basato su pesi posizionali (1/1, 1/2, 1/3...).
        """
        if df is None or df.empty:
            if df is not None:
                df["poi_score"] = 0
            return df

        if not ranked_categories:
            df["poi_score"] = 0
            return df

        df_ranked = df.copy()
        
        # 1. Calcola i pesi posizionali: 1/1, 1/2, 1/3...
        weights = {}
        for i, cat in enumerate(ranked_categories):
            weights[cat] = 1.0 / (i + 1)
            
        # 2. Normalizza i pesi
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {cat: w / total_weight for cat, w in weights.items()}
            
        # 3. Calcola lo score pesato per ogni riga
        # Poiché le colonne originali (sanita, mobilita, ecc.) sono in scala 1-5,
        # normalizziamo a 0-100: (val - 1) / 4 * 100
        
        def calculate_row_score(row):
            score = 0
            for cat, weight in weights.items():
                if cat in row:
                    val = pd.to_numeric(row[cat], errors="coerce")
                    if not pd.isna(val):
                        # (val - 1) / 4 -> scala 0-1
                        # * weight -> pesato
                        # * 100 -> scala 0-100
                        norm_val = max(0, min(1, (val - 1) / 4))
                        score += norm_val * weight * 100
            return score

        df_ranked["poi_score"] = df_ranked.apply(calculate_row_score, axis=1)
        df_ranked["poi_score"] = df_ranked["poi_score"].round(1)

        # Add transparency columns: weight per category
        cols_to_return = ["id", "poi_score"]
        used_cats = [cat for cat in ranked_categories if cat in df_ranked.columns]
        weight_cols = []
        
        for cat in used_cats:
            # Weight used for this category
            weight = weights.get(cat, 0.0)
            col_name = f"poi_weight_{cat}"
            df_ranked[col_name] = round(weight, 3)
            weight_cols.append(col_name)
        
        return df_ranked[cols_to_return + list(used_cats) + weight_cols]
