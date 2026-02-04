import json
import re
from typing import Any, Dict
from datetime import datetime

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from geopy.distance import geodesic

from app.core.config import settings
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PoiAmenityAgentResult
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_prompt_template
from app.utils.decorators import handle_agent_error, log_llm_usage

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


DEFAULT_PROMPT = """
Sei un esperto analista urbano. Data una richiesta utente e una lista di categorie di servizi preselezionate, il tuo compito è selezionare i servizi delle categorie selezionate che devono essere in prossimità per soddisfare la richiesta.

**Richiesta Utente**: {query}

**Categorie Selezionate**: {selected_categories}

**Servizi disponibili per categoria**:
{available_amenities}

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


class PoiAmenityAgent(BaseAgent):
    name = "poi-amenity-agent"

    def __init__(self, model_name: str = None):
        resolved_model = model_name or AGENT_MODELS.get("poi_amenity_agent") or AGENT_MODELS.get("default")
        self.llm = get_llm(model_name=resolved_model)
        
        # Carica i dataset per il calcolo dello score
        if os.path.exists(CLUSTER_AMENITY_COUNTS_PATH):
            self.cluster_amenity_percentages_df = pd.read_csv(CLUSTER_AMENITY_COUNTS_PATH)
        else:
            raise FileNotFoundError(f"Cluster amenity percentages not found at {CLUSTER_AMENITY_COUNTS_PATH}")

    @log_llm_usage
    @handle_agent_error(
        fallback_value=PoiAmenityAgentResult(
            raw_text="",
            selected_categories=[],
            selected_amenities={},
            category_weights={},
            amenity_weights={}
        )
    )
    def run(self, query: str, category_weights: Dict[str, float]) -> PoiAmenityAgentResult:
        selected_categories = [cat for cat, weight in category_weights.items() if weight > 0]
        available_amenities = get_category_amenities_str(category_weights)
        
        template_text = get_prompt_template("poi_amenity_agent", "template", DEFAULT_PROMPT)
        prompt_template = PromptTemplate.from_template(template_text)

        chain = prompt_template | self.llm | StrOutputParser()

        try:
            response_text = invoke_with_langfuse(chain, {
                "query": query,
                "selected_categories": ", ".join(selected_categories),
                "available_amenities": available_amenities
            })

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                amenities_by_category = data.get("amenities", {})
                
                # Calcola i pesi delle amenity: 1/n per quelle selezionate, 0 per quelle non selezionate
                amenity_weights = {}
                for category, amenities in amenities_by_category.items():
                    amenity_weights[category] = {}
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
            
            return PoiAmenityAgentResult(
                raw_text=response_text,
                selected_categories=selected_categories,
                selected_amenities=amenities_by_category,
                category_weights=category_weights,
                amenity_weights=amenity_weights
            )

        except Exception as e:
            print(f"Errore PoiAmenityAgent: {e}")
            # Fallback: tutte le amenity con peso 0 per ogni categoria selezionata
            amenity_weights = {}
            for category in selected_categories:
                all_amenities = CATEGORY_AMENITIES.get(category, [])
                amenity_weights[category] = {amenity: 0.0 for amenity in all_amenities}
            return PoiAmenityAgentResult(
                raw_text="",
                selected_categories=selected_categories,
                selected_amenities={},
                category_weights=category_weights,
                amenity_weights=amenity_weights
            )
