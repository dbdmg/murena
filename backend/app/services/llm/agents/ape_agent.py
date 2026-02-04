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
from app.services.llm.agents.schema import ApeAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage
from app.utils.json_parser import safe_extract_json


class ApeAgentOutput(BaseModel):
    """Schema di output strutturato per l'APE Agent."""
    found: bool = Field(default=False, description="True se ci sono criteri energetici rilevanti")
    suggested_filters: List[str] = Field(default_factory=list, description="Filtri APE suggeriti")


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
        self.structured_llm = self.llm.with_structured_output(ApeAgentOutput, method="function_calling")
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
            statistics=stats_str,
            score_legend=score_legend or "Nessuna legenda disponibile.",
        )

        prompt_inputs = {"system_content": system_content, "query": query}
        user_text = self.render_template(self.user_template, query=query).strip()
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

    def _run_ranking(self, *, df: pd.DataFrame) -> pd.DataFrame:
        """Modalità ranking: calcolo score deterministico 0-100 basato sulla qualità energetica."""
        if df is None or df.empty:
            if df is not None:
                df["energy_score"] = 0
            return df

        df_ranked = df.copy()
        
        # Le colonne APE sono calcolate in processors.py: calculate_ape_score
        # ape_total_points va da 6 a 20. Normalizziamo 100 * (points - 6) / (20 - 6)
        if "ape_total_points" in df_ranked.columns:
            points = pd.to_numeric(df_ranked["ape_total_points"], errors="coerce").fillna(6)
            df_ranked["energy_score"] = (100 * (points - 6) / (20 - 6)).clip(0, 100)
        elif "ape_score_total" in df_ranked.columns:
            # Fallback se abbiamo solo lo score 1-5
            score = pd.to_numeric(df_ranked["ape_score_total"], errors="coerce").fillna(1)
            df_ranked["energy_score"] = ((score - 1) * 25).clip(0, 100)
        else:
            df_ranked["energy_score"] = 0
            
        df_ranked["energy_score"] = df_ranked["energy_score"].round(1)
        return df_ranked
