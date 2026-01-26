from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, SQLAgentResult
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
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
- NON usare MAI la clausola LIMIT. Vogliamo TUTTI i risultati pertinenti per il ranking successivo.
- Se ti senti costretto a mettere un limite, usa LIMIT 10000.
- Termina SEMPRE la query con un punto e virgola (;).
- NON includere commenti, spiegazioni o Markdown nel blocco SQL.

REGOLE CRITICHE DI FILTRAGGIO:
- NON usare MAI le colonne `ape_score_*` (es. ape_score_total) nella clausola WHERE.
- NON usare MAI le colonne POI (sanita, mobilita, verde, sport, commerciale, educazione) nella clausola WHERE.
- Queste colonne servono solo per il ranking successivo, non per filtrare i dati grezzi.

ESEMPI CONCRETI:

1. Filtro geografico con distanza:
Query: "Appartamenti entro 2km dal Politecnico (45.0628, 7.6621)"
SQL: SELECT * FROM IMMOBILI 
     WHERE haversine_km(latitudine, longitudine, 45.0628, 7.6621) < 2
     AND tipologia_bene_immobile = 'Abitazione'
     ORDER BY haversine_km(latitudine, longitudine, 45.0628, 7.6621) ASC;

2. Filtro per superficie:
Query: "Uffici di almeno 150mq"
SQL: SELECT * FROM IMMOBILI
     WHERE superficie_di_riferimento_mq >= 150
     AND tipologia_bene_immobile = 'Ufficio';

3. CORRETTO - Nessun filtro su APE/POI (ranking successivo):
Query: "Trilocale efficiente vicino scuole"
SQL: SELECT * FROM IMMOBILI
     WHERE tipologia_bene_immobile = 'Abitazione'
     AND haversine_km(latitudine, longitudine, 45.07, 7.68) < 3;
-- Nota: ape_score_total e educazione NON sono nel WHERE!

4. SBAGLIATO - Da evitare:
Query: "Immobili con classe A"
SQL ERRATO: SELECT * FROM IMMOBILI WHERE ape_score_classe >= 4;
SQL CORRETTO: SELECT * FROM IMMOBILI WHERE classe_energetica_ape LIKE 'A%';
-- Usa il valore categorico grezzo, NON il punteggio computato.

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
        from app.core.config import settings

        resolved_model = (
            model_name or AGENT_MODELS.get("sql_agent") or AGENT_MODELS.get("default")
        )
        # Use AGENT_TEMPERATURE for deterministic SQL generation
        self.llm = get_llm(
            model_name=resolved_model, temperature=settings.AGENT_TEMPERATURE
        )

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("sql_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("sql_agent", DEFAULT_USER)

        # Load retry prompts separately
        self.retry_system = get_system_prompt(
            "sql_agent", DEFAULT_RETRY_SYSTEM, key="retry_system"
        )
        self.retry_user = get_user_template(
            "sql_agent", DEFAULT_RETRY_USER, key="retry_user"
        )

    def _invoke(
        self, system: str, user_template: str, variables: dict, is_retry: bool = False
    ) -> tuple[str, PromptRecord]:
        user_text = user_template.format(**variables).strip()
        full_text = f"[SYSTEM]\n{system}\n\n[USER]\n{user_text}"

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                ("user", user_template),
            ]
        )
        chain = prompt | self.llm
        response = invoke_with_langfuse(chain, variables)
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

        raw_text, prompt_record = self._invoke(
            system, user_template, variables, is_retry
        )
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
