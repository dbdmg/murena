import json
from typing import List, Union, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, TypologyAgentResult, TypologyResponse
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json


class TypologyAgent(BaseAgent):
    name = "typology-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("typology_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("typology_agent")
        self.user_template = get_user_template("typology_agent")

        # Create ChatPromptTemplate with system/user separation
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )
        self.parser = StrOutputParser()
        self.chain = self.prompt | self.llm | self.parser

    @log_llm_usage
    @handle_agent_error(
        fallback_value=TypologyAgentResult(raw_text="Error", prompt=None)
    )
    def run(self, *, query: str = None, mode: str = "filtering", **kwargs) -> Union[TypologyAgentResult, pd.DataFrame]:
        """
        Esegue l'agente in due modalità:
        - filtering: Identifica le tipologie pertinenti ordinate per ranking (LLM).
        - ranking: Calcola uno score 0-100 basato sulla posizione della tipologia nel ranking.
        """
        if mode == "filtering":
            return self._run_filtering(
                query=query, 
                available_typologies=kwargs.get("available_typologies"),
                statistics=kwargs.get("statistics")
            )
        elif mode == "ranking":
            return self._run_ranking(**kwargs)
        else:
            raise ValueError(f"Modalità '{mode}' non supportata dal TypologyAgent.")

    def _run_filtering(self, query: str, available_typologies: Union[str, List[str]], statistics: dict = None) -> TypologyAgentResult:
        # If available_typologies is a list, join it.
        if isinstance(available_typologies, list):
            typologies_str = ", ".join([f'"{t}"' for t in available_typologies])
        else:
            typologies_str = available_typologies or "N/D"
            
        stats_str = json.dumps(statistics, indent=2, ensure_ascii=False) if statistics else "N/D"

        prompt_inputs = {
            "query": query, 
            "available_typologies": typologies_str,
            "statistics": stats_str
        }

        # Format user prompt with variables
        user_text = self.render_template(self.user_template, **prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        response_text = invoke_with_langfuse(
            self.chain,
            {
                "system_content": self.system_prompt,
                "user_content": user_text,
            },
        )

        return TypologyAgentResult(
            raw_text=response_text,
            prompt=PromptRecord(
                system=self.system_prompt.strip(),
                user=user_text,
                full_text=full_text,
            ),
        )

    def _run_ranking(self, *, df: pd.DataFrame, ranked_typologies: List[str]) -> pd.DataFrame:
        """
        Modalità ranking: assegna uno score (0-100) in base alla posizione della tipologia nel ranking.
        La prima tipologia riceve 100, l'ultima tra quelle selezionate riceve uno score base (es. 50), 
        le altre tipologie non selezionate ricevono 0.
        """
        if df is None or df.empty:
            if df is not None:
                df["typology_score"] = 0
            return df

        if not ranked_typologies:
            df["typology_score"] = 100 # Se non ci sono filtri, tutte sono ugualmente valide
            return df

        df_ranked = df.copy()
        
        # Mappa delle tipologie al loro punteggio
        # Es: 3 tipologie -> [100, 75, 50]
        n = len(ranked_typologies)
        if n == 1:
            scores = {ranked_typologies[0]: 100.0}
        else:
            # Distribuzione lineare tra 100 e 50
            scores = {
                typ: round(100 - (i * (50 / (n - 1))), 1) 
                for i, typ in enumerate(ranked_typologies)
            }

        def get_score(val):
            return scores.get(val, 0.0)

        df_ranked["typology_score"] = df_ranked["tipologia_bene_immobile"].apply(get_score)
        
        return df_ranked[["id", "tipologia_bene_immobile", "typology_score"]]
