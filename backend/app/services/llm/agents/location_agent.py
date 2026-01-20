import json
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import LocationAgentResult, Place, PromptRecord
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage

DEFAULT_SYSTEM = """Sei un esperto nell'estrazione di luoghi (POI o aree) da una singola frase in italiano.

Vincoli e regole:
- Limita l'interpretazione all'area di Torino e provincia.
- Se presente, restituisci i luoghi nella forma strutturata JSON.
- Se non è presente alcun riferimento geografico, restituisci un array vuoto.
- Non aggiungere commenti o testo non-JSON.

Restituisci ESCLUSIVAMENTE un JSON con la seguente struttura:
{{
    "places": [
        {{"name": "<nome del luogo>", "city": "<città o null>"}},
        ...
    ]
}}

Esempi validi:
Input: "mostrami gli edifici abbandonati vicino al centro storico di Torino"
Output: {{"places": [{{"name": "Centro Storico", "city": "Torino"}}]}}

Input: "trovami edifici disponibili per eventi"
Output: {{"places": []}}"""

DEFAULT_USER = """Frase: "{query}" """


def _extract_json(text: str) -> Any:
    """Prova ad estrarre un JSON dalla risposta del modello.
    Accetta sia un JSON puro che un blocco con testo circostante.
    """
    text = text.strip()
    # Tenta parsing diretto
    try:
        return json.loads(text)
    except Exception:
        pass

    # Cerca il primo blocco {...} o [...] plausibile
    start_positions = [text.find("{"), text.find("[")]
    start_positions = [p for p in start_positions if p != -1]
    if not start_positions:
        return None
    start = min(start_positions)
    for end in range(len(text), start, -1):
        fragment = text[start:end]
        try:
            return json.loads(fragment)
        except Exception:
            continue
    return None


class LocationAgent(BaseAgent):
    name = "location-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("location_agent") or AGENT_MODELS.get("default")
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
        fallback_value=LocationAgentResult(raw_text="Error", places=[], prompt=None)
    )
    def run(self, *, query: str) -> LocationAgentResult:
        prompt_inputs = {"query": query}

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        raw = self.chain.invoke(prompt_inputs)

        data = _extract_json(raw) or {"places": []}
        places = []
        if isinstance(data, dict) and isinstance(data.get("places"), list):
            for item in data["places"]:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                city = item.get("city")
                if isinstance(name, str) and name.strip():
                    places.append(Place(name=name.strip(), city=(city or None)))

        prompt_record = PromptRecord(
            system=self.system_prompt.strip(),
            user=user_text,
            full_text=full_text,
        )

        return LocationAgentResult(raw_text=raw, places=places, prompt=prompt_record)
