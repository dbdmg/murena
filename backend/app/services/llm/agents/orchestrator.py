from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import sqlparse
import tabulate

from app.core.config import settings

# Constants from settings
MAX_ITEMS_FOR_LLM = settings.MAX_ITEMS_FOR_LLM
MAX_ITEMS_FOR_MAP = settings.MAX_ITEMS_FOR_MAP
MAX_LLM_CAP = settings.MAX_LLM_CAP

from app.core.constants import APE_SCORE_LEGEND

from app.data.loaders import get_coordinates
from app.data.processors import calculate_travel_times_df
from app.services.llm.agents.ape_agent import ApeAgent
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.evaluation_agent import EvaluationAgent
from app.services.llm.agents.location_agent import LocationAgent
from app.services.llm.agents.needs_metric_agent import NeedsMetricAgent
from app.services.llm.agents.normative_agent import NormativeAgent
from app.services.llm.agents.poi_amenity_agent import PoiAmenityAgent
from app.services.llm.agents.poi_category_agent import PoiCategoryAgent
from app.services.llm.agents.schema import (
    AgentContext,
    EvaluationAgentResponse,
    NeedsMetricPlan,
)
from app.services.llm.agents.sql_agent import SQLAgent
from app.services.llm.agents.typology_agent import TypologyAgent
from app.services.llm.agents.use_case_agent import UseCaseAgent


@dataclass
class OrchestratorResult:
    map_df: pd.DataFrame
    location: List[List[Union[str, float]]]
    status_msg: str
    gemini_responses: Dict[str, Any]
    where_clause: str
    context: AgentContext
    broker_summary: Optional[str] = None


class OrchestratorAgent(BaseAgent):
    """Agente orchestratore che coordina l'intera pipeline multi-agente."""

    name = "orchestrator-agent"
    CLASSIC_STEPS = [
        {"key": "analysis", "label": "Analisi parallela agenti"},
        {"key": "processing", "label": "Elaborazione risultati"},
        {"key": "sql", "label": "Generazione query SQL"},
        {"key": "execution", "label": "Esecuzione query"},
        {"key": "evaluation", "label": "Valutazione dataset"},
        {"key": "merge", "label": "Finalizzazione risultati"},
        {"key": "complete", "label": "Completato"},
    ]
    AGENT_STEPS = [
        {"key": "analysis", "label": "Analisi parallela agenti"},
        {"key": "processing", "label": "Elaborazione risultati"},
        {"key": "sql", "label": "Generazione query SQL"},
        {"key": "execution", "label": "Esecuzione query"},
        {"key": "evaluation", "label": "Valutazione dataset"},
        {"key": "merge", "label": "Finalizzazione risultati"},
        {"key": "complete", "label": "Completato"},
    ]

    def __init__(
        self,
        *,
        analysis_mode: str = "agent",
        execute_sql_fn: Optional[Callable[[str, pd.DataFrame], pd.DataFrame]] = None,
        location_agent: Optional[LocationAgent] = None,
        needs_agent: Optional[NeedsMetricAgent] = None,
        use_case_agent: Optional[UseCaseAgent] = None,
        sql_agent: Optional[SQLAgent] = None,
        evaluation_agent: Optional[EvaluationAgent] = None,
        typology_agent: Optional[TypologyAgent] = None,
        ape_agent: Optional[ApeAgent] = None,
        poi_category_agent: Optional[PoiCategoryAgent] = None,
        poi_amenity_agent: Optional[PoiAmenityAgent] = None,
        normative_agent: Optional[NormativeAgent] = None,
    ) -> None:
        if execute_sql_fn is None:
            raise ValueError("execute_sql_fn e obbligatoria per OrchestratorAgent.")

        self.analysis_mode = (analysis_mode or "agent").lower()
        self.is_agent_mode = self.analysis_mode == "agent"
        self.execute_sql_fn = execute_sql_fn

        self.location_agent = location_agent or LocationAgent()
        self.needs_agent = needs_agent or NeedsMetricAgent()
        self.use_case_agent = use_case_agent or UseCaseAgent()
        self.sql_agent = sql_agent or SQLAgent()
        self.evaluation_agent = evaluation_agent or EvaluationAgent()
        self.typology_agent = typology_agent or TypologyAgent()
        self.ape_agent = ape_agent or ApeAgent()
        self.poi_category_agent = poi_category_agent or PoiCategoryAgent()
        self.poi_amenity_agent = poi_amenity_agent or PoiAmenityAgent()
        self.normative_agent = normative_agent or NormativeAgent()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        *,
        query: str,
        dataset_key: str,
        base_dataset: pd.DataFrame,
        db_schema: Dict[str, Any],
        ape_df: pd.DataFrame = None,
        set_progress: Optional[Callable[[Any], None]] = None,
        llm_limit: Optional[int] = None,
        map_limit: Optional[int] = None,
        metro_graph: Optional[Any] = None,
    ) -> OrchestratorResult:
        if base_dataset is None:
            raise FileNotFoundError("Dataset non disponibile per l'analisi.")

        step_definitions = (
            self.AGENT_STEPS if self.is_agent_mode else self.CLASSIC_STEPS
        )
        total_steps = len(step_definitions)

        def update_progress(step_index: int, message: str) -> None:
            if not set_progress:
                return
            percent = step_index * 100 / total_steps
            steps_state = self._build_step_states(step_definitions, step_index, message)
            set_progress((percent, steps_state))

        context = AgentContext(user_query=query)
        gemini_responses: Dict[str, Any] = {
            "analysis_mode": self.analysis_mode,
            "dataset_key": dataset_key,
        }

        # ------------------------------------------------------------------
        # PARALLEL EXECUTION - All agents run in parallel from user query
        # ------------------------------------------------------------------
        update_progress(0, "Analisi parallela della query...")

        # Prepare inputs
        available_typologies = []
        if (
            base_dataset is not None
            and "tipologia_bene_immobile" in base_dataset.columns
        ):
            available_typologies = [
                str(x)
                for x in base_dataset["tipologia_bene_immobile"].unique()
                if pd.notna(x)
            ]

        sample_columns = (
            ", ".join(base_dataset.columns[:15])
            if hasattr(base_dataset, "columns")
            else ""
        )

        # Define tasks for parallel execution
        def run_typology():
            logging.info("🔧 Executing TypologyAgent")
            result = self.typology_agent.run(query, available_typologies)
            logging.info(f"✅ TypologyAgent completed: {result.typologies}")
            return result

        def run_location():
            logging.info("📍 Executing LocationAgent")
            result = self.location_agent.run(query=query)
            logging.info(f"✅ LocationAgent completed: {len(result.places)} places")
            return result

        def run_ape():
            # Always run APE agent if data is available
            if ape_df is not None:
                logging.info("⚡ Executing ApeAgent")
                result = self.ape_agent.run(query, ape_df, score_legend=APE_SCORE_LEGEND)
                logging.info(f"✅ ApeAgent completed")
                return result
            logging.info("⚠️ ApeAgent skipped: no data")
            return None

        def run_poi():
            logging.info("🏪 Executing POI Agents")
            category_result = self.poi_category_agent.run(query=query)
            logging.info(f"✅ PoiCategoryAgent completed: {len(category_result.category_weights)} categories")
            amenity_result = self.poi_amenity_agent.run(
                query=query, category_weights=category_result.category_weights
            )
            logging.info(f"✅ PoiAmenityAgent completed: {len(amenity_result.selected_categories)} categories")
            return (category_result, amenity_result)

        def run_normative():
            logging.info("📚 Executing NormativeAgent")
            result = self.normative_agent.run(query=query)
            logging.info(f"✅ NormativeAgent completed")
            return result

        # Execute all agents in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_typology = executor.submit(run_typology)
            future_location = executor.submit(run_location)
            future_ape = executor.submit(run_ape)
            future_poi = executor.submit(run_poi)
            future_normative = executor.submit(run_normative)

            # Collect results
            typology_result = future_typology.result()
            loc_result = future_location.result()
            ape_result = future_ape.result()
            poi_results = future_poi.result()
            normative_result = future_normative.result()

        update_progress(1, "Elaborazione risultati agenti...")

        # Process Typology results
        context.typology_result = typology_result
        gemini_responses["typology_extraction"] = {
            "prompt": (
                typology_result.prompt.model_dump() if typology_result.prompt else None
            ),
            "response": typology_result.raw_text,
            "typologies": typology_result.typologies,
        }

        # Apply typology filter
        working_dataset = base_dataset
        if typology_result.typologies:
            working_dataset = base_dataset[
                base_dataset["tipologia_bene_immobile"].isin(typology_result.typologies)
            ]

        # Process Location results
        context.locations = loc_result.places
        gemini_responses["location_extraction"] = {
            "prompt": loc_result.prompt.model_dump() if loc_result.prompt else None,
            "response": loc_result.raw_text,
            "places": [p.model_dump() for p in loc_result.places],
        }

        # Geocode locations
        location_payload: List[List[Union[str, float]]] = []
        if loc_result.places:
            for place in loc_result.places:
                search_query = (
                    f"{place.name}, {place.city}" if place.city else place.name
                )
                try:
                    lat, lon = get_coordinates(search_query)
                except Exception:
                    lat, lon = None, None
                if lat is not None and lon is not None:
                    location_payload.append([search_query, lat, lon])

        # Process APE results
        ape_filters: List[str] = []
        if ape_result is not None:
            gemini_responses["ape_analysis"] = {
                "prompt": (
                    ape_result.prompt.model_dump() if ape_result.prompt else None
                ),
                "response": ape_result.raw_text,
                "answer": ape_result.answer,
            }
            if (
                hasattr(ape_result, "suggested_filters")
                and ape_result.suggested_filters
            ):
                ape_filters = ape_result.suggested_filters

        # Process POI results
        if poi_results:
            poi_category_result, poi_amenity_result = poi_results
            gemini_responses["poi_category_analysis"] = {
                "prompt": (
                    poi_category_result.prompt.model_dump()
                    if poi_category_result.prompt
                    else None
                ),
                "response": poi_category_result.raw_text,
                "category_weights": poi_category_result.category_weights,
            }
            gemini_responses["poi_amenity_analysis"] = {
                "prompt": (
                    poi_amenity_result.prompt.model_dump()
                    if poi_amenity_result.prompt
                    else None
                ),
                "response": poi_amenity_result.raw_text,
                "amenity_weights": poi_amenity_result.amenity_weights,
            }
            context.poi_category_result = poi_category_result
            context.poi_amenity_result = poi_amenity_result

        # Process Normative results
        if normative_result:
            gemini_responses["normative_analysis"] = {
                "prompt": (
                    normative_result.prompt.model_dump()
                    if normative_result.prompt
                    else None
                ),
                "response": normative_result.raw_text,
                "constraints": normative_result.constraints,
                "recommendations": normative_result.recommendations,
            }
            context.normative_result = normative_result

        # ------------------------------------------------------------------
        # STEP 2 - SQL generation + STEP 3 execution
        # ------------------------------------------------------------------
        update_progress(2, "Generazione query SQL...")
        max_retries = 5
        retry_count = 0
        selected_data = pd.DataFrame()
        sql_query = ""

        loc_obj = None
        if isinstance(location_payload, list) and location_payload:
            _, lat, lon = location_payload[0]
            loc_obj = {"lat": lat, "lon": lon}

        # Use query directly without augmentation
        sql_prompt = query

        while retry_count < max_retries:
            if retry_count == 0:
                sql_result = self.sql_agent.run(
                    query=sql_prompt, scheme=str(db_schema), location=loc_obj
                )
                sql_query = sql_result.sql_query
                gemini_responses["sql_generation"] = {
                    "prompt": (
                        sql_result.prompt.model_dump() if sql_result.prompt else None
                    ),
                    "response": sql_result.raw_text,
                    "sql_query": sql_query,
                }
            else:
                update_progress(
                    2,
                    f"Rigenerazione query SQL (tentativo {retry_count + 1}/{max_retries})...",
                )
                sql_result = self.sql_agent.run(
                    query=sql_prompt,
                    scheme=str(db_schema),
                    location=loc_obj,
                    failed_query=sql_query,
                )
                sql_query = sql_result.sql_query
                gemini_responses[f"sql_generation_retry_{retry_count}"] = {
                    "prompt": (
                        sql_result.prompt.model_dump() if sql_result.prompt else None
                    ),
                    "response": sql_result.raw_text,
                    "sql_query": sql_query,
                }

            update_progress(3, f"Esecuzione query (tentativo {retry_count + 1})...")
            selected_data = self.execute_sql_fn(sql_query, working_dataset)
            if not selected_data.empty:
                break
            retry_count += 1

        if selected_data.empty:
            status_msg = (
                f"La ricerca non ha prodotto risultati dopo {max_retries} tentativi."
            )
            context.filtered_dataset_preview = []
            gemini_responses["agent_context"] = context.model_dump()
            update_progress(6, "Completato.")
            return OrchestratorResult(
                map_df=pd.DataFrame(),
                location=location_payload,
                status_msg=status_msg,
                gemini_responses=gemini_responses,
                where_clause="Nessuna clausola WHERE trovata.",
                context=context,
            )

        # ------------------------------------------------------------------
        # STEP 5 - Post processing + evaluation prep
        # ------------------------------------------------------------------
        try:
            parsed = sqlparse.parse(sql_query)[0]
            where_clause_str = next(
                (
                    str(token)
                    for token in parsed.tokens
                    if isinstance(token, sqlparse.sql.Where)
                ),
                "Nessuna clausola WHERE trovata.",
            )
        except Exception:
            where_clause_str = "Nessuna clausola WHERE trovata."

        cols_to_add = working_dataset.columns.difference(selected_data.columns).tolist()
        if (
            "id" in working_dataset.columns
            and "id" in selected_data.columns
            and cols_to_add
        ):
            selected_data = pd.merge(
                selected_data,
                working_dataset[["id"] + cols_to_add],
                on="id",
                how="left",
            )

        location_list = location_payload if isinstance(location_payload, list) else []
        if location_list:
            enriched_data = calculate_travel_times_df(selected_data, location_list)
        else:
            enriched_data = selected_data

        if not isinstance(enriched_data, pd.DataFrame):
            enriched_data = selected_data

        if "distanza_km" not in enriched_data.columns:
            enriched_data["distanza_km"] = np.nan

        context.filtered_dataset_preview = enriched_data.head(10).to_dict("records")

        llm_cap = min(int(llm_limit) if llm_limit else MAX_ITEMS_FOR_LLM, MAX_LLM_CAP)
        map_cap = self._resolve_map_cap(map_limit)

        # Build use case from agent results
        use_case_parts = [f"Query: {query}"]
        if ape_result:
            use_case_parts.append(f"APE: {ape_result.answer}")
        if poi_results:
            poi_category_result, poi_amenity_result = poi_results
            use_case_parts.append(f"POI Categories: {list(poi_category_result.category_weights.keys())}")
        if normative_result:
            use_case_parts.append(f"Normative: {normative_result.normative_info[:200]}")
        use_case_str = "\n".join(use_case_parts)

        update_progress(4, f"Valutazione su top {llm_cap}...")
        eval_input_df = enriched_data.head(llm_cap).copy()
        eval_input_df["is_evaluated"] = True
        estates_data_str = tabulate.tabulate(
            eval_input_df, headers="keys", tablefmt="grid"
        )
        eval_payload: EvaluationAgentResponse = self.evaluation_agent.run(
            use_case=use_case_str,
            estates_data=estates_data_str,
        )
        eval_results = eval_payload.results
        context.evaluation_results = eval_results
        gemini_responses["evaluation"] = {
            "prompt": eval_payload.prompt.model_dump() if eval_payload.prompt else None,
            "response": eval_payload.raw_text,
            "results": [res.model_dump() for res in eval_results],
        }

        # ------------------------------------------------------------------
        # STEP 5 - Merge evaluation back into map dataset
        # ------------------------------------------------------------------
        update_progress(5, "Finalizzazione risultati...")
        map_df = enriched_data.head(map_cap).copy()
        map_df["is_evaluated"] = False

        if eval_results:
            val_data: List[Dict[str, Any]] = []
            for res in eval_results:
                pro_text = "\n".join(res.pros) if res.pros else ""
                contro_text = "\n".join(res.cons) if res.cons else ""
                val_data.append(
                    {
                        "id": res.id,
                        "score": res.score,
                        "motivazione": res.evaluation_text,
                        "pro": pro_text,
                        "contro": contro_text,
                    }
                )

            valutazioni_df = pd.DataFrame(val_data)
            if (
                not valutazioni_df.empty
                and "id" in eval_input_df.columns
                and "id" in map_df.columns
            ):
                valutazioni_df["id"] = valutazioni_df["id"].astype(str)
                eval_input_df["id"] = eval_input_df["id"].astype(str)
                map_df["id"] = map_df["id"].astype(str)

                evaluated_df = pd.merge(
                    eval_input_df, valutazioni_df, on="id", how="left"
                )
                map_df = pd.merge(
                    map_df,
                    evaluated_df[
                        ["id", "score", "motivazione", "pro", "contro"]
                    ].drop_duplicates("id"),
                    on="id",
                    how="left",
                )
                map_df["is_evaluated"] = map_df["id"].isin(eval_input_df["id"])
                status_msg = (
                    f"Trovati {len(map_df)} risultati. "
                    f"LLM ha valutato {len(valutazioni_df)}/{len(eval_input_df)} elementi."
                )
            else:
                status_msg = (
                    f"Trovati {len(map_df)} risultati. Nessuna valutazione generata."
                )
        else:
            status_msg = (
                f"Trovati {len(map_df)} risultati. Nessuna valutazione LLM disponibile."
            )
            eval_ids = (
                enriched_data.head(llm_cap)["id"]
                if "id" in enriched_data.columns
                else []
            )
            map_df["is_evaluated"] = (
                map_df.get("id").isin(eval_ids) if "id" in map_df.columns else False
            )

        gemini_responses["agent_context"] = context.model_dump()
        update_progress(6, "Completato.")

        return OrchestratorResult(
            map_df=map_df,
            location=location_payload,
            status_msg=status_msg,
            gemini_responses=gemini_responses,
            where_clause=where_clause_str,
            context=context,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resolve_llm_cap(
        self, llm_limit: Optional[int], plan: Optional[NeedsMetricPlan]
    ) -> int:
        base_cap = min(int(llm_limit) if llm_limit else MAX_ITEMS_FOR_LLM, MAX_LLM_CAP)
        if self.is_agent_mode and plan and plan.dataset_strategy.top_k:
            return min(base_cap, plan.dataset_strategy.top_k)
        return base_cap

    def _resolve_map_cap(self, map_limit: Optional[int]) -> int:
        try:
            m_val = int(map_limit) if map_limit else MAX_ITEMS_FOR_MAP
            return max(1, m_val)
        except (TypeError, ValueError):
            return MAX_ITEMS_FOR_MAP

    def _augment_query_with_plan(
        self, query: str, plan: Optional[NeedsMetricPlan], ape_filters: List[str] = None
    ) -> str:
        if not (self.is_agent_mode and plan):
            return query

        filters_list = (
            plan.dataset_strategy.filters.copy()
            if plan.dataset_strategy.filters
            else []
        )
        if ape_filters:
            filters_list.extend(ape_filters)

        filters = "\n".join(filters_list) if filters_list else ""
        metrics = "\n".join(
            f"- {metric.name}: {metric.goal or ''} (peso {metric.weight})"
            for metric in plan.metrics
        )
        notes = plan.dataset_strategy.notes or ""
        ape_note = plan.ape_strategy.strategy or ""
        ape_status = "usa dati APE" if plan.ape_strategy.use_ape else "APE opzionale"
        plan_text = (
            f"OBIETTIVO: {plan.summary}\n"
            f"METRICHE:\n{metrics or '- non specificate'}\n"
            f"FILTRI:\n{filters or '- nessuno suggerito'}\n"
            f"ORDINAMENTO: {plan.dataset_strategy.sort_by or 'non specificato'}\n"
            f"NOTE: {notes}\n"
            f"APE: {ape_status} - {ape_note}\n"
            f"TOP_K: {plan.dataset_strategy.top_k or 'default'}\n"
        )
        return f"{query} \n\nPiano di metriche e strategia:\n{plan_text}"

    def _format_plan_for_evaluation(self, plan: NeedsMetricPlan) -> str:
        metrics_text = (
            "\n".join(
                f"- {metric.name}: {metric.goal or 'Obiettivo non specificato'}"
                for metric in plan.metrics
            )
            or "- Metriche non definite"
        )
        filters_text = (
            ", ".join(plan.dataset_strategy.filters) or "nessun filtro specifico"
        )
        ape_text = plan.ape_strategy.strategy or (
            "Utilizzo APE" if plan.ape_strategy.use_ape else "APE non prioritario"
        )
        return (
            f"Obiettivo: {plan.summary}\n"
            f"Metriche:\n{metrics_text}\n"
            f"Strategia Dataset: ordina per {plan.dataset_strategy.sort_by or 'rilevanza'}, "
            f"applica {filters_text}, top_k={plan.dataset_strategy.top_k or 'default'}\n"
            f"Indicazioni APE: {ape_text}"
        )

    def _build_step_states(
        self,
        steps: List[Dict[str, str]],
        current_index: int,
        detail: str,
    ) -> List[Dict[str, str]]:
        state_list: List[Dict[str, str]] = []
        for idx, step in enumerate(steps, start=1):
            if idx < current_index:
                state = "done"
            elif idx == current_index:
                state = "current"
            else:
                state = "pending"
            state_list.append(
                {
                    "label": step.get("label", f"Step {idx}"),
                    "state": state,
                    "detail": detail if state == "current" else "",
                }
            )
        return state_list
