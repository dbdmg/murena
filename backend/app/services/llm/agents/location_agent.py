import json
from typing import Any, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import LocationAgentResult, Place, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json


# Modello per la risposta strutturata
class LocationResponse(BaseModel):
    places: List[Place] = Field(
        default_factory=list, description="Lista dei luoghi estratti"
    )


DEFAULT_SYSTEM = """# RUOLO
Sei il Location Agent per l'applicazione Real Estate AI.
Il tuo compito è estrarre dalla query dell'utente TUTTI i riferimenti geografici (città, zone, POI, indirizzi).

# REGOLE
1. Identifica OGNI luogo menzionato esplicitamente o implicitamente.
2. Per ogni luogo, estrai: nome, città (se presente), e coordinate geografiche approssimate.
3. Se non ci sono luoghi specifici, restituisci una lista vuota.
4. NON inventare luoghi se non sono nel testo.

# OUTPUT
Restituisci ESCLUSIVAMENTE un JSON valido:
{
  "places": [
    {"name": "Nome Luogo", "city": "Città", "lat": 45.07, "lon": 7.68}
  ]
}

# ESEMPI
Query: "Trilocale vicino al Politecnico di Torino"
Output: {{"places": [{{"name": "Politecnico di Torino", "city": "Torino", "lat": 45.0628, "lon": 7.6621}}]}}

Query: "Appartamento economico"
Output: {{"places": []}}
"""

DEFAULT_USER = """Frase: "{query}" """


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
        self.system_prompt = get_system_prompt("location_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("location_agent", DEFAULT_USER)

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
        fallback_value=LocationAgentResult(raw_text="Error", prompt=None)
    )
    def run(self, *, query: str) -> LocationAgentResult:
        prompt_inputs = {"query": query}

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        raw = invoke_with_langfuse(self.chain, prompt_inputs)

        prompt_record = PromptRecord(
            system=self.system_prompt.strip(),
            user=user_text,
            full_text=full_text,
        )

        return LocationAgentResult(raw_text=raw, prompt=prompt_record)
