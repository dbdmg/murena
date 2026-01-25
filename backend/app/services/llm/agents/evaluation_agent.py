import json
from typing import List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import (
    EvaluationAgentResponse,
    EvaluationResult,
    PromptRecord,
)
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage


class EvaluationList(BaseModel):
    evaluations: List[EvaluationResult] = Field(
        description="Lista delle valutazioni degli immobili"
    )


DEFAULT_SYSTEM = """Sei un Esperto Senior di Valorizzazione Immobiliare e Rigenerazione Urbana per il Ministero dell'Economia e delle Finanze (MEF).
Il tuo obiettivo è analizzare un portafoglio di immobili pubblici per identificare le migliori opportunità di valorizzazione.

Protocollo di Valutazione:
1. Analisi del Potenziale: Non limitarti allo stato attuale. Valuta la trasformabilità dell'immobile.
2. Fattori Critici:
   - Posizione (zona_omi, punteggi POI: sanita, mobilita, verde, sport, commerciale, educazione)
   - Dimensione (superficie_di_riferimento_mq)
   - Sostenibilità Energetica (classe_energetica_ape, ape_score_* dove 1=scarso, 5=ottimo)
   - Accessibilità (tempo_minuti, distanza_km se disponibili)
3. Scoring (0-100):
   - 90-100 (Top Prospect): Immobile ideale, nessun ostacolo significativo.
   - 75-89 (High Potential): Ottimo candidato con piccole criticità.
   - 60-74 (Medium Potential): Adatto ma con sfide da gestire.
   - <60 (Low Potential): Scarsa vocazione per l'uso richiesto.

I dati degli immobili sono forniti in formato JSON. Ogni oggetto rappresenta un immobile con i suoi attributi.

{format_instructions}"""

DEFAULT_USER = """Richiesta Utente (Obiettivo Strategico):
{query}

Scenario di Valorizzazione (Use Case):
{use_case}

Dati degli Immobili Candidati (JSON):
{estates_data}"""


BROKER_SYSTEM = """Sei un Senior Real Estate Broker e Consulente Strategico per il Ministero.
Il tuo compito è scrivere una "Executive Summary" COMPARATIVA per il decisore finale.

Istruzioni:
1. Sintesi Diretta: Inizia con una frase forte che identifica la migliore opportunità.
2. Comparazione: Confronta i top 3 candidati. Evidenzia pro e contro relativi.
3. Raccomandazione: Dai un consiglio finale basato sul miglior compromesso.
4. Tono: Professionale, sintetico, autorevole. Massimo 10-12 righe."""

BROKER_USER = """Richiesta Utente:
{query}

Top Candidati Selezionati:
{candidates_data}"""


class EvaluationAgent(BaseAgent):
    name = "evaluation-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("evaluation_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("evaluation_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("evaluation_agent", DEFAULT_USER)

        self.parser = PydanticOutputParser(pydantic_object=EvaluationList)

        # Inject format_instructions into system prompt
        system_with_format = self.system_prompt.replace(
            "{format_instructions}", self.parser.get_format_instructions()
        )

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_with_format),
                ("user", self.user_template),
            ]
        )

        # Broker prompt (system/user separated)
        broker_system = get_system_prompt("broker_agent", BROKER_SYSTEM)
        broker_user = get_user_template("broker_agent", BROKER_USER)
        self.broker_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", broker_system),
                ("user", broker_user),
            ]
        )

        # Store templates for PromptRecord
        self._system_with_format = system_with_format
        self._broker_system = broker_system
        self._broker_user = broker_user

        # Se il modello supporta structured output nativo (es. Gemini/OpenAI), usiamolo
        if hasattr(self.llm, "with_structured_output"):
            self.chain = self.prompt | self.llm.with_structured_output(EvaluationList)
        else:
            self.chain = self.prompt | self.llm | self.parser

        # Broker chain (pure text)
        self.broker_chain = self.broker_prompt | self.llm

    @log_llm_usage
    def run(
        self, *, use_case: str, estates_data: str, query: str
    ) -> EvaluationAgentResponse:
        prompt_inputs = {
            "use_case": use_case,
            "estates_data": estates_data,
            "query": query,
        }

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self._system_with_format}\n\n[USER]\n{user_text}"

        try:
            result = self.chain.invoke(prompt_inputs)

            # Gestione differenziata in base al tipo di output (oggetto Pydantic o altro)
            if isinstance(result, EvaluationList):
                results = result.evaluations
                raw_text = json.dumps([r.model_dump() for r in results], indent=2)
            else:
                # Fallback se la catena restituisce qualcos'altro
                results = []
                raw_text = str(result)

        except Exception as e:
            print(f"Errore nel parsing della valutazione: {e}")
            results = []
            raw_text = f"Error: {str(e)}"

        prompt_record = PromptRecord(
            system=self._system_with_format.strip(),
            user=user_text,
            full_text=full_text,
        )

        return EvaluationAgentResponse(
            prompt=prompt_record, raw_text=raw_text, results=results
        )

    @log_llm_usage
    def run_synthesis(self, *, query: str, candidates_data: str) -> str:
        """Genera una sintesi comparativa (Broker Review)."""
        try:
            res = self.broker_chain.invoke(
                {"query": query, "candidates_data": candidates_data}
            )
            # Handle standard langchain response objects (content vs str)
            return res.content if hasattr(res, "content") else str(res)
        except Exception as e:
            return f"Impossibile generare sintesi: {e}"
