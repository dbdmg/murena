from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import ApeAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage
from app.utils.json_parser import safe_extract_json

DEFAULT_SYSTEM = """Sei un esperto di efficienza energetica e certificazioni APE (Attestato di Prestazione Energetica).
Hai accesso alle statistiche del dataset immobiliare e alla legenda dei punteggi.

{score_legend}

STATISTICHE DATASET:
{statistics}

Il tuo compito è:
1. Analizzare la richiesta dell'utente.
2. Valutare se è utile applicare filtri energetici per favorire gli immobili più efficienti.
3. Fornire una risposta discorsiva spiegando la strategia energetica.
4. Suggerire filtri SPECIFICI sui campi `ape_score_*` o altri campi APE se necessario.
   NOTA: Usa i filtri solo se l'utente richiede esplicitamente efficienza o risparmio.
   
Restituisci ESCLUSIVAMENTE un JSON con la seguente struttura:
{{
    "answer": "<spiegazione della strategia>",
    "suggested_filters": [
        "ape_score_total >= 4",
        "classe_energetica_ape IN ('A1', 'A2', 'A3', 'A4')"
    ]
}}

Se non ci sono filtri da suggerire, lascia "suggested_filters" vuoto array [].
"""

DEFAULT_USER = """Richiesta utente: "{query}" """


class ApeAgent(BaseAgent):
    name = "ape-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("ape_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("ape_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("ape_agent", DEFAULT_USER)

        # Create ChatPromptTemplate with system/user separation
        # Note: We construct the chain dynamically in run() because system prompt changes with stats
        from langchain_core.prompts import ChatPromptTemplate

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", self.user_template),
            ]
        )
        self.parser = StrOutputParser()
        self.chain = self.prompt_template | self.llm | self.parser

    @log_llm_usage
    def run(
        self,
        query: str,
        columns: list[str] = None,
        statistics: dict = None,
        score_legend: str = "",
    ) -> ApeAgentResult:
        if not statistics and not columns:
            # Fallback legacy behavior or graceful exit
            return ApeAgentResult(
                raw_text="Dati APE non disponibili.",
                answer="Non sono disponibili dati APE per questa analisi.",
                relevant_ape_ids=[],
                suggested_filters=[],
                prompt=None,
            )

        # Format statistics string
        stats_str = "Nessuna statistica disponibile."
        if statistics:
            import json

            stats_str = json.dumps(statistics, indent=2, ensure_ascii=False)
        elif columns:
            stats_str = "Colonne disponibili: " + ", ".join(columns)

        # Prepare system prompt content
        # We manually inject variables into the system string before passing to LLM
        # This is because get_system_prompt returns a string that expects formatting
        system_content = self.system_prompt.format(
            statistics=stats_str,
            score_legend=score_legend or "Nessuna legenda disponibile.",
        )

        prompt_inputs = {"system_content": system_content, "query": query}

        # User text for record keeping
        user_text = self.user_template.format(query=query).strip()
        full_text = f"[SYSTEM]\n{system_content}\n\n[USER]\n{user_text}"

        try:
            response_text = self.chain.invoke(prompt_inputs)

            # Parse JSON
            data = safe_extract_json(response_text)

            answer = ""
            suggested_filters = []

            if data and isinstance(data, dict):
                answer = data.get("answer", "")
                suggested_filters = data.get("suggested_filters", [])

                # Ensure suggested_filters is a list of strings
                if isinstance(suggested_filters, list):
                    suggested_filters = [
                        str(f)
                        for f in suggested_filters
                        if isinstance(f, (str, int, float))
                    ]
                else:
                    suggested_filters = []
            else:
                # Fallback text parsing if JSON fails completely
                answer = response_text
                # Try simple regex for filters if they appear in text (legacy support)
                import re

                legacy_filters = re.findall(r"FILTRO:\s*(.*)", response_text)
                if legacy_filters:
                    suggested_filters.extend(legacy_filters)

            return ApeAgentResult(
                raw_text=response_text,
                answer=answer,
                relevant_ape_ids=[],
                suggested_filters=suggested_filters,
                prompt=PromptRecord(
                    system=system_content,
                    user=user_text,
                    full_text=full_text,
                ),
            )

        except Exception as e:
            print(f"Errore ApeAgent: {e}")
            return ApeAgentResult(
                raw_text=str(e),
                answer="Si è verificato un errore nell'analisi energetica.",
                relevant_ape_ids=[],
                suggested_filters=[],
                prompt=None,
            )
