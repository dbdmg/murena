import json
import re
from typing import Dict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PoiCategoryAgentResult, PromptRecord, CategoryResponse
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json

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
        fallback_value=PoiCategoryAgentResult(
            raw_text="",
            category_weights={cat: 0.0 for cat in PROMPT_CATEGORIES},
            prompt=PromptRecord(system="", user="", full_text="")
        )
    )
    def run(self, *, query: str) -> PoiCategoryAgentResult:
        prompt_inputs = {"query": query}

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        raw = invoke_with_langfuse(self.chain, prompt_inputs)

        # Parse with safe_extract_json using Pydantic model
        parsed_data = safe_extract_json(raw, schema=CategoryResponse)

        categories = []
        if parsed_data and isinstance(parsed_data, CategoryResponse):
            categories = parsed_data.categories
        else:
            # Fallback for manual or partial creation if strict validation failed but we got dict
            pass

        # Validate categories are in allowed list
        valid_categories = [cat for cat in categories if cat in PROMPT_CATEGORIES]
        if len(valid_categories) != len(categories):
            print(f"⚠️ PoiCategoryAgent: Some categories were invalid: {set(categories) - set(valid_categories)}")
        
        categories = valid_categories
        
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

        prompt_record = PromptRecord(
            system=self.system_prompt.strip(),
            user=user_text,
            full_text=full_text,
        )

        return PoiCategoryAgentResult(raw_text=raw, category_weights=category_weights, prompt=prompt_record)
