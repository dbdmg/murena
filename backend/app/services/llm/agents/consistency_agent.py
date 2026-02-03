from typing import List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import ConsistencyAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json


# Modello per la risposta strutturata
class ConsistencyResponse(BaseModel):
    requirements: List[str] = Field(
        default_factory=list, description="Lista dei requisiti consolidati"
    )


DEFAULT_SYSTEM = """# RUOLO
Sei il Consistency Agent per l'applicazione Real Estate AI.
Il tuo compito è analizzare i requisiti estratti da diversi agenti specializzati e produrre una lista consolidata e "pulita" di requisiti, priva di contraddizioni.

# INPUT
Riceverai i risultati dei seguenti agenti:
- Typology Agent: Tipologie di immobili suggerite.
- Location Agent: Luoghi e aree di interesse.
- Normative Agent: Vincoli normativi e legali.
- APE Agent: Requisiti di efficienza energetica.

# REGOLE DI CONSOLIDAMENTO
1. Identifica e rimuovi eventuali contraddizioni (es. un agente chiede classe A e un altro chiede "massima economia" che potrebbe implicare classi basse - risolvi dando priorità alla richiesta esplicita dell'utente).
2. Unifica i requisiti simili.
3. Se un requisito normativo è obbligatorio, deve avere la precedenza.
4. Mantieni i requisiti territoriali (location) chiari.
5. Il risultato sarà usato per generare una query SQL: usa un linguaggio tecnico ma chiaro.
6. Non aggiungere requisiti non presenti negli input, limitati a pulire e consolidare quelli esistenti.

# OUTPUT
Restituisci ESCLUSIVAMENTE un JSON valido con questa struttura:
{{
  "requirements": ["requisito 1", "requisito 2", ...]
}}
"""

DEFAULT_USER = """Query originale dell'utente: "{query}"

Requisiti individuati dagli agenti:
- Tipologie: {typologies}
- Luoghi: {locations}
- Normative: {normative_info}
- Efficienza Energetica (APE): {ape_info}
"""


class ConsistencyAgent(BaseAgent):
    name = "consistency-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("consistency_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        self.system_prompt = get_system_prompt("consistency_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("consistency_agent", DEFAULT_USER)

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
        fallback_value=ConsistencyAgentResult(
            raw_text="{}", prompt=None
        )
    )
    def run(
        self,
        query: str,
        typologies: List[str],
        locations: List[str],
        normative_info: str,
        ape_info: str,
    ) -> ConsistencyAgentResult:
        prompt_inputs = {
            "query": query,
            "typologies": ", ".join(typologies) if typologies else "Nessuna specifica",
            "locations": ", ".join(locations) if locations else "Nessuna specifica",
            "normative_info": normative_info or "Nessuna specifica",
            "ape_info": ape_info or "Nessuna specifica",
        }

        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        response_text = invoke_with_langfuse(self.chain, prompt_inputs)

        return ConsistencyAgentResult(
            raw_text=response_text,
            prompt=PromptRecord(
                system=self.system_prompt.strip(),
                user=user_text,
                full_text=full_text,
            ),
        )
