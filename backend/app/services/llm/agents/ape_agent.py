from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import ApeAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage

DEFAULT_SYSTEM = """Sei un esperto di efficienza energetica e certificazioni APE (Attestato di Prestazione Energetica).
Hai accesso a un dataset contenente i dati APE degli immobili, arricchito con punteggi di qualità (1-5).

Legenda Punteggi (1-5):
- ape_score_classe: 5 (A1-A4), 3 (B-E), 1 (F-G)
- ape_score_impianto: 5 (Pompa di calore/Teleriscaldamento), 3 (Condensazione/Biomassa), 1 (Altro)
- ape_score_involucro: 5 (Ottimo), 3 (Medio), 1 (Scarso)
- ape_score_rinnovabili: 5 (Sì), 1 (No)
- ape_score_total: Media dei punteggi

Il tuo compito è:
1. Analizzare la richiesta dell'utente.
2. Valutare se è utile applicare filtri energetici per favorire gli immobili più efficienti.
3. Fornire una risposta discorsiva spiegando la strategia energetica.
4. Elencare eventuali filtri da applicare sui campi `ape_score_*` o altri campi APE.
   Formato filtri: "FILTRO: <campo> <operatore> <valore>" (es. "FILTRO: ape_score_total >= 4")

Rispondi in modo discorsivo. Se suggerisci filtri, elencali alla fine su righe separate con il prefisso "FILTRO:"."""

DEFAULT_USER = """Schema del dataset APE (inclusi punteggi):
{columns}

Richiesta utente: "{query}" """


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
    def run(self, query: str, columns: list[str] = None) -> ApeAgentResult:
        if not columns:
            return ApeAgentResult(
                raw_text="Dati APE non disponibili.",
                answer="Non sono disponibili dati APE per questa analisi.",
                relevant_ape_ids=[],
                suggested_filters=[],
                prompt=None,
            )

        columns_desc = ", ".join(columns)
        prompt_inputs = {"query": query, "columns": columns_desc}

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        try:
            response_text = self.chain.invoke(prompt_inputs)

            # Parse filters
            filters = []
            lines = response_text.split("\n")
            clean_lines = []
            for line in lines:
                if line.strip().startswith("FILTRO:"):
                    filters.append(line.strip().replace("FILTRO:", "").strip())
                else:
                    clean_lines.append(line)

            answer_text = "\n".join(clean_lines).strip()

            return ApeAgentResult(
                raw_text=response_text,
                answer=answer_text,
                relevant_ape_ids=[],
                suggested_filters=filters,
                prompt=PromptRecord(
                    system=self.system_prompt.strip(),
                    user=user_text,
                    full_text=full_text,
                ),
            )

        except Exception as e:
            print(f"Errore ApeAgent: {e}")
            return ApeAgentResult(
                raw_text=str(e),
                answer="Si è verificato un errore nell'analisi dei dati APE.",
                relevant_ape_ids=[],
                suggested_filters=[],
                prompt=None,
            )
