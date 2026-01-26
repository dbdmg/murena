import json
import os
from typing import List, Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.core.constants import SCORE_LEGEND
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import (
    AgentContext,
    ChatAction,
    MapAssistantResponse,
    PromptRecord,
)
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage


DEFAULT_SYSTEM = """Sei un Assistente Intelligente per una mappa interattiva di immobili del Ministero (MEF).
Hai accesso al contesto della ricerca corrente e ai risultati visibili.

OBIETTIVO:
Rispondere alle domande dell'utente O eseguire azioni sulla mappa (filtri, reset).

ISTRUZIONI PER LE AZIONI:
1. Se l'utente chiede di **filtrare** (es. "Togli gli uffici", "Solo classe A"), genera un'azione "filter".
   - Campi supportati: 'tipologia', 'classe_energetica', 'score'.
   - Valori Tipologia: 'Ufficio', 'Alloggio', 'Posto Auto', 'Magazzino', etc. (Case-insensitive)
   - Valori Classe: 'A1', 'A2', 'B', 'C', 'D', 'E', 'F', 'G'.
2. Se l'utente chiede di **resettare** o mostrare tutto, genera un'azione "reset".
3. Se l'utente chiede cose che richiedono una **nuova ricerca** (es. "Cerca a Milano" se siamo a Roma), genera un'azione "rerun".
4. Se è una semplice domanda (es. "Qual è il migliore?", "Perché questo edificio?", "Elencami gli uffici"), azione "none" e rispondi nel testo usando i DATI DI CONTESTO e la VALUTAZIONE AI.

{score_legend}

RISPOSTA:
Devi restituire un oggetto JSON formattato secondo lo schema richiesto.
{format_instructions}"""

DEFAULT_USER = """CONTESTO DATASET (Metadata):
{dataset_metadata}

CONTESTO DATI (Primi 15 risultati visibili):
{context_data}

VALUTAZIONE AI (Se disponibile):
{evaluation_context}

CONTESTO UTENTE:
Query Iniziale: {user_query}
Numero Risultati Totali: {results_count}
Filtri Attivi: {current_filters}

ULTIME INTERAZIONI:
{chat_history}

DOMANDA UTENTE:
{message}"""


class MapAssistantAgent(BaseAgent):
    name = "map-assistant-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("map_assistant")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Define output parser
        self.parser = PydanticOutputParser(pydantic_object=MapAssistantResponse)

        # Load Metadata
        self.metadata_str = self._load_metadata()

        # Load system and user prompts separately
        format_instructions = self.parser.get_format_instructions()
        self.system_prompt = get_system_prompt("map_assistant", DEFAULT_SYSTEM).format(
            format_instructions=format_instructions, score_legend=SCORE_LEGEND
        )
        self.user_template = get_user_template("map_assistant", DEFAULT_USER)

        # Create ChatPromptTemplate with system/user separation
        from langchain_core.prompts import ChatPromptTemplate

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                ("user", self.user_template),
            ]
        )

        # Chain
        if hasattr(self.llm, "with_structured_output"):
            self.chain = self.prompt | self.llm.with_structured_output(
                MapAssistantResponse
            )
        else:
            self.chain = self.prompt | self.llm | self.parser

    def _load_metadata(self) -> str:
        """Loads and formats db_metadata.json into a string."""
        try:
            # Assuming app/data/db_metadata.json exists relative to valid path
            # Need to find absolute path or relative to project root.
            # BaseAgent doesn't inherently give root, so we infer or use hardcoded relative for now.
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            meta_path = os.path.join(base_dir, "data", "db_metadata.json")

            if not os.path.exists(meta_path):
                return "Metadata non disponibile."

            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Format nicely
            lines = []
            for field, info in data.items():
                desc = info.get("description", "")
                vals = info.get("values", [])
                if vals and len(vals) > 10:
                    vals_str = ", ".join(vals[:10]) + "..."
                elif vals:
                    vals_str = ", ".join(vals)
                else:
                    # check for min/max
                    low = info.get("min")
                    high = info.get("max")
                    if low is not None and high is not None:
                        vals_str = f"Range: {low} - {high}"
                    else:
                        vals_str = "N/D"

                lines.append(f"- {field}: {desc} (Valori: {vals_str})")

            return "\n".join(lines)
        except Exception:
            return "Errore caricamento metadata."

    @log_llm_usage
    def run(
        self,
        *,
        message: str,
        context: AgentContext,
        current_filters: dict,
        chat_history: List[str],
    ) -> MapAssistantResponse:

        # Prepare inputs
        results_count = (
            len(context.filtered_dataset_preview)
            if context.filtered_dataset_preview
            else "N/D"
        )
        history_str = (
            "\n".join(chat_history[-5:])
            if chat_history
            else "Nessuna interazione precedente."
        )

        # Build Context Data (RAG Lite)
        context_items = []
        if context.filtered_dataset_preview:
            for item in context.filtered_dataset_preview[:15]:  # Limit to top 15
                # Extract key info
                tipo = item.get("tipologia_bene_immobile", "N/D")
                indirizzo = item.get("indirizzo", "N/D")
                citta = item.get("comune", "N/D")
                score = item.get("score", "N/D")
                mq = item.get("superficie_di_riferimento_mq", "N/D")
                classe = item.get("classe_energetica_ape", "N/D")
                denom = item.get("denominazione", "Immobile")
                oid = item.get("id", "N/D")

                line = (
                    f"- [ID {oid}] {denom} ({tipo}): {indirizzo}, {citta}. "
                    f"Mq: {mq}, Classe: {classe}, Score: {score}"
                )
                context_items.append(line)

        context_data_str = (
            "\n".join(context_items)
            if context_items
            else "Nessun dato visibile specifico."
        )

        # Build Evaluation Context
        eval_items = []
        if context.evaluation_results:
            for res in context.evaluation_results:
                pros = ", ".join(res.pros) if res.pros else "N/D"
                cons = ", ".join(res.cons) if res.cons else "N/D"
                line = (
                    f"- ID {res.id}: Score AI {res.score}/100. Motivo: {res.evaluation_text} "
                    f"[Pro: {pros}] [Contro: {cons}]"
                )
                eval_items.append(line)

        eval_context_str = (
            "\n".join(eval_items)
            if eval_items
            else "Nessuna valutazione AI disponibile al momento."
        )

        prompt_inputs = {
            "user_query": context.user_query,
            "results_count": str(results_count),
            "current_filters": json.dumps(current_filters, ensure_ascii=False),
            "chat_history": history_str,
            "message": message,
            "context_data": context_data_str,
            "dataset_metadata": self.metadata_str,
            "evaluation_context": eval_context_str,
        }

        try:
            result = invoke_with_langfuse(self.chain, prompt_inputs)

            # Formatting fallback if result is not Pydantic (e.g. raw dict from some LLMs)
            if not isinstance(result, MapAssistantResponse):
                # Try to parse if it's a dict
                result = MapAssistantResponse(**result)

            raw_text = result.response_text

        except Exception as e:
            # Fallback error response
            raw_text = f"Mi dispiace, si è verificato un errore nell'elaborazione: {e}"
            result = MapAssistantResponse(
                response_text=raw_text,
                action=ChatAction(action_type="none", reasoning="Error recovery"),
                prompt=None,
            )

        # Attach prompt metadata
        # Ensure message is a string for PromptRecord
        safe_message = message if message is not None else "N/D"
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        result.prompt = PromptRecord(
            system=self.system_prompt.strip(),
            user=user_text,
            full_text=full_text,
        )

        return result
