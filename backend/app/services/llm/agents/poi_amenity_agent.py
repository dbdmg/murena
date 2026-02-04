import json
import re
from typing import Any, Dict
from datetime import datetime

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from geopy.distance import geodesic

from app.core.config import settings
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PoiAmenityAgentResult, AmenityResponse, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json

import pandas as pd
import os

# Agent models configuration
AGENT_MODELS = settings.agent_models

# Importa le categorie dalla configurazione centralizzata
from amenities_config import CATEGORIES

# Carica il dataset distinct_amenities_per_category
csv_path = os.path.join(os.path.dirname(__file__), '../../../../notebooks/01_pois/distinct_amenities_per_category.csv')
df_amenities = pd.read_csv(csv_path)
CATEGORY_AMENITIES = df_amenities.groupby('categoria')['amenity_value'].apply(list).to_dict()

# Path per i dataset necessari al calcolo dello score
CLUSTER_AMENITY_COUNTS_PATH = os.path.join(
    os.path.dirname(__file__),
    '../../../../notebooks/03_clustering/cluster_amenity_percentages_n_150.csv'
)

# Genera la mappatura amenity -> categoria dinamicamente
AMENITY_TO_CATEGORY = {}
for category, amenities in CATEGORY_AMENITIES.items():
    for amenity in amenities:
        AMENITY_TO_CATEGORY[amenity] = category

# Genera la lista di amenity per categoria per il prompt
def get_category_amenities_str(category_weights):
    lines = []
    # Filtra solo le categorie con peso > 0
    selected_categories = [cat for cat, weight in category_weights.items() if weight > 0]
    for category in selected_categories:
        if category in CATEGORY_AMENITIES:
            amenity_names = CATEGORY_AMENITIES[category]
            lines.append(f"- {category.capitalize()}: {', '.join(amenity_names)}")
    return '\n'.join(lines)


DEFAULT_SYSTEM = """
Sei un esperto analista urbano. Data una richiesta utente e una lista di categorie di servizi preselezionate, il tuo compito è selezionare i servizi delle categorie selezionate che devono essere in prossimità per soddisfare la richiesta.

**Istruzioni**:
- Per ogni categoria, seleziona SOLO i servizi che devono essere in prossimità per la richiesta.
- Se nessun servizio in una categoria deve essere in prossimità, non selezionare nulla per quella categoria.

**Output** (JSON puro senza testo):
{{{{
    "amenities": {{{{
        "categoria1": ["servizio1_1", "servizio1_2"],
        "categoria2": ["servizio2_1"]
    }}}}
}}}}
"""

DEFAULT_USER = """**Richiesta Utente**: {query}

**Categorie Selezionate**: {selected_categories}

**Servizi disponibili per categoria**:
{available_amenities}"""


class PoiAmenityAgent(BaseAgent):
    name = "poi-amenity-agent"

    def __init__(self, model_name: str = None):
        resolved_model = model_name or AGENT_MODELS.get("poi_amenity_agent") or AGENT_MODELS.get("default")
        self.llm = get_llm(model_name=resolved_model)
        
        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("poi_amenity_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("poi_amenity_agent", DEFAULT_USER)
        
        # Create ChatPromptTemplate with system/user separation
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                ("user", self.user_template),
            ]
        )
        self.parser = StrOutputParser()
        self.chain = self.prompt | self.llm | self.parser

    @log_llm_usage
    @handle_agent_error(
        fallback_value=PoiAmenityAgentResult(
            raw_text="{}",
            prompt=PromptRecord(system="", user="", full_text="")
        )
    )
    def run(self, *, query: str, category_weights: Dict[str, float]) -> PoiAmenityAgentResult:
        selected_categories = [cat for cat, weight in category_weights.items() if weight > 0]
        available_amenities = get_category_amenities_str(category_weights)
        
        prompt_inputs = {
            "query": query,
            "selected_categories": ", ".join(selected_categories),
            "available_amenities": available_amenities
        }
        
        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        raw = invoke_with_langfuse(self.chain, prompt_inputs)

        # Parse with safe_extract_json using Pydantic model
        parsed_data = safe_extract_json(raw, schema=AmenityResponse)

        amenities_by_category = {}
        if parsed_data and isinstance(parsed_data, AmenityResponse):
            amenities_by_category = parsed_data.amenities
        
        # Calcola i pesi delle amenity: 1/n per quelle selezionate, 0 per quelle non selezionate
        amenity_weights = {}
        for category, amenities in amenities_by_category.items():
            amenity_weights[category] = {}
            if amenities:
                n = len(amenities)
                for amenity in amenities:
                    amenity_weights[category][amenity] = 1.0 / n
        
        # Aggiungi peso 0 per le amenity non selezionate in ogni categoria
        for category in selected_categories:
            if category not in amenity_weights:
                amenity_weights[category] = {}
            
            # Ottieni tutte le amenity possibili per questa categoria
            all_amenities = CATEGORY_AMENITIES.get(category, [])
            for amenity in all_amenities:
                if amenity not in amenity_weights[category]:
                    amenity_weights[category][amenity] = 0.0
    
        prompt_record = PromptRecord(
            system=self.system_prompt.strip(),
            user=user_text,
            full_text=full_text,
        )

        result_payload = {
            "selected_categories": selected_categories,
            "selected_amenities": amenities_by_category,
            "category_weights": category_weights,
            "amenity_weights": amenity_weights
        }

        return PoiAmenityAgentResult(
            raw_text=json.dumps(result_payload),
            prompt=prompt_record
        )
