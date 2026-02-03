from typing import List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, TypologyAgentResult
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json


# Modello per la risposta strutturata
class TypologyResponse(BaseModel):
    typologies: List[str] = Field(
        default_factory=list, description="Lista delle tipologie selezionate"
    )


DEFAULT_SYSTEM = """# RUOLO
Sei il Typology Agent per l'applicazione Real Estate AI.
Il tuo compito è identificare quali tipologie di immobili sono pertinenti alla richiesta dell'utente.

# REGOLE
1. Analizza la richiesta e seleziona le tipologie rilevanti dalla lista fornita.
2. Se la richiesta è generica, lascia la lista vuota (nessun filtro).
3. Sii inclusivo: "uffici" include "Ufficio pubblico", "Ufficio privato", ecc.
4. Se non trovi corrispondenze esatte, usa tipologie semanticamente simili.

# OUTPUT
Restituisci ESCLUSIVAMENTE un JSON valido:
{
  "typologies": ["<tipologia 1>", "<tipologia 2>"]
}

# ESEMPI
Query: "Cerco una scuola"
Tipologie: ["SCUOLA", "ISTITUTO SCOLASTICO", "ASILO"]
Output: {{"typologies": ["SCUOLA", "ISTITUTO SCOLASTICO"]}}

Query: "Immobili in centro"
Output: {{"typologies": []}}
"""

DEFAULT_USER = """Lista delle tipologie disponibili:
{available_typologies}

Richiesta utente: "{query}"

Risposta JSON:"""


class TypologyAgent(BaseAgent):
    name = "typology-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("typology_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("typology_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("typology_agent", DEFAULT_USER)

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
        fallback_value=TypologyAgentResult(raw_text="Error", prompt=None)
    )
    def run(self, query: str, available_typologies: str) -> TypologyAgentResult:
        # If available_typologies is a list, join it. If it's already a string (from graph_agent), use it.
        if isinstance(available_typologies, list):
            typologies_str = ", ".join([f'"{t}"' for t in available_typologies])
        else:
            typologies_str = available_typologies

        prompt_inputs = {"query": query, "available_typologies": typologies_str}

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        response_text = invoke_with_langfuse(self.chain, prompt_inputs)

        return TypologyAgentResult(
            raw_text=response_text,
            prompt=PromptRecord(
                system=self.system_prompt.strip(),
                user=user_text,
                full_text=full_text,
            ),
        )
