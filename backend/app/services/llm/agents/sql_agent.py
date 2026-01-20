from typing import Any, Optional

from langchain_core.prompts import PromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, SQLAgentResult
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage

DEFAULT_SYSTEM = """Sei un esperto di SQL. Il tuo compito è generare una query per DuckDB per estrarre informazioni da un database.

Requisiti:
- La tabella principale si chiama `IMMOBILI`. Usa SEMPRE questo nome.
- Usa i nomi di colonna esattamente come nello schema fornito.
- Se la richiesta include un luogo, usa `haversine_km(latitudine, longitudine, {lat}, {lon})` per calcolare la distanza.
- APPLICA SEMPRE un filtro di distanza se c'è un luogo (es. `WHERE haversine_km(...) < 3`). Se l'utente non specifica il raggio, usa 3km come default.
- Ordina i risultati per distanza crescente.
- Se non è presente un luogo, non usare filtri di distanza.
- Usa WHERE con condizioni ben definite.
- Usa GROUP BY, ORDER BY o aggregazioni solo se necessario.
- NON usare MAI la clausola LIMIT. Vogliamo tutti i risultati pertinenti.
- Termina SEMPRE la query con un punto e virgola (;).
- NON includere commenti, spiegazioni o Markdown nel blocco SQL.

Restituisci ESCLUSIVAMENTE la query SQL."""

DEFAULT_USER = """Schema:
{scheme}

Query Utente: "{query}"
Località (opzionale): {location_str}"""

DEFAULT_RETRY_SYSTEM = """Sei un esperto di SQL e il tuo compito è correggere una query che non ha prodotto risultati o ha generato un errore.

Requisiti:
- La tabella principale si chiama `IMMOBILI`.
- Se c'è un errore di sintassi o di colonna, CORREGGILO basandoti sullo schema fornito.
- Se l'errore è "Nessun risultato" (query vuota ma corretta), prova ad allentare i vincoli:
    1. Rilassa i Criteri Qualitativi.
    2. Rimuovi Criteri Secondari.
    3. Aumenta il raggio di distanza (es. da 3km a 5km o 10km) se i criteri geografici sono troppo stringenti.

Restituisci ESCLUSIVAMENTE la nuova query SQL corretta."""

DEFAULT_RETRY_USER = """Errore Riscontrato:
{error_msg}

Query Utente Originale: "{query}"
Query Fallita: "{failed_query}"
Località (opzionale): {location_str}

Schema:
{scheme}"""


def _clean_sql(text: str) -> str:
    """Pulisce la stringa SQL da markdown e commenti."""
    text = text.strip()
    if text.startswith("```sql"):
        text = text[6:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


class SQLAgent(BaseAgent):
    name = "sql-agent"

    def __init__(self, model_name: str = None):
        resolved_model = model_name or AGENT_MODELS.get("sql_agent") or AGENT_MODELS.get("default")
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("sql_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("sql_agent", DEFAULT_USER)

        # Load retry prompts separately
        self.retry_system = get_system_prompt("sql_agent", DEFAULT_RETRY_SYSTEM, key="retry_system")
        self.retry_user = get_user_template("sql_agent", DEFAULT_RETRY_USER, key="retry_user")

    def _invoke(
        self, system: str, user_template: str, variables: dict, is_retry: bool = False
    ) -> tuple[str, PromptRecord]:
        user_text = user_template.format(**variables).strip()
        full_text = f"[SYSTEM]\n{system}\n\n[USER]\n{user_text}"

        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                ("user", user_template),
            ]
        )
        chain = prompt | self.llm
        response = chain.invoke(variables)
        raw_text = getattr(response, "content", str(response))

        prompt_record = PromptRecord(
            system=system.strip(),
            user=user_text,
            full_text=full_text,
        )
        return raw_text, prompt_record

    @log_llm_usage
    def run(
        self,
        *,
        query: str,
        scheme: str,
        location: Optional[Any] = None,
        failed_query: Optional[str] = None,
        error_msg: Optional[str] = None,
        db_metadata: str = "",
    ) -> SQLAgentResult:
        location_str = ""
        lat = 0.0
        lon = 0.0

        if location:
            # Gestione location object o stringa
            if hasattr(location, "lat") and hasattr(location, "lon"):
                lat = location.lat
                lon = location.lon
                location_str = f"Lat: {lat}, Lon: {lon}"
            elif isinstance(location, dict):
                lat = location.get("lat", 0.0)
                lon = location.get("lon", 0.0)
                location_str = f"Lat: {lat}, Lon: {lon}"
            else:
                location_str = str(location)

        # Se abbiamo coordinate valide, passiamole al prompt per interpolazione diretta se necessario
        # Nota: Il prompt template sopra usa {lat} e {lon} solo se location è presente.
        # Per semplicità, passiamo location_str che contiene tutto.
        # Ma per haversine servono i numeri.

        # Modifica dinamica del prompt per inserire lat/lon se disponibili
        if lat and lon:
            location_str = f"Latitudine {lat}, Longitudine {lon}"

        is_retry = bool(failed_query)
        system = self.retry_system if is_retry else self.system_prompt
        user_template = self.retry_user if is_retry else self.user_template

        variables = {
            "query": query,
            "scheme": scheme,
            "failed_query": failed_query or "",
            "location_str": location_str,
            "lat": lat,
            "lon": lon,
            "error_msg": error_msg or "Nessun risultato trovato (query vuota).",
            "db_metadata": db_metadata,
        }

        raw_text, prompt_record = self._invoke(system, user_template, variables, is_retry)
        sql = _clean_sql(raw_text)

        # Fix common SQL syntax errors from LLM
        # 1. Fix single quote escaping: replace \' with ''
        sql = sql.replace("\\'", "''")

        return SQLAgentResult(
            sql_query=sql,
            explanation=None,
            raw_text=raw_text,
            prompt=prompt_record,
        )
