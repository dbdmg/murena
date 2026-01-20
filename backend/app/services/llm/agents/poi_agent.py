import json
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PoiAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage

DEFAULT_SYSTEM = """Sei un esperto di analisi urbana e servizi (Points of Interest).
Il tuo compito è analizzare la richiesta dell'utente per capire quali servizi sono importanti per lui e assegnare un peso a ciascuna delle 6 categorie POI disponibili.

Categorie POI disponibili:
- sanita (Ospedali, farmacie, cliniche)
- mobilita (Metro, bus, stazioni, parcheggi)
- verde (Parchi, giardini, aree verdi)
- sport (Palestre, piscine, centri sportivi)
- commerciale (Supermercati, negozi, centri commerciali)
- educazione (Scuole, università, biblioteche)

Regole di assegnazione pesi (0.0 - 1.0):
- Se l'utente menziona esplicitamente una categoria come importante (es. "vicino alla metro"), assegna un peso alto (0.7 - 1.0).
- Se l'utente menziona una categoria come non importante (es. "non mi interessano le scuole"), assegna peso 0.0.
- Se l'utente non menziona una categoria, assegna un peso di default basso (0.1 - 0.3) a seconda del contesto generale (es. per una famiglia, educazione e verde sono implicitamente importanti).
- La somma dei pesi NON deve necessariamente fare 1.0.

Output richiesto:
Restituisci SOLO un oggetto JSON con la seguente struttura:
{{
    "poi_weights": {{
        "sanita": <float>,
        "mobilita": <float>,
        "verde": <float>,
        "sport": <float>,
        "commerciale": <float>,
        "educazione": <float>
    }},
    "constraints": {{
        "must_have": ["<categoria>", ...],  // Categorie che DEVONO avere uno score alto (>3)
        "must_not_have": ["<categoria>", ...] // Categorie da evitare (raro)
    }}
}}"""

DEFAULT_USER = """Richiesta utente: "{query}" """


class PoiAgent(BaseAgent):
    name = "poi-agent"

    def __init__(self, model_name: str = None):
        resolved_model = model_name or AGENT_MODELS.get("poi_agent") or AGENT_MODELS.get("default")
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("poi_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("poi_agent", DEFAULT_USER)

        # Create ChatPromptTemplate with system/user separation
        from langchain_core.prompts import ChatPromptTemplate

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

        try:
            response_text = self.chain.invoke(prompt_inputs)

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                poi_weights = data.get("poi_weights", {})
                constraints = data.get("constraints", {})
            else:
                # Fallback defaults if JSON parsing fails
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

        except Exception as e:
            print(f"Errore PoiAgent: {e}")
            return PoiAgentResult(raw_text=str(e), poi_weights={}, constraints={}, prompt=None)
