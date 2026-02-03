from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import PromptRecord, SQLAgentResult
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import log_llm_usage

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
        self.system_prompt = get_system_prompt("sql_agent")
        self.user_template = get_user_template("sql_agent")

        # Load retry prompts separately
        self.retry_system = get_system_prompt(
            "sql_agent", key="retry_system"
        )
        self.retry_user = get_user_template(
            "sql_agent", key="retry_user"
        )

    def _invoke(
        self, system: str, user_template: str, variables: dict, is_retry: bool = False
    ) -> tuple[str, PromptRecord]:
        user_text = self.render_template(user_template, **variables).strip()
        full_text = f"[SYSTEM]\n{system}\n\n[USER]\n{user_text}"

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )
        chain = prompt | self.llm
        response = invoke_with_langfuse(
            chain, {"system_content": system, "user_content": user_text}
        )
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
            raw_text=sql,
            prompt=prompt_record,
        )
