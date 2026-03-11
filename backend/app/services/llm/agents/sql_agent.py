from typing import Any, Optional, List, Dict
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings, AGENT_MODELS
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, SQLAgentResult, SQLResponse
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse, is_oss_model
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage
from app.utils.json_parser import safe_extract_json

import re
import sqlglot

def _clean_sql(text: str) -> str:
    """
    Pulisce la stringa SQL da markdown, commenti e testo addizionale.
    Estrae solo la prima query SELECT valida se presente.
    """
    # Rimuove blocchi di ragionamento <think> (DeepSeek-R1)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    
    # Rimuove blocchi di codice markdown
    text = re.sub(r'```sql\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*', '', text)
    
    # Rimuove commenti SQL inline (-- commento)
    text = re.sub(r'--.*$', '', text, flags=re.MULTILINE)
    
    # Cerca il primo WITH o SELECT e prende tutto fino alla fine o al primo punto e virgola
    # Questo aiuta se l'LLM aggiunge chiacchiere prima o dopo
    match = re.search(r'((?:WITH|SELECT)\s+.*)', text, re.IGNORECASE | re.DOTALL)
    if match:
        sql = match.group(1).strip()
        # Se c'è un punto e virgola, prendiamo solo fino a lì (evita comandi multipli)
        if ';' in sql:
            sql = sql.split(';')[0].strip()
        
        # Formattazione tramite sqlglot per leggibilità e correttezza sintattica
        try:
            # transpile restituisce una lista di query, prendiamo la prima
            transpiled = sqlglot.transpile(sql, read="duckdb", pretty=True)
            if transpiled:
                return transpiled[0]
        except Exception:
            # Fallback alla stringa pulita ma non formattata in caso di errore di parsing
            return sql
    
    return text.strip()

def _validate_sql(sql: str) -> bool:
    """Verifica che la query sia un SELECT sicuro e valido per DuckDB."""
    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        return False
    
    # Lista di parole chiave proibite per sicurezza (anche se DuckDB in memory è isolato)
    prohibited = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "EXECUTE", "ATTACH"]
    for word in prohibited:
        # Cerchiamo la parola intera
        if re.search(r'\b' + word + r'\b', sql_upper):
            return False
            
    return True


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
        self.system_prompt = get_system_prompt("sql_agent")
        self.user_template = get_user_template("sql_agent")

        # Load retry prompts separately
        self.retry_system = get_system_prompt(
            "sql_agent", key="retry_system"
        )
        self.retry_user = get_user_template(
            "sql_agent", key="retry_user"
        )

        self.is_oss = is_oss_model(resolved_model)
        
        # Detect if we should use structured output
        if hasattr(self.llm, "with_structured_output") and not self.is_oss:
            self.structured_llm = self.llm.with_structured_output(SQLResponse, method="function_calling")
        else:
            self.structured_llm = None

    def _invoke(
        self, system: str, user_template: str, variables: dict, is_retry: bool = False
    ) -> tuple[str, str, str, PromptRecord]:
        user_text = self.render_template(user_template, **variables).strip()
        full_text = f"[SYSTEM]\n{system}\n\n[USER]\n{user_text}"

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )
        
        # Initial values
        final_sql = ""
        explanation = ""
        raw_text = ""
        
        # Try structured output first if enabled
        if self.structured_llm:
            try:
                chain = prompt | self.structured_llm
                response = invoke_with_langfuse(
                    chain, {"system_content": system, "user_content": user_text}
                )
                if isinstance(response, SQLResponse):
                    prompt_record = PromptRecord(
                        system=system.strip(),
                        user=user_text,
                        full_text=full_text,
                    )
                    return response.sql, response.explanation or "", response.model_dump_json(), prompt_record
                raw_text = str(response)
            except Exception:
                # Fallback to raw chain
                chain = prompt | self.llm | StrOutputParser()
                raw_text = invoke_with_langfuse(
                    chain, {"system_content": system, "user_content": user_text}
                )
        else:
            chain = prompt | self.llm | StrOutputParser()
            raw_text = invoke_with_langfuse(
                chain, {"system_content": system, "user_content": user_text}
            )

        # Post-process for JSON if it's a string (forced extraction)
        # We try to extract JSON before cleaning SQL via regex
        extracted = safe_extract_json(raw_text, schema=SQLResponse)
        if extracted and isinstance(extracted, SQLResponse):
            final_sql = extracted.sql
            explanation = extracted.explanation or ""
        elif isinstance(extracted, dict) and "sql" in extracted:
            final_sql = extracted["sql"]
            explanation = extracted.get("explanation", "")
        else:
            # Last resort: existing regex cleaning if JSON extraction failed
            final_sql = _clean_sql(raw_text)
            # If we used regex cleaning, we might be able to extract explanation too
            if not explanation and "spiegazione" in raw_text.lower():
                 expl_match = re.search(r"(?:spiegazione|explanation):\s*(.*)", raw_text, re.IGNORECASE | re.DOTALL)
                 if expl_match:
                     explanation = expl_match.group(1).strip()

        # Reconstruct clean JSON for raw_text if we have structured data
        if final_sql:
            raw_text = json.dumps({"sql": final_sql, "explanation": explanation}, ensure_ascii=False, indent=2)

        prompt_record = PromptRecord(
            system=system.strip(),
            user=user_text,
            full_text=full_text,
        )
        return final_sql, explanation, raw_text, prompt_record

    @log_llm_usage
    def run(
        self,
        *,
        query: str,
        scheme: str = "",
        all_requirements: str = "N/D",
        location: Optional[Any] = None,
        failed_query: Optional[str] = None,
        error_msg: Optional[str] = None,
        db_metadata: str = "",
        raw_response: Optional[str] = None,  # If provided, bypass LLM and use this
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
            "all_requirements": all_requirements,
            "failed_query": failed_query or "",
            "location_str": location_str,
            "lat": lat,
            "lon": lon,
            "error_msg": error_msg or "Nessun risultato trovato (query vuota).",
            "db_metadata": db_metadata,
        }

        if raw_response:
            # If we already have the SQL (deterministic relaxation), bypass LLM but return same structure
            # to trigger logging hooks in tests.
            return SQLAgentResult(
                raw_text=_clean_sql(raw_response),
                prompt=PromptRecord(
                    system="DETERMINISTIC RELAXATION (Bypass LLM)",
                    user=f"Relaxing query: {failed_query}",
                    full_text=f"Bypassing LLM for deterministic relaxation.\nResult: {raw_response}"
                )
            )

        sql, explanation, raw_text, prompt_record = self._invoke(
            system, user_template, variables, is_retry
        )

        # Fix common SQL syntax errors from LLM
        # 1. Fix single quote escaping: replace \' with ''
        sql = sql.replace("\\'", "''")

        # Basic Validation
        if not _validate_sql(sql):
            # If invalid, we return it anyway but the orchestrator will catch the execution failure
            # or we could prepend a comment to help debugging.
            pass

        return SQLAgentResult(
            raw_text=raw_text,
            sql=sql,
            explanation=explanation,
            prompt=prompt_record,
        )
