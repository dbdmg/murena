import json
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, UseCaseResult
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage

DEFAULT_SYSTEM = """Sei un esperto in analisi di requisiti per immobili pubblici.
Il tuo compito è generare un use case strutturato basandoti sulla query dell'utente.

Restituisci ESCLUSIVAMENTE un JSON con la seguente struttura:
{{
    "description": "<descrizione dettagliata dello use case>",
    "target_audience": "<target audience identificata>",
    "key_metrics": ["<metrica 1>", "<metrica 2>", ...]
}}"""

DEFAULT_USER = """Query Utente: "{query}"
Schema Database (per contesto): {db_schema}"""


def _extract_json(text: str) -> Any:
    """Prova ad estrarre un JSON dalla risposta del modello."""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

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


class UseCaseAgent(BaseAgent):
    name = "use-case-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("use_case_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("use_case_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("use_case_agent", DEFAULT_USER)

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
    def run(self, *, query: str, db_schema: str) -> UseCaseResult:
        prompt_inputs = {"query": query, "db_schema": db_schema}

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        raw = self.chain.invoke(prompt_inputs)
        data = _extract_json(raw)

        if not data:
            # Fallback se il JSON non è valido
            return UseCaseResult(
                raw_text=raw,
                description="Impossibile generare use case strutturato.",
                target_audience="Generico",
                key_metrics=[],
                prompt=PromptRecord(
                    system=self.system_prompt.strip(),
                    user=user_text,
                    full_text=full_text,
                ),
            )

        prompt_record = PromptRecord(
            system=self.system_prompt.strip(),
            user=user_text,
            full_text=full_text,
        )

        return UseCaseResult(
            raw_text=raw,
            description=data.get("description", ""),
            target_audience=data.get("target_audience", ""),
            key_metrics=data.get("key_metrics", []),
            prompt=prompt_record,
        )
