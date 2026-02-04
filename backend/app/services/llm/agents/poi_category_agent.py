import json
import re
from typing import Dict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PoiCategoryAgentResult
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage

import pandas as pd
import os

# Agent models configuration
AGENT_MODELS = settings.agent_models

# Importa le categorie dalla configurazione centralizzata
from amenities_config import CATEGORIES, PROMPT_CATEGORIES

# Carica il dataset distinct_amenities_per_category
csv_path = os.path.join(os.path.dirname(__file__), '../../../../notebooks/01_pois/distinct_amenities_per_category.csv')
df_amenities = pd.read_csv(csv_path)
CATEGORY_AMENITIES = df_amenities.groupby('categoria')['amenity_value'].apply(list).to_dict()

# Genera la mappatura amenity -> categoria dinamicamente
AMENITY_TO_CATEGORY = {}
for category, amenities in CATEGORY_AMENITIES.items():
    for amenity in amenities:
        AMENITY_TO_CATEGORY[amenity] = category

# Genera la lista di amenity per categoria per il prompt
def get_category_amenities_str():
    lines = []
    for category, amenities in CATEGORY_AMENITIES.items():
        amenity_names = amenities
        lines.append(f"- {category.capitalize()}: {', '.join(amenity_names)}")
    return '\n'.join(lines)

DEFAULT_SYSTEM = f"""
Sei un esperto analista urbano. Analizza la richiesta dell'utente e seleziona SOLO le categorie di servizi che devono trovarsi in prossimità del progetto immobiliare descritto.

**Categorie disponibili**: {', '.join(PROMPT_CATEGORIES)}

**Istruzioni**:
- Seleziona SOLO le categorie essenziali per il tipo di progetto
- Sii selettivo: non includere categorie poco rilevanti o generiche
- Ordina per priorità decrescente (più importanti prima)

**Output** (JSON puro senza testo):
{{{{
    "categories": ["categoria1", "categoria2"]
}}}}
"""

DEFAULT_USER = """**Richiesta**: {query}"""


class PoiCategoryAgent(BaseAgent):
    name = "poi-category-agent"

    def __init__(self, model_name: str = None):
        resolved_model = model_name or AGENT_MODELS.get("poi_category_agent") or AGENT_MODELS.get("default")
        self.llm = get_llm(model_name=resolved_model)
        
        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("poi_category_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("poi_category_agent", DEFAULT_USER)

    @log_llm_usage
    @handle_agent_error(
        fallback_value=PoiCategoryAgentResult(
            raw_text="",
            category_weights={cat: 0.0 for cat in PROMPT_CATEGORIES}
        )
    )
    def run(self, query: str) -> PoiCategoryAgentResult:
        prompt_template = PromptTemplate.from_template(self.user_template)

        chain = prompt_template | self.llm | StrOutputParser()

        prompt_inputs = {"query": query}
        
        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        try:
            response_text = invoke_with_langfuse(chain, prompt_inputs)

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                categories = data.get("categories", [])
                
                # Calcola i pesi delle categorie basati sull'ordine di selezione
                category_weights = {}
                for i, cat in enumerate(categories):
                    category_weights[cat] = 1.0 / (i + 1)
                
                # Normalizza i pesi delle categorie selezionate
                if category_weights:
                    total_weight = sum(category_weights.values())
                    category_weights = {cat: weight / total_weight for cat, weight in category_weights.items()}
                
                # Aggiungi peso 0 per le categorie non selezionate
                all_categories = PROMPT_CATEGORIES
                for cat in all_categories:
                    if cat not in category_weights:
                        category_weights[cat] = 0.0

                return PoiCategoryAgentResult(
                    raw_text=response_text,
                    category_weights=category_weights
                )
            else:
                # No JSON found in response, return default
                print(f"⚠️ PoiCategoryAgent: No JSON found in response")
                category_weights = {cat: 0.0 for cat in PROMPT_CATEGORIES}
                return PoiCategoryAgentResult(
                    raw_text=response_text,
                    category_weights=category_weights
                )

        except Exception as e:
            print(f"Errore PoiCategoryAgent: {e}")
            category_weights = {cat: 0.0 for cat in PROMPT_CATEGORIES}
            return PoiCategoryAgentResult(
                raw_text="",
                category_weights=category_weights
            )
