from typing import List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.core.constants import (
    SQL_FILTERABLE_COLUMNS,
    RANKING_ONLY_COLUMNS,
    POI_CATEGORIES,
    SCORE_LEGEND,
)

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import (
    NeedsMetricPlan,
    PromptRecord,
)
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json

DEFAULT_SYSTEM = """Sei il Needs & Metric Agent per l'applicazione MEF-Immobili.
Il tuo compito è analizzare la richiesta dell'utente e creare un PIANO DI ANALISI strutturato.

### RUOLO
Devi tradurre il bisogno (es. "scuole, efficienza energetica") in metriche di ranking e filtri dataset.

### CONTESTO DATI
Hai a disposizione le seguenti colonne per FILTRARE e ORDINARE:

1. COLONNE FILTRABILI (SQL WHERE):
{sql_filterable_columns}

2. COLONNE PER RANKING (O Punteggi):
{ranking_only_columns}
(Queste colonne NON devono essere usate per filtri rigidi SQL, ma solo per ordinamento o calcolo punteggi)

3. CATEGORIE POI (1-5):
{poi_categories}

{score_legend}

### REGOLE
1. **FILTRI SQL**: Usa SOLO le colonne nella lista "COLONNE FILTRABILI".
   - ❌ NON filtrare MAI per punteggi APE (ape_score_*) o POI (sanita, mobilita...).
   - ✅ Usa filtri SQL (filters) per: superficie, tipologia, zona, epoca, comune, classe energetica.
   
2. **METRICHE & RANKING**: Se l'utente chiede "buone scuole" o "efficiente":
   - ❌ NON filtrare via SQL (esclude troppi risultati).
   - ✅ Aggiungi una METRICA con peso alto (es. name="educazione", weight=0.8).
   - ✅ Oppure usa SORT_BY (es. "educazione DESC").

3. **STRATEGIA DATASET**:
   - Punta ad avere un set ampio di candidati (100-500) da far valutare all'Evaluation Agent.
   - Usa "filters" solo per requisiti "hard" (es. "minimo 100mq").

### OUTPUT
Restituisci ESCLUSIVAMENTE un JSON valido che rispetti questo schema:
{{
    "summary": "<riassunto obiettivo>",
    "metrics": [
        {{"name": "<nome_colonna>", "goal": "<descrizione>", "weight": 0.5, "data_points": ["<colonna>"]}}
    ],
    "dataset_strategy": {{
        "filters": ["<filtro sql like>"],  // Es. "superficie_di_riferimento_mq > 100"
        "sort_by": "<colonna> DESC",
        "notes": "<note>"
    }},
    "ape_strategy": {{
        "use_ape": <true|false>,
        "strategy": "<come usare i dati ape>"
    }}
}}
"""

DEFAULT_USER = """Query Utente: "{query}"
Schema Database (riferimento tipi): {db_schema}
"""


class NeedsMetricAgent(BaseAgent):
    """Agente che sintetizza metriche, filtri e strategia APE a partire dalla query."""

    name = "needs-metric-agent"

    def __init__(self, model_name: str = None):
        from app.core.config import settings

        resolved_model = (
            model_name
            or AGENT_MODELS.get("needs_metric_agent")
            or AGENT_MODELS.get("default")
        )
        # Use AGENT_TEMPERATURE for consistency in filter suggestions
        self.llm = get_llm(
            model_name=resolved_model, temperature=settings.AGENT_TEMPERATURE
        )

        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("needs_metric_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("needs_metric_agent", DEFAULT_USER)

        # Create ChatPromptTemplate
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", self.user_template),
            ]
        )
        self.parser = StrOutputParser()
        self.chain = self.prompt_template | self.llm | self.parser

    @log_llm_usage
    @handle_agent_error(
        fallback_value=None  # Will be handled by return type hint or explicit construction match
    )
    def run(
        self,
        query: str,
        db_schema: str,
        dataset_sample: str = "",
        db_metadata: str = "",
        categorical_values: dict = None,  # NEW: categorical value lists
    ) -> NeedsMetricPlan:
        # Construct dynamic lists for prompt
        sql_filterable = ", ".join(SQL_FILTERABLE_COLUMNS)
        ranking_only = ", ".join(RANKING_ONLY_COLUMNS)
        poi_cats = ", ".join([f"{k} ({v})" for k, v in POI_CATEGORIES.items()])

        # Format system prompt
        system_content = self.system_prompt.format(
            sql_filterable_columns=sql_filterable,
            ranking_only_columns=ranking_only,
            poi_categories=poi_cats,
            score_legend=SCORE_LEGEND,
            format_instructions="",  # Optional if we moved json structure into main prompt text
        )

        prompt_inputs = {
            "system_content": system_content,
            "query": query,
            "db_schema": db_schema,
            "dataset_sample": dataset_sample,
            "db_metadata": db_metadata,
        }

        # Add categorical values info to user prompt if available
        if categorical_values:
            import json

            categorical_info = json.dumps(
                categorical_values, indent=2, ensure_ascii=False
            )
            categorical_context = f"""

VALORI CATEGORICI DISPONIBILI:
{categorical_info}

Quando l'utente menziona valori specifici (es. "classe F o G", "epoca recente"), 
usa questi valori esatti nei filtri. Esempio:
- "classe energetica bassa (F o G)" → filters: ["classe_energetica_ape IN ('F', 'G')"]
- "immobili recenti" → filters: ["epoca_costruzione IN ('...valori recenti...)"]  
"""
            prompt_inputs["db_metadata"] = db_metadata + categorical_context
        else:
            prompt_inputs["db_metadata"] = db_metadata

        user_text = self.user_template.format(
            query=query,
            db_schema=db_schema,
            dataset_sample=dataset_sample,
            db_metadata=db_metadata,
        ).strip()
        full_text = f"[SYSTEM]\n{system_content}\n\n[USER]\n{user_text}"

        try:
            raw = invoke_with_langfuse(self.chain, prompt_inputs)

            # Parse with Pydantic model
            plan = safe_extract_json(raw, schema=NeedsMetricPlan)

            if not plan:
                # Fallback empty plan
                from app.services.llm.agents.schema import (
                    MetricDefinition,
                    DatasetStrategy,
                    ApeUsagePlan,
                )

                plan = NeedsMetricPlan(
                    summary="Fallback: could not parse plan",
                    metrics=[],
                    dataset_strategy=DatasetStrategy(),
                    ape_strategy=ApeUsagePlan(),
                )

            # Inject prompt record (since safe_extract_json returns clean model)
            plan.raw_text = raw
            plan.prompt = PromptRecord(
                system=system_content, user=user_text, full_text=full_text
            )

            return plan

        except Exception as e:
            # Re-raise or return empty?
            # handle_agent_error decorator should handle exceptions, but we need to match return type
            print(f"Error NeedsMetricAgent: {e}")
            from app.services.llm.agents.schema import DatasetStrategy, ApeUsagePlan

            return NeedsMetricPlan(
                summary=f"Error: {str(e)}",
                raw_text="Error",
                metrics=[],
                dataset_strategy=DatasetStrategy(),
                ape_strategy=ApeUsagePlan(),
            )
