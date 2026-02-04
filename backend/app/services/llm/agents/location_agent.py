import json
from typing import Any, List, Optional, Union
import pandas as pd
import numpy as np

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import LocationAgentResult, Place, PromptRecord, LocationResponse
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json
from app.data.processors import calculate_travel_times_df


class LocationAgent(BaseAgent):
    name = "location-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("location_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("location_agent")
        self.user_template = get_user_template("location_agent")

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
        fallback_value=LocationAgentResult(raw_text="Error", prompt=None)
    )
    def run(self, *, query: str = None, mode: str = "filtering", **kwargs) -> Union[LocationAgentResult, pd.DataFrame]:
        """
        Esegue l'agente in due modalità:
        - filtering: Estrae i luoghi e la distanza raggio dall'LLM.
        - ranking: Calcola uno score deterministico (0-100) per gli immobili in base alla distanza.
        """
        if mode == "filtering":
            return self._run_filtering(query=query)
        elif mode == "ranking":
            return self._run_ranking(**kwargs)
        else:
            raise ValueError(f"Modalità '{mode}' non supportata dal LocationAgent.")

    def _run_filtering(self, query: str) -> LocationAgentResult:
        """Modalità originale: estrazione entità geografiche tramite LLM + Geocoding."""
        from app.data.loaders import get_coordinates
        from concurrent.futures import ThreadPoolExecutor

        prompt_inputs = {"query": query}

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        raw = invoke_with_langfuse(
            self.chain,
            {
                "system_content": self.system_prompt,
                "user_content": user_text,
            },
        )

        # Parsing per estrarre l'indicazione di successo/presenza luoghi
        loc_data = safe_extract_json(raw, schema=LocationResponse)
        places = loc_data.places if loc_data else []

        # Geocoding logic
        valid_places = []
        if places:
            def geocode_place(place):
                search_query = (
                    f"{place.name}, {place.city}" if place.city else place.name
                )
                try:
                    lat, lon = get_coordinates(search_query)
                except Exception:
                    lat, lon = None, None
                
                # Update place object
                place.lat = lat
                place.lon = lon
                return place

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(geocode_place, p) for p in places]
                for future in futures:
                    p = future.result()
                    if p.lat is not None and p.lon is not None:
                        valid_places.append(p)

        # Update found flag based on SUCCESSFUL GEOCODING
        has_locations = len(valid_places) > 0
        
        # Update raw_text with enriched data
        if loc_data:
            loc_data.places = valid_places
            loc_data.found = has_locations
            raw = loc_data.model_dump_json()

        prompt_record = PromptRecord(
            system=self.system_prompt.strip(),
            user=user_text,
            full_text=full_text,
        )

        return LocationAgentResult(
            raw_text=raw, 
            prompt=prompt_record, 
            has_locations=has_locations
        )


    def _run_ranking(self, *, df: pd.DataFrame, places: List[Place]) -> pd.DataFrame:
        """Modalità ranking: calcolo score deterministico 0-100 basato sulla distanza."""
        if df is None or df.empty or not places:
            if df is not None:
                df["location_score"] = 0
            return df

        # Prepariamo il payload per calculate_travel_times_df
        # Formato atteso: [[name, lat, lon], ...]
        locations_payload = []
        for p in places:
            if p.lat is not None and p.lon is not None:
                locations_payload.append([p.name, p.lat, p.lon])
        
        if not locations_payload:
            df["location_score"] = 0
            return df

        # Calcoliamo le distanze (se non sono già presenti nel DF o se vogliamo ricalcolarle per questi POI)
        # La funzione calculate_travel_times_df aggiunge 'distanza_km' e 'poi_riferimento'
        df_ranked = calculate_travel_times_df(df, locations_payload)

        # Creiamo un mapping raggio per ogni POI
        radius_map = {p.name: p.radius_km for p in places}

        def calculate_score(row):
            poi = row.get("poi_riferimento")
            dist = row.get("distanza_km")
            
            if pd.isna(dist) or poi not in radius_map:
                return 0
            
            radius = radius_map[poi]
            if radius <= 0:
                return 100 if dist == 0 else 0
            
            # Score lineare: 100 a distanza 0, 0 a distanza >= radius
            score = 100 * (1 - (dist / radius))
            return max(0, min(100, score))

        df_ranked["location_score"] = df_ranked.apply(calculate_score, axis=1)
        
        # Arrotondiamo per pulizia
        df_ranked["location_score"] = df_ranked["location_score"].round(1)
        
        return df_ranked

