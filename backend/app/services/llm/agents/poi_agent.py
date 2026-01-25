from typing import Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PoiAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json


# Modello risposta
class PoiResponse(BaseModel):
    poi_weights: Dict[str, float] = Field(
        default_factory=dict, description="Pesi per categoria POI"
    )
    constraints: Dict[str, List[str]] = Field(
        default_factory=dict, description="Vincoli specifici"
    )


DEFAULT_SYSTEM = """# RUOLO
Sei il POI Agent per l'applicazione Real Estate AI.
Il tuo compito è analizzare quali servizi di prossimità (Points of Interest) sono importanti per l'utente.

# REGOLE
1. Assegna pesi (0.0 - 1.0) alle 6 categorie POI:
   - sanita (Ospedali, farmacie, cliniche)
   - mobilita (Metro, bus, stazioni, parcheggi)
   - verde (Parchi, giardini, aree verdi)
   - sport (Palestre, piscine, centri sportivi)
   - commerciale (Supermercati, negozi, centri commerciali)
   - educazione (Scuole, università, biblioteche)

2. Logica di assegnazione:
   - Menzionato esplicitamente come importante: peso alto (0.7 - 1.0)
   - Non rilevante: peso 0.0
   - Non menzionato: peso di default basso (0.1 - 0.3) in base al contesto

# OUTPUT
Restituisci ESCLUSIVAMENTE un JSON valido:
{
  "poi_weights": {
    "sanita": <float>,
    "mobilita": <float>,
    "verde": <float>,
    "sport": <float>,
    "commerciale": <float>,
    "educazione": <float>
  },
  "constraints": {
    "must_have": ["<categoria>"],
    "must_not_have": []
  }
}
"""

DEFAULT_USER = """Richiesta utente: "{query}" """


class PoiAgent(BaseAgent):
    name = "poi-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("poi_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("poi_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("poi_agent", DEFAULT_USER)

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
        fallback_value=PoiAgentResult(
            raw_text="Error",
            poi_weights={
                "sanita": 0.1,
                "mobilita": 0.1,
                "verde": 0.1,
                "sport": 0.1,
                "commerciale": 0.1,
                "educazione": 0.1,
            },
            constraints={},
            prompt=None,
        )
    )
    def run(self, query: str) -> PoiAgentResult:
        prompt_inputs = {"query": query}

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        response_text = self.chain.invoke(prompt_inputs)

        # Extract JSON using safe_extract_json with schema
        parsed_data = safe_extract_json(response_text, schema=PoiResponse)

        if parsed_data and isinstance(parsed_data, PoiResponse):
            poi_weights = parsed_data.poi_weights
            constraints = parsed_data.constraints
        else:
            # Fallback defaults if parsing fails
            poi_weights = {
                "sanita": 0.1,
                "mobilita": 0.1,
                "verde": 0.1,
                "sport": 0.1,
                "commerciale": 0.1,
                "educazione": 0.1,
            }
            constraints = {}

        return PoiAgentResult(
            raw_text=response_text,
            poi_weights=poi_weights,
            constraints=constraints,
            prompt=PromptRecord(
                system=self.system_prompt.strip(),
                user=user_text,
                full_text=full_text,
            ),
        )
