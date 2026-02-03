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
        self.system_prompt = get_system_prompt("needs_metric_agent")
        self.user_template = get_user_template("needs_metric_agent")

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
        system_content = self.render_template(
            self.system_prompt,
            sql_filterable_columns=sql_filterable,
            ranking_only_columns=ranking_only,
            poi_categories=poi_cats,
            score_legend=SCORE_LEGEND,
            format_instructions="",
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

        user_text = self.render_template(
            self.user_template,
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
