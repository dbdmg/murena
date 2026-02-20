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
from app.core.constants import LOCATION_AGENT_COLUMNS
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
        self.structured_llm = self.llm.with_structured_output(LocationResponse, method="function_calling")
        self.chain = self.prompt | self.structured_llm

    def run(
        self,
        *,
        query: str = None,
        mode: str = "filtering",
        **kwargs
    ) -> Union[LocationAgentResult, pd.DataFrame]:
        """
        Esegue l'agente per estrarre luoghi (LLM) o calcolare il ranking (Deterministico).
        """
        try:
            if mode == "filtering":
                return self._run_filtering(query=query)
            elif mode == "ranking":
                return self._run_ranking(
                    df=kwargs.get("df"),
                    places=kwargs.get("places")
                )
            else:
                raise ValueError(f"Modalità '{mode}' non supportata dal LocationAgent.")
        except Exception as e:
            from app.utils.logger import logger
            logger.error(f"Error in {self.name}.run ({mode}): {e}")
            if mode == "ranking":
                df = kwargs.get("df")
                if df is not None:
                    if "location_score" not in df.columns:
                        df["location_score"] = 0.0
                    return df
                return pd.DataFrame()
            return LocationAgentResult(raw_text="{}", found=False, places=[], prompt=None)

    def _run_filtering(self, query: str) -> LocationAgentResult:
        """Modalità originale: estrazione entità geografiche tramite LLM + Geocoding."""
        from app.data.loaders import get_coordinates
        from concurrent.futures import ThreadPoolExecutor

        # Format specific columns list
        columns_str = "\n".join([f"- `{col}`" for col in LOCATION_AGENT_COLUMNS])

        prompt_inputs = {
            "query": query,
            "reference_columns": columns_str
        }

        # Format prompts with variables
        rendered_system_prompt = self.render_template(self.system_prompt, **prompt_inputs).strip()
        user_text = self.render_template(self.user_template, **prompt_inputs).strip()

        # Invocation with structured output
        loc_data: LocationResponse = invoke_with_langfuse(
            self.chain,
            {
                "system_content": rendered_system_prompt,
                "user_content": user_text
            },
        )
        
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
        raw = "{}"
        if loc_data:
            loc_data.places = valid_places
            loc_data.found = has_locations
            raw = loc_data.model_dump_json()

        prompt_record = PromptRecord(
            system=rendered_system_prompt,
            user=user_text,
            full_text=f"[SYSTEM]\n{rendered_system_prompt}\n\n[USER]\n{user_text}",
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
        # Arrotondiamo alla seconda cifra decimale come richiesto
        radius_map = {
            p.name: round(p.radius_km, 2)
            for p in places
        }

        def calculate_score_details(row):
            poi = row.get("poi_riferimento")
            dist = row.get("distanza_km")
            
            if pd.isna(dist) or poi not in radius_map:
                return 0.0, 0.0
            
            # Use dynamic R parameter based on calculation: e^(-(radius_km/R)^3) = 0.2
            # R ≈ radius_km / 1.17195
            
            target_radius = radius_map.get(poi)
            if not target_radius or target_radius <= 0:
                target_radius = 3.0  # default radius if missing
            
            # Già arrotondato sopra, ma per sicurezza nel caso di default
            target_radius = round(target_radius, 2)

            # Calculate R
            # (-ln(0.2))^(1/3)
            decay_constant = (-np.log(0.2))**(1/3)
            R = target_radius / decay_constant
            
            # Truncate if distance exceeds the target radius (consistent with GT)
            if dist > target_radius:
                return 0.0, 0.0

            # Exponential decay formula: e(-(dist/R)^3)
            # This produces a value between 0 and 1
            raw_score = np.exp(-((dist / R) ** 3))
            
            # Normalize to 0-100
            final_score = raw_score * 100.0
            
            return final_score, raw_score

        # Apply calculation returning tuple
        score_details = df_ranked.apply(calculate_score_details, axis=1)
        
        # Unpack into columns
        df_ranked["location_score"] = score_details.apply(lambda x: x[0]).round(1)
        df_ranked["location_raw_score"] = score_details.apply(lambda x: x[1]).round(4)
        
        # Add transparency: radius used per row
        def get_radius(row):
            poi = row.get("poi_riferimento")
            return radius_map.get(poi, 0.0) if poi else 0.0

        df_ranked["location_radius_used_km"] = df_ranked.apply(get_radius, axis=1)
        df_ranked["location_partial_score"] = df_ranked["location_score"]

        return df_ranked[["id", "location_score", "distanza_km", "poi_riferimento", "location_raw_score", "location_partial_score", "location_radius_used_km"]]

