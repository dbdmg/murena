import json
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, TypologyAgentResult
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage

DEFAULT_SYSTEM = """Sei un esperto immobiliare. Il tuo compito è identificare quali tipologie di immobili sono pertinenti alla richiesta dell'utente, selezionandole da una lista predefinita.

Istruzioni:
1. Analizza la richiesta dell'utente.
2. Seleziona dalla lista le tipologie che soddisfano la richiesta.
3. Se la richiesta è generica o non specifica una tipologia, seleziona tutte le tipologie che potrebbero essere rilevanti o lascia la lista vuota per indicare "nessun filtro".
4. Sii inclusivo: se l'utente cerca "uffici", includi anche tipologie simili se presenti (es. "Uffici pubblici", "Uffici privati").
5. Restituisci ESCLUSIVAMENTE un JSON con la seguente struttura:
{{
    "typologies": ["<tipologia 1>", "<tipologia 2>", ...]
}}

Esempi:
Input: "Cerco una scuola"
Output: {{"typologies": ["SCUOLA", "ISTITUTO SCOLASTICO"]}}

Input: "Immobili in centro"
Output: {{"typologies": []}}"""

DEFAULT_USER = """Lista delle tipologie disponibili:
{available_typologies}

Richiesta utente: "{query}"

Risposta JSON:"""


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text)
    except Exception:
        return {"typologies": []}


class TypologyAgent(BaseAgent):
    name = "typology-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("typology_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("typology_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("typology_agent", DEFAULT_USER)

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
        fallback_value=TypologyAgentResult(raw_text="Error", typologies=[], prompt=None)
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

        try:
            response_text = self.chain.invoke(prompt_inputs)

            parsed = _extract_json(response_text)
            typologies = parsed.get("typologies", [])

            return TypologyAgentResult(
                raw_text=response_text,
                typologies=typologies,
                prompt=PromptRecord(
                    system=self.system_prompt.strip(),
                    user=user_text,
                    full_text=full_text,
                ),
            )

        except Exception as e:
            print(f"Errore TypologyAgent: {e}")
            return TypologyAgentResult(raw_text=str(e), typologies=[], prompt=None)
