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
from app.services.llm.agents.schema import PromptRecord, PropertyTechnicalAgentResult, PropertyTechnicalResponse
from app.core.constants import PROPERTY_TECHNICAL_AGENT_COLUMNS
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json


class PropertyTechnicalAgent(BaseAgent):
    name = "property-technical-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("property_technical_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("property_technical_agent")
        self.user_template = get_user_template("property_technical_agent")

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
        fallback_value=PropertyTechnicalAgentResult(raw_text="Error", prompt=None)
    )
    def run(self, *, query: str = None, mode: str = "filtering", **kwargs) -> Union[PropertyTechnicalAgentResult, pd.DataFrame]:
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
            raise ValueError(f"Modalità '{mode}' non supportata dal PropertyTechnicalAgent.")

    def _run_filtering(self, query: str, available_typologies: Union[str, List[str]], statistics: dict = None) -> PropertyTechnicalAgentResult:
        # If available_typologies is a list, join it.
        if isinstance(available_typologies, list):
            descriptions_str = ", ".join([f'"{t}"' for t in available_typologies])
        else:
            descriptions_str = available_typologies or "N/D"
            
        stats_str = json.dumps(statistics, indent=2, ensure_ascii=False) if statistics else "N/D"

        # Format specific columns list
        columns_str = "\n".join([f"- `{col}`" for col in PROPERTY_TECHNICAL_AGENT_COLUMNS])

        prompt_inputs = {
            "query": query, 
            "available_typologies": descriptions_str,
            "statistics": stats_str,
            "reference_columns": columns_str
        }

        # Format prompts with variables
        rendered_system_prompt = self.render_template(self.system_prompt, **prompt_inputs).strip()
        user_text = self.render_template(self.user_template, **prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{rendered_system_prompt}\n\n[USER]\n{user_text}"

        response_text = invoke_with_langfuse(
            self.chain,
            {
                "system_content": rendered_system_prompt,
                "user_content": user_text,
            },
        )

        return PropertyTechnicalAgentResult(
            raw_text=response_text,
            prompt=PromptRecord(
                system=rendered_system_prompt,
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
                df["property_technical_score"] = 0
            return df

        if not ranked_typologies:
            df["property_technical_score"] = 100 # Se non ci sono filtri, tutte sono ugualmente valide
            return df

        df_ranked = df.copy()
        
        # Mappa delle tipologie al loro punteggio
        # Es: 3 tipologie -> [100, 75, 50]
        n = len(ranked_typologies)
        property_map = {} # map property_value -> (score, rank_position)
        
        if n == 1:
             property_map[ranked_typologies[0]] = (100.0, 1)
        else:
            # Distribuzione armonica: 100, 50, 33, 25...
            for i, typ in enumerate(ranked_typologies):
                # Score calculation: 100 / (position)
                score = round(100.0 / (i + 1), 1)
                property_map[typ] = (score, i + 1)

        def get_details(val):
            # Returns tuple (score, rank)
            if val in property_map:
                score, rank = property_map[val]
                return score, rank
            return 0.0, "N/A"

        # Apply to create temporary series
        details = df_ranked["tipologia_bene_immobile"].apply(get_details)
        
        # Expand into columns
        df_ranked["property_technical_score"] = details.apply(lambda x: x[0])
        df_ranked["property_technical_partial_score"] = df_ranked["property_technical_score"]
        df_ranked["property_technical_rank_position"] = details.apply(lambda x: x[1])
        
        # Columns Order: ID, Score, Data, Metadata(Weights/Analysis)
        return df_ranked[["id", "property_technical_score", "tipologia_bene_immobile", "property_technical_rank_position", "property_technical_partial_score"]]
