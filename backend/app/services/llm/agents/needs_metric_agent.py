import json
from typing import Any, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import (
    ApeUsagePlan,
    DatasetStrategy,
    MetricDefinition,
    NeedsMetricPlan,
    PromptRecord,
)
from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage

DEFAULT_SYSTEM = """Agisci come Needs & Metric Agent per l'applicazione MEF-Immobili.
Il tuo compito è interpretare il bisogno dell'utente e proporre un piano di analisi strutturato.

RESTITUISCI SOLO un JSON con la seguente struttura:
{{
    "summary": "<riassunto del bisogno/obiettivo>",
    "metrics": [
        {{"name": "<nome>", "goal": "<obiettivo>", "weight": 0.35, "data_points": ["colonna_1", "colonna_2"]}}
    ],
    "dataset_strategy": {{
        "filters": ["<descrizione filtro 1>", "<descrizione filtro 2>"],
        "sort_by": "<colonna> <ASC|DESC>",
        "notes": "<indicazioni aggiuntive>"
    }},
    "ape_strategy": {{
        "use_ape": true,
        "strategy": "<come sfruttare i dati APE se necessari>"
    }}
}}

Linee guida:
- Usa i nomi delle colonne presenti nello schema quando suggerisci filtri o metriche.
- "data_points" deve citare colonne o fonti utili per calcolare la metrica.
- Se i dati APE non sono rilevanti, imposta use_ape=false e spiega il motivo.
- Se l'immobile è utilizzato direttamente non penalizzarlo.
- CRITICO: NON suggerire MAI filtri SQL (clausola WHERE) per metriche soggettive o punteggi.
- BLACKLIST FILTRI SQL (Vietato usare queste colonne in "filters"):
  * Colonne POI: [sanita, mobilita, verde, sport, commerciale, educazione]
  * Colonne APE: [ape_score_total, ape_score_classe, classe_energetica_ape]
  * Colonne Stato: [stato_manutentivo, utilizzo_del_bene]
- Se l'utente chiede "buone scuole" o "alta efficienza", NON filtrare via SQL. Inserisci queste colonne in "sort_by" (es. "educazione DESC") o lascia che sia il Ranking Agent a gestirle tramite i pesi.
- I filtri SQL devono essere usati SOLO per vincoli "duri" e oggettivi:
  * Superficie (es. superficie_di_riferimento_mq > 100)
  * Tipologia (es. tipologia_bene_immobile = '...')
  * Distanza (es. raggio < 2km)
- L'obiettivo è ottenere un AMPIO set di candidati (es. 100-1000) da ordinare successivamente."""

DEFAULT_USER = """Query Utente: "{query}"
Schema Database: {db_schema}
Colonne di esempio: {dataset_sample}"""


def _extract_json(text: str) -> Any:
    """Prova ad estrarre un JSON valido dalla risposta del modello."""
    text = (text or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start_positions = [pos for pos in (text.find("{"), text.find("[")) if pos != -1]
    if not start_positions:
        return None

    start = min(start_positions)
    for end in range(len(text), start, -1):
        snippet = text[start:end]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            continue
    return None


def _safe_float(value: Any, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class NeedsMetricAgent(BaseAgent):
    """Agente che sintetizza metriche, filtri e strategia APE a partire dalla query."""

    name = "needs-metric-agent"

    def __init__(self, model_name: Optional[str] = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("needs_metric_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("needs_metric_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("needs_metric_agent", DEFAULT_USER)

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
    @handle_agent_error(
        fallback_value=NeedsMetricPlan(
            summary="Error generating plan",
            metrics=[],
            dataset_strategy=DatasetStrategy(filters=[], sort_by="", notes="Error"),
            ape_strategy=ApeUsagePlan(use_ape=False, strategy="Error"),
            raw_text="Error",
            prompt=None,
        )
    )
    def run(
        self,
        query: str,
        db_schema: str,
        dataset_sample: str = "",
        db_metadata: str = "",
    ) -> NeedsMetricPlan:
        prompt_inputs = {
            "query": query,
            "db_schema": db_schema,
            "dataset_sample": dataset_sample or "",
            "db_metadata": db_metadata,
        }

        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"
        raw = self.chain.invoke(prompt_inputs)

        data = _extract_json(raw) or {}
        metrics_cfg = data.get("metrics") or []
        metrics = []
        for item in metrics_cfg:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            metrics.append(
                MetricDefinition(
                    name=name.strip(),
                    goal=item.get("goal"),
                    weight=_safe_float(item.get("weight"), 1.0),
                    data_points=[
                        dp
                        for dp in (item.get("data_points") or [])
                        if isinstance(dp, str)
                    ],
                )
            )

        dataset_cfg = data.get("dataset_strategy") or {}
        dataset_strategy = DatasetStrategy(
            filters=[
                f for f in (dataset_cfg.get("filters") or []) if isinstance(f, str)
            ],
            sort_by=dataset_cfg.get("sort_by"),
            top_k=_safe_int(dataset_cfg.get("top_k")),
            notes=dataset_cfg.get("notes"),
        )

        ape_cfg = data.get("ape_strategy") or {}
        ape_strategy = ApeUsagePlan(
            use_ape=bool(ape_cfg.get("use_ape", False)),
            strategy=ape_cfg.get("strategy"),
        )

        prompt_record = PromptRecord(
            system=self.system_prompt.strip(),
            user=user_text,
            full_text=full_text,
        )

        return NeedsMetricPlan(
            summary=data.get("summary", ""),
            raw_text=raw,
            prompt=prompt_record,
            metrics=metrics,
            dataset_strategy=dataset_strategy,
            ape_strategy=ape_strategy,
        )
