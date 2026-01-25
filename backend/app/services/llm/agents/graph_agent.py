from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union

from langgraph.graph import END, StateGraph
import numpy as np
import pandas as pd
import sqlparse
import tabulate

from app.services.analysis.ranking import calculate_ranking_score
from app.core.config import settings
from app.core.constants import SCORE_LEGEND, APE_AGENT_COLUMNS

MAX_ITEMS_FOR_LLM = settings.MAX_ITEMS_FOR_LLM
MAX_ITEMS_FOR_MAP = settings.MAX_ITEMS_FOR_MAP
MAX_LLM_CAP = settings.MAX_LLM_CAP
USE_MOCK_RESPONSES = settings.USE_MOCK_RESPONSES
from app.data.loaders import get_coordinates
from app.data.processors import calculate_travel_times_df
from app.services.llm.agents.ape_agent import ApeAgent
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.evaluation_agent import EvaluationAgent
from app.services.llm.agents.location_agent import LocationAgent
from app.services.llm.agents.needs_metric_agent import NeedsMetricAgent
from app.services.llm.agents.orchestrator import OrchestratorResult
from app.services.llm.agents.poi_agent import PoiAgent
from app.services.llm.agents.schema import (
    AgentContext,
    EvaluationAgentResponse,
    NeedsMetricPlan,
    PoiAgentResult,
    TypologyAgentResult,
)
from app.services.llm.agents.sql_agent import SQLAgent
from app.services.llm.agents.typology_agent import TypologyAgent
from app.services.llm.agents.use_case_agent import UseCaseAgent
from app.utils.logger import logger
from app.services.llm.mocks import (
    MOCK_TYPOLOGY,
    MOCK_LOCATION,
    MOCK_STRATEGY,
    MOCK_SQL_QUERY,
    MOCK_EVALUATION,
    MOCK_BROKER_SUMMARY,
)
from app.utils.run_json_logger import get_run_logger


class GraphState(TypedDict):
    query: str
    dataset_key: str
    # base_dataset: Any  # REMOVED for Memory Management
    dataset_path: Optional[str]  # Path to parquet file
    # working_dataset: Any # REMOVED for Memory Management
    # ape_df: Any # REMOVED for Memory Management
    db_schema: Dict[str, Any]
    db_metadata: Dict[str, Any]  # New field for metadata
    dataset_metadata: Dict[
        str, Any
    ]  # New field for lightweight metadata (columns, typologies)

    # Intermediate
    location_payload: List[List[Union[str, float]]]
    use_case_str: str
    metrics_plan: Optional[NeedsMetricPlan]
    typology_result: Optional[TypologyAgentResult]
    poi_result: Optional[PoiAgentResult]
    sql_query: str
    selected_data: Any  # pd.DataFrame
    execution_error: Optional[str]
    retry_count: int
    status_msg: str
    gemini_responses: Dict[str, Any]
    context: AgentContext
    where_clause: str
    broker_summary: str  # Executive summary from Senior Broker

    # Config
    llm_limit: Optional[int]
    map_limit: Optional[int]
    metro_graph: Any
    analysis_mode: str

    # Progress callback
    set_progress: Optional[Callable[[Any], None]]
    step_definitions: List[Dict[str, str]]
    relax_constraints: bool  # Flag for smart relaxation


class GraphOrchestratorAgent(BaseAgent):
    """
    Orchestrator implemented using LangGraph.
    """

    name = "graph-orchestrator-agent"

    def __init__(
        self,
        *,
        analysis_mode: str = "agent",
        execute_sql_fn: Optional[
            Callable[[str, pd.DataFrame], tuple[pd.DataFrame, Optional[str]]]
        ] = None,
        location_agent: Optional[LocationAgent] = None,
        needs_agent: Optional[NeedsMetricAgent] = None,
        use_case_agent: Optional[UseCaseAgent] = None,
        sql_agent: Optional[SQLAgent] = None,
        evaluation_agent: Optional[EvaluationAgent] = None,
        typology_agent: Optional[TypologyAgent] = None,
        ape_agent: Optional[ApeAgent] = None,
        poi_agent: Optional[PoiAgent] = None,
    ) -> None:
        if execute_sql_fn is None:
            raise ValueError("execute_sql_fn is required.")

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
        self.poi_agent = poi_agent or PoiAgent()

        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node("analyze_request", self._analyze_request)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("handle_retry", self._handle_retry)
        workflow.add_node("fallback_results", self._fallback_results)  # NEW
        workflow.add_node("enrich_results", self._enrich_results)
        workflow.add_node("rank_results", self._rank_results)
        workflow.add_node("evaluate_results", self._evaluate_results)
        workflow.add_node("broker_review", self._broker_review)
        workflow.add_node("finalize_results", self._finalize_results)

        # Add edges
        workflow.set_entry_point("analyze_request")
        workflow.add_edge("analyze_request", "generate_sql")
        workflow.add_edge("generate_sql", "execute_sql")
        workflow.add_edge("handle_retry", "generate_sql")

        # Conditional edge for retry loop
        workflow.add_conditional_edges(
            "execute_sql",
            self._check_sql_execution,
            {
                "retry": "handle_retry",
                "retry_relax": "handle_retry",
                "continue": "enrich_results",
                "fallback": "fallback_results",  # NEW: route to fallback instead of empty
            },
        )

        # Fallback continues to enrich (so ranking/evaluation still happen)
        workflow.add_edge("fallback_results", "enrich_results")
        workflow.add_edge("enrich_results", "rank_results")
        workflow.add_edge("rank_results", "evaluate_results")
        workflow.add_edge("evaluate_results", "broker_review")
        workflow.add_edge("broker_review", "finalize_results")
        workflow.add_edge("finalize_results", END)

        return workflow.compile()

    def run(
        self,
        *,
        query: str,
        dataset_key: str,
        base_dataset: pd.DataFrame,
        db_schema: Dict[str, Any],
        ape_df: pd.DataFrame = None,
        dataset_path: Optional[str] = None,
        set_progress: Optional[Callable[[Any], None]] = None,
        llm_limit: Optional[int] = None,
        map_limit: Optional[int] = None,
        metro_graph: Optional[Any] = None,
    ) -> OrchestratorResult:

        step_definitions = [
            {"key": "analysis", "label": "Analisi"},
            {"key": "sql", "label": "SQL"},
            {"key": "execution", "label": "Esecuzione"},
            {"key": "enrichment", "label": "Arricchimento"},
            {"key": "evaluation", "label": "Valutazione"},
            {"key": "broker", "label": "Broker"},
            {"key": "merge", "label": "Finalizzazione"},
            {"key": "complete", "label": "Completato"},
        ]

        # Load metadata
        # Load metadata (lite version for token optimization)
        metadata_path = os.path.join("app", "data", "db_metadata_lite.json")
        db_metadata = {}
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    db_metadata = json.load(f)
            except Exception:
                # Fail silently on metadata load error
                pass

        # Extract lightweight metadata from base_dataset to avoid passing it in state
        dataset_metadata = {
            "columns": list(base_dataset.columns) if base_dataset is not None else [],
            "sample_columns": (
                ", ".join(base_dataset.columns[:15]) if base_dataset is not None else ""
            ),
            "typologies": [],
        }
        if (
            base_dataset is not None
            and "tipologia_bene_immobile" in base_dataset.columns
        ):
            dataset_metadata["typologies"] = [
                str(x)
                for x in base_dataset["tipologia_bene_immobile"].unique()
                if pd.notna(x)
            ]

        initial_state: GraphState = {
            "query": query,
            "dataset_key": dataset_key,
            # "base_dataset": base_dataset, # REMOVED
            "dataset_path": dataset_path,
            # "working_dataset": base_dataset, # REMOVED
            # "ape_df": ape_df, # REMOVED
            "db_schema": db_schema,
            "db_metadata": db_metadata,
            "dataset_metadata": dataset_metadata,
            "location_payload": [],
            "use_case_str": "",
            "metrics_plan": None,
            "typology_result": None,
            "sql_query": "",
            "selected_data": pd.DataFrame(),
            "execution_error": None,
            "retry_count": 0,
            "status_msg": "",
            "gemini_responses": {
                "analysis_mode": self.analysis_mode,
                "dataset_key": dataset_key,
            },
            "context": AgentContext(user_query=query),
            "where_clause": "",
            "broker_summary": "",
            "llm_limit": llm_limit,
            "map_limit": map_limit,
            "metro_graph": metro_graph,
            "analysis_mode": self.analysis_mode,
            "set_progress": set_progress,
            "step_definitions": step_definitions,
            "relax_constraints": False,
        }

        # Safe recursion limit to handle retry loops while preventing infinite loops
        final_state = self.workflow.invoke(initial_state, {"recursion_limit": 30})

        # Get results - finalize_results should have added is_evaluated
        result_df = final_state["selected_data"]

        # Ensure is_evaluated exists (safety check)
        if not result_df.empty and "is_evaluated" not in result_df.columns:
            logger.warning("is_evaluated column missing, adding default")
            result_df["is_evaluated"] = False

        # Optional JSON export for LLM analysis/debugging
        if settings.ENABLE_RUN_JSON_EXPORT:
            logger.info("JSON export enabled, attempting to save run...")
            try:
                # Generate unique run_id if not in state
                run_id = final_state.get("run_id", f"run_{int(time.time()*1000)}")
                logger.debug(f"Run ID: {run_id}")

                # Convert result_df to JSON-serializable format
                results_json = {
                    "buildings": (
                        result_df.to_dict(orient="records")
                        if not result_df.empty
                        else []
                    )
                }
                logger.debug(
                    f"Results prepared: {len(results_json['buildings'])} buildings"
                )

                # Log the run
                json_logger = get_run_logger()
                json_logger.log_run(
                    run_id=run_id,
                    query=query,
                    status="completed",
                    gemini_responses=final_state["gemini_responses"],
                    results=results_json,
                )
                logger.info("✅ Run successfully exported to JSON")
            except Exception as e:
                logger.error(f"Failed to export run to JSON: {e}")
                import traceback

                logger.error(traceback.format_exc())

        return OrchestratorResult(
            map_df=result_df,
            location=final_state["location_payload"],
            status_msg=final_state["status_msg"],
            gemini_responses=final_state["gemini_responses"],
            where_clause=final_state["where_clause"],
            context=final_state["context"],
            broker_summary=final_state.get("broker_summary", ""),
        )

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def _update_progress(self, state: GraphState, step_index: int, message: str):
        if state["set_progress"]:
            total_steps = len(state["step_definitions"])
            percent = step_index * 100 / total_steps

            # Build step states
            steps_state = []
            for idx, step in enumerate(state["step_definitions"], start=1):
                if idx < step_index:
                    s = "done"
                elif idx == step_index:
                    s = "current"
                else:
                    s = "pending"
                steps_state.append(
                    {
                        "label": step.get("label", f"Step {idx}"),
                        "state": s,
                        "detail": message if s == "current" else "",
                    }
                )

            state["set_progress"]((percent, steps_state))

    def _get_ape_statistics(self, dataset_path: str) -> dict:
        """Estrae statistiche APE per l'agente."""
        try:
            if not dataset_path or not os.path.exists(dataset_path):
                return {}

            # Read only columns needed for APE analysis to save memory
            df = pd.read_parquet(dataset_path, columns=APE_AGENT_COLUMNS)

            stats = {
                "total_records": len(df),
                "with_ape_data": int(df["classe_energetica_ape"].notna().sum()),
            }

            if stats["with_ape_data"] > 0:
                stats["percentage"] = round(
                    (stats["with_ape_data"] / stats["total_records"]) * 100, 1
                )

            for col in APE_AGENT_COLUMNS:
                if col not in df.columns:
                    continue

                if pd.api.types.is_numeric_dtype(df[col]):
                    valid_data = df[col].dropna()
                    if not valid_data.empty:
                        stats[col] = {
                            "min": round(float(valid_data.min()), 2),
                            "max": round(float(valid_data.max()), 2),
                            "mean": round(float(valid_data.mean()), 2),
                            "percentiles": {
                                "25%": round(float(valid_data.quantile(0.25)), 2),
                                "50%": round(float(valid_data.quantile(0.50)), 2),
                                "75%": round(float(valid_data.quantile(0.75)), 2),
                            },
                        }
                else:
                    # Categorie (es. Classe Energetica)
                    stats[col] = df[col].value_counts().head(10).to_dict()

            return stats
        except Exception as e:
            logger.error(f"Error calculating APE statistics: {e}")
            return {"error": str(e)}

    def _extract_categorical_values(self, db_metadata: dict) -> dict:
        """
        Extract categorical value lists for columns with discrete values.

        Returns:
            Dict mapping column names to list of possible values
        """
        categorical_columns = [
            "classe_energetica_ape",
            "tipologia_bene_immobile",
            "epoca_costruzione",
            "natura_del_bene",
            "utilizzo_del_bene",
            "finalita",
        ]

        categorical_values = {}

        for col in categorical_columns:
            if col in db_metadata and "values" in db_metadata[col]:
                categorical_values[col] = db_metadata[col]["values"]
            elif col == "classe_energetica_ape":
                # Hardcode energy classes if not in metadata
                categorical_values[col] = [
                    "A1",
                    "A2",
                    "A3",
                    "A4",
                    "B",
                    "C",
                    "D",
                    "E",
                    "F",
                    "G",
                ]

        return categorical_values

    def _analyze_request(self, state: GraphState) -> GraphState:
        self._update_progress(state, 1, "Analisi richiesta in parallelo...")
        query = state["query"]
        logger.info(f"Starting analysis for query: {query}")

        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating request analysis...")
            time.sleep(2)

            # Mock Typology
            state["typology_result"] = MOCK_TYPOLOGY
            state["context"].typology_result = MOCK_TYPOLOGY

            # Mock Location
            state["context"].locations = MOCK_LOCATION.places

            # Mock Strategy
            state["metrics_plan"] = MOCK_STRATEGY
            state["context"].metrics_plan = MOCK_STRATEGY
            state["use_case_str"] = "Mock Use Case Strategy"

            # Populate Gemini responses needed for UI
            state["gemini_responses"]["typology_extraction"] = {
                "response": MOCK_TYPOLOGY.raw_text,
                "typologies": MOCK_TYPOLOGY.typologies,
            }
            state["gemini_responses"]["location_extraction"] = {
                "response": MOCK_LOCATION.raw_text,
                "places": [p.model_dump() for p in MOCK_LOCATION.places],
            }
            state["gemini_responses"]["needs_metric_plan"] = {
                "response": MOCK_STRATEGY.raw_text,
                "plan": MOCK_STRATEGY.model_dump(),
            }

            # Fake payload for location
            state["location_payload"] = [
                [p.name, p.lat, p.lon] for p in MOCK_LOCATION.places
            ]

            return state

        dataset_metadata = state["dataset_metadata"]
        db_schema = state["db_schema"]

        # Prepare inputs
        sample_columns = dataset_metadata.get("sample_columns", "")

        # Define tasks
        def run_typology():
            # Pass metadata to typology agent if supported, otherwise just query
            return self.typology_agent.run(
                query=query,
                available_typologies=str(
                    state["db_metadata"]
                    .get("tipologia_bene_immobile", {})
                    .get("values", [])
                ),
            )

        def run_location():
            return self.location_agent.run(query=query)

        def run_strategy():
            if self.is_agent_mode:
                # Extract categorical values for better filter generation
                categorical_values = self._extract_categorical_values(
                    state["db_metadata"]
                )

                return self.needs_agent.run(
                    query=query,
                    db_schema=str(db_schema),
                    dataset_sample=sample_columns,
                    db_metadata=json.dumps(state["db_metadata"], ensure_ascii=False),
                    categorical_values=categorical_values,  # NEW
                )
            else:
                return self.use_case_agent.run(query=query, db_schema=str(db_schema))

        def run_ape():
            # Check keywords for classic mode or always run for agent mode if needed
            keywords = ["ape", "energetica", "classe", "consumo", "co2", "emissioni"]
            if self.is_agent_mode or any(k in query.lower() for k in keywords):
                # Calculate statistics
                ape_stats = self._get_ape_statistics(state.get("dataset_path"))
                # Pass stats and legend explicitly
                return self.ape_agent.run(
                    query=query,
                    columns=APE_AGENT_COLUMNS,
                    statistics=ape_stats,
                    score_legend=SCORE_LEGEND,
                )
            return None

        def run_poi():
            return self.poi_agent.run(query=query)

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_typology = executor.submit(run_typology)
            future_location = executor.submit(run_location)
            future_strategy = executor.submit(run_strategy)
            future_ape = executor.submit(run_ape)
            future_poi = executor.submit(run_poi)

            typology_result = future_typology.result()
            loc_result = future_location.result()
            strategy_result = future_strategy.result()
            ape_result = future_ape.result()
            poi_result = future_poi.result()

        # Process Typology
        state["typology_result"] = typology_result
        state["gemini_responses"]["typology_extraction"] = {
            "prompt": (
                typology_result.prompt.model_dump() if typology_result.prompt else None
            ),
            "response": typology_result.raw_text,
            "typologies": typology_result.typologies,
        }
        state["context"].typology_result = typology_result
        # REMOVED HARD FILTERING:
        # if typology_result.typologies:
        #     state["working_dataset"] = base_dataset[
        #         base_dataset['tipologia_bene_immobile'].isin(
        #             typology_result.typologies
        #         )
        #     ]

        # Process Location
        # Initialize locations in context (will be updated with coords below)
        state["context"].locations = loc_result.places
        state["gemini_responses"]["location_extraction"] = {
            "prompt": loc_result.prompt.model_dump() if loc_result.prompt else None,
            "response": loc_result.raw_text,
            "places": [p.model_dump() for p in loc_result.places],
        }

        location_payload = []
        if loc_result.places:

            def geocode_place(place):
                search_query = (
                    f"{place.name}, {place.city}" if place.city else place.name
                )
                try:
                    lat, lon = get_coordinates(search_query)
                except Exception:
                    lat, lon = None, None
                return search_query, lat, lon

            # Use ThreadPoolExecutor for parallel geocoding
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Map places to futures, preserving order
                futures = [executor.submit(geocode_place, p) for p in loc_result.places]

                for i, future in enumerate(futures):
                    search_query, lat, lon = future.result()

                    if lat is not None and lon is not None:
                        location_payload.append([search_query, lat, lon])
                        # Update context with coordinates for UI
                        if i < len(state["context"].locations):
                            state["context"].locations[i].lat = lat
                            state["context"].locations[i].lon = lon
                    else:
                        logger.warning(f"Could not geocode: {search_query}")

        # Contract: location is always a list; empty list means "no location".
        state["location_payload"] = location_payload

        # Process POI
        state["poi_result"] = poi_result
        state["gemini_responses"]["poi_analysis"] = {
            "prompt": poi_result.prompt.model_dump() if poi_result.prompt else None,
            "response": poi_result.raw_text,
            "weights": poi_result.poi_weights,
            "constraints": poi_result.constraints,
        }

        # Process Strategy & APE
        ape_text = ""
        if ape_result:
            state["gemini_responses"]["ape_analysis"] = {
                "prompt": ape_result.prompt.model_dump() if ape_result.prompt else None,
                "response": ape_result.raw_text,
                "answer": ape_result.answer,
            }
            ape_text = f"\n\nAnalisi APE: {ape_result.answer}"

        # Process POI Text for Context
        poi_text = ""
        if poi_result:
            high_priority = [k for k, v in poi_result.poi_weights.items() if v >= 0.6]
            poi_text = f"\n\nAnalisi POI: L'utente ha espresso preferenza per: {', '.join(high_priority)}."
            if poi_result.constraints.get("must_have"):
                poi_text += f" Vincoli stretti: {', '.join(poi_result.constraints['must_have'])}."

        if self.is_agent_mode:
            # strategy_result is NeedsMetricPlan
            plan = strategy_result

            # FORCE APE INTEGRATION: If ApeAgent has something to say, we include it.
            if ape_result:
                # Append to summary for context
                plan.summary += ape_text

                # Update the strategy object to ensure it's passed to Evaluation
                if not plan.ape_strategy.strategy:
                    plan.ape_strategy.strategy = ape_result.answer
                else:
                    plan.ape_strategy.strategy += f" | {ape_result.answer}"

                # Force flag to true so downstream logic knows to use it
                plan.ape_strategy.use_ape = True

            # FORCE POI INTEGRATION
            if poi_result:
                plan.summary += poi_text

            state["metrics_plan"] = plan
            state["context"].metrics_plan = plan
            state["gemini_responses"]["needs_metric_plan"] = {
                "prompt": plan.prompt.model_dump() if plan.prompt else None,
                "response": plan.raw_text,
                "plan": plan.model_dump(),
            }
            state["use_case_str"] = self._format_plan_for_evaluation(plan)
        else:
            # strategy_result is UseCaseResult
            use_case_result = strategy_result
            state["use_case_str"] = use_case_result.description + ape_text + poi_text
            state["gemini_responses"]["use_case_generation"] = {
                "prompt": (
                    use_case_result.prompt.model_dump()
                    if use_case_result.prompt
                    else None
                ),
                "response": use_case_result.raw_text,
                "description": use_case_result.description,
            }
            state["gemini_responses"]["use_case_generation"] = {
                "prompt": (
                    use_case_result.prompt.model_dump()
                    if use_case_result.prompt
                    else None
                ),
                "response": use_case_result.raw_text,
                "use_case": use_case_result.model_dump(),
            }
            state["use_case_str"] = (
                f"Descrizione: {use_case_result.description}\n"
                f"Target: {use_case_result.target_audience}\n"
                f"Metriche: {', '.join(use_case_result.key_metrics)}"
            ) + ape_text

        return state

    def _generate_sql(self, state: GraphState) -> GraphState:
        retry_count = state["retry_count"]
        self._update_progress(
            state, 4, f"Generazione SQL (tentativo {retry_count + 1})..."
        )

        query = state["query"]
        db_schema = state["db_schema"]
        location_payload = state["location_payload"]
        metrics_plan = state["metrics_plan"]
        failed_query = state["sql_query"] if retry_count > 0 else ""
        error_msg = state.get("execution_error")

        loc_obj = None
        if isinstance(location_payload, list) and location_payload:
            _, lat, lon = location_payload[0]
            loc_obj = {"lat": lat, "lon": lon}

        sql_prompt = self._augment_query_with_plan(
            query, metrics_plan, state.get("typology_result")
        )

        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating SQL generation...")
            time.sleep(1.5)
            state["sql_query"] = MOCK_SQL_QUERY
            state["gemini_responses"]["sql_generation"] = {
                "response": "Mock SQL generated",
                "sql_query": MOCK_SQL_QUERY,
            }
            return state

        if state.get("relax_constraints"):
            logger.info("Applying SMART RELAXATION to SQL prompt")
            sql_prompt += "\n\nATTENZIONE: La ricerca precedente ha prodotto 0 risultati. IL TUO OBIETTIVO ORA È TROVARE ALTERNATIVE. RILASSA I VINCOLI (es. espandi il range di prezzo, rimuovi filtri su piano o ascensore, allarga il raggio geografico). DEVI restituire qualcosa."

        if retry_count == 0:
            sql_result = self.sql_agent.run(
                query=sql_prompt,
                scheme=str(db_schema),
                location=loc_obj,
                db_metadata=json.dumps(state["db_metadata"], ensure_ascii=False),
            )
        else:
            sql_result = self.sql_agent.run(
                query=sql_prompt,
                scheme=str(db_schema),
                location=loc_obj,
                failed_query=failed_query,
                error_msg=error_msg,
                db_metadata=json.dumps(state["db_metadata"], ensure_ascii=False),
            )

        state["sql_query"] = sql_result.sql_query
        key = (
            "sql_generation"
            if retry_count == 0
            else f"sql_generation_retry_{retry_count}"
        )
        state["gemini_responses"][key] = {
            "prompt": sql_result.prompt.model_dump() if sql_result.prompt else None,
            "response": sql_result.raw_text,
            "sql_query": sql_result.sql_query,
        }
        return state

    def _execute_sql(self, state: GraphState) -> GraphState:
        self._update_progress(state, 5, "Esecuzione query...")
        sql_query = state["sql_query"]
        dataset_path = state.get("dataset_path")

        logger.info(f"Executing SQL: {sql_query}")
        # Pass None as working_dataset, rely on dataset_path and DuckDB
        selected_data, error = self.execute_sql_fn(
            sql_query, None, dataset_path=dataset_path
        )

        if error:
            logger.error(f"SQL Execution Error: {error}")
        else:
            logger.info(f"SQL returned {len(selected_data)} rows")

        state["selected_data"] = selected_data
        state["execution_error"] = error
        return state

    def _check_sql_execution(self, state: GraphState) -> str:
        if state.get("execution_error"):
            if state["retry_count"] < 5:
                logger.warning(
                    f"Retrying due to error (Attempt {state['retry_count'] + 1})"
                )
                return "retry"
            logger.error("Max retries reached with error. Activating fallback.")
            return "fallback"

        if not state["selected_data"].empty:
            return "continue"

        if state["retry_count"] < 5:
            logger.warning(
                f"Retrying due to empty results (Attempt {state['retry_count'] + 1})"
            )
            return "retry_relax"

        logger.warning("Max retries reached with empty results. Activating fallback.")
        return "fallback"

    def _handle_retry(self, state: GraphState) -> GraphState:
        # Check if we need to relax constraints based on the edge that brought us here
        # LangGraph doesn't pass edge metadata easily, but we can infer or use specific nodes.
        # However, since we use the same handle_retry node, we can just check the previous state logic
        # OR we can make _check_sql_execution return different edges.

        # Simplified: If selected_data is empty and no error, it's a relaxation retry
        relax = False
        if not state.get("execution_error") and state["selected_data"].empty:
            relax = True

        return {"retry_count": state["retry_count"] + 1, "relax_constraints": relax}

    def _fallback_results(self, state: GraphState) -> GraphState:
        """
        Fallback when SQL queries fail after max retries.
        Returns top results from full dataset so user always gets something.
        """
        self._update_progress(
            state, 5, "Nessun risultato trovato. Generazione alternative..."
        )
        logger.warning("Fallback activated: loading top results from full dataset")

        dataset_path = state.get("dataset_path")
        if not dataset_path:
            logger.error("No dataset path for fallback")
            state["status_msg"] = "Errore: impossibile generare alternative."
            return state

        try:
            full_df = pd.read_parquet(dataset_path)
            logger.info(f"Fallback loaded {len(full_df)} rows from dataset")

            # Get user location if available for sorting
            user_location = None
            loc_payload = state.get("location_payload")
            if isinstance(loc_payload, list) and len(loc_payload) > 0:
                try:
                    user_location = (float(loc_payload[0][1]), float(loc_payload[0][2]))
                except Exception:
                    pass

            # Sort by best APE score, or by distance if location available
            if (
                user_location
                and "latitudine" in full_df.columns
                and "longitudine" in full_df.columns
            ):
                # Calculate distance for sorting
                lat, lon = user_location
                full_df["_fallback_dist"] = np.sqrt(
                    (full_df["latitudine"] - lat) ** 2
                    + (full_df["longitudine"] - lon) ** 2
                )
                fallback_df = full_df.nsmallest(500, "_fallback_dist")
                fallback_df = fallback_df.drop(columns=["_fallback_dist"])
            elif "ape_score_total" in full_df.columns:
                # Sort by APE score (higher is better)
                fallback_df = full_df.nlargest(500, "ape_score_total")
            else:
                # Random sample as last resort
                fallback_df = full_df.sample(min(500, len(full_df)))

            state["selected_data"] = fallback_df
            state["gemini_responses"]["fallback_activated"] = True
            state["status_msg"] = (
                "Nessun risultato trovato con i criteri specificati. "
                "Mostro alternative suggerite."
            )
            logger.info(f"Fallback returning {len(fallback_df)} results")

        except Exception as e:
            logger.error(f"Fallback failed: {e}")
            state["status_msg"] = f"Errore durante la generazione di alternative: {e}"

        return state

    def _enrich_results(self, state: GraphState) -> GraphState:
        self._update_progress(state, 6, "Arricchimento dati...")
        selected_data = state["selected_data"]
        sql_query = state["sql_query"]
        location_payload = state["location_payload"]
        dataset_path = state.get("dataset_path")

        # Post-processing similar to OrchestratorAgent
        try:
            parsed = sqlparse.parse(sql_query)[0]
            state["where_clause"] = next(
                (
                    str(token)
                    for token in parsed.tokens
                    if isinstance(token, sqlparse.sql.Where)
                ),
                "Nessuna clausola WHERE trovata.",
            )
        except Exception:
            state["where_clause"] = "Nessuna clausola WHERE trovata."

        # ============================================================
        # CRITICAL: LEFT JOIN with full dataset to recover ALL columns
        # SQL might only select specific columns, but we need everything
        # for the UI (surface_area, meta_immobile, ape_scores, etc.)
        # ============================================================
        if dataset_path and not selected_data.empty and "id" in selected_data.columns:
            try:
                full_df = pd.read_parquet(dataset_path)
                logger.info(
                    f"Enrichment: merging {len(selected_data)} SQL results with "
                    f"{len(full_df)} full dataset rows"
                )

                # Ensure ID is string for matching
                selected_data["id"] = selected_data["id"].astype(str)
                full_df["id"] = full_df["id"].astype(str)

                # Get columns only in full_df (not in selected_data)
                sql_columns = set(selected_data.columns)
                full_columns = set(full_df.columns)
                missing_columns = full_columns - sql_columns

                if missing_columns:
                    # Only merge the missing columns (more efficient)
                    merge_columns = ["id"] + list(missing_columns)
                    full_subset = full_df[merge_columns].drop_duplicates(subset=["id"])

                    # LEFT JOIN: preserve all SQL rows, add missing columns
                    selected_data = selected_data.merge(
                        full_subset, on="id", how="left"
                    )
                    logger.info(
                        f"Enrichment: added {len(missing_columns)} missing columns"
                    )

            except Exception as e:
                logger.warning(f"Failed to enrich with full dataset: {e}")
                # Continue with whatever data we have

        # 1. Calculate travel times on the SELECTED subset first (for performance)
        location_list = location_payload if isinstance(location_payload, list) else []

        if location_list:
            # Enrich with direct Haversine distance (distanza_km) for ranking & filters
            selected_data = calculate_travel_times_df(selected_data, location_list)

        # 2. Mark as matched
        enriched_data = selected_data.copy()
        enriched_data["is_match"] = True

        if "distanza_km" not in enriched_data.columns:
            enriched_data["distanza_km"] = np.nan

        state["context"].filtered_dataset_preview = enriched_data.head(10).to_dict(
            "records"
        )
        return state

    def _extract_search_radius(self, sql_query: str) -> float:
        """Extract search radius from SQL WHERE clause (e.g., '< 15' -> 15.0)."""
        import re

        if not sql_query:
            return 5.0

        # Look for pattern like: haversine_km(...) < 15
        match = re.search(
            r"haversine_km.*?<\s*(\d+(?:\.\d+)?)", sql_query, re.IGNORECASE
        )
        return float(match.group(1)) if match else 5.0

    def _calculate_component_weights(
        self, metrics_plan: Optional[NeedsMetricPlan], user_location: tuple = None
    ) -> dict:
        """
        Calculate ranking component weights from NeedsMetricAgent metrics.

        Returns:
            dict with keys: ape_weight, poi_weight_factor, distance_weight
        """
        if not metrics_plan or not metrics_plan.metrics:
            # Fallback to defaults
            return {
                "ape_weight": 0.2,
                "poi_weight_factor": 0.4,
                "distance_weight": 0.4 if user_location else 0.0,
            }

        # Sum weights by category based on metric names
        ape_related = sum(
            m.weight
            for m in metrics_plan.metrics
            if any(
                kw in m.name.lower()
                for kw in [
                    "efficienza",
                    "ape",
                    "energetica",
                    "energetico",
                    "isolamento",
                    "involucro",
                    "impianto",
                    "rinnovabili",
                    "classe",
                    "consumo",
                ]
            )
        )

        poi_related = sum(
            m.weight
            for m in metrics_plan.metrics
            if any(
                kw in m.name.lower()
                for kw in [
                    "sanita",
                    "mobilita",
                    "verde",
                    "sport",
                    "commerciale",
                    "educazione",
                    "servizi",
                    "trasporti",
                    "scuole",
                    "ospedali",
                    "negozi",
                ]
            )
        )

        # Distance gets weight only if location is specified
        distance_base = 0.3 if user_location else 0.0

        # Normalize to sum to 1.0
        total = ape_related + poi_related + distance_base
        if total == 0:
            # No specific metrics → balanced defaults
            return {
                "ape_weight": 0.3,
                "poi_weight_factor": 0.3,
                "distance_weight": 0.4 if user_location else 0.0,
            }

        return {
            "ape_weight": ape_related / total if total > 0 else 0.2,
            "poi_weight_factor": poi_related / total if total > 0 else 0.3,
            "distance_weight": distance_base / total if total > 0 else 0.4,
        }

    def _rank_results(self, state: GraphState) -> GraphState:
        self._update_progress(state, 6, "Ranking intelligente dei risultati...")
        df = state["selected_data"]
        poi_result = state.get("poi_result")
        metrics_plan = state.get("metrics_plan")

        if df is None or df.empty:
            return state

        # Extract user location if available
        user_location = None
        loc_payload = state.get("location_payload")
        if isinstance(loc_payload, list) and len(loc_payload) > 0:
            # Take the first location found
            # Format: [name, lat, lon]
            try:
                user_location = (float(loc_payload[0][1]), float(loc_payload[0][2]))
            except Exception:
                pass

        # Extract weights
        poi_weights = poi_result.poi_weights if poi_result else {}

        # Extract search radius from SQL query
        search_radius = self._extract_search_radius(state.get("sql_query", ""))

        # Calculate component weights dynamically from NeedsMetricAgent output
        weights = self._calculate_component_weights(metrics_plan, user_location)

        # Calculate ranking with dynamic weights and adaptive distance
        ranked_df = calculate_ranking_score(
            df,
            poi_weights=poi_weights,
            user_location=user_location,
            search_radius_km=search_radius,
            ape_weight=weights["ape_weight"],
            poi_weight_factor=weights["poi_weight_factor"],
            distance_weight=weights["distance_weight"],
        )

        state["selected_data"] = ranked_df
        return state

    def _evaluate_results(self, state: GraphState) -> GraphState:
        enriched_data = state["selected_data"]

        llm_cap = self._resolve_llm_cap(state["llm_limit"], state["metrics_plan"])

        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating Evaluation...")
            self._update_progress(
                state, 7, f"Avvio valutazione qualitativa simulata..."
            )
            time.sleep(1)

            # Create fake evaluation results matching selected IDs if possible, or just generic
            # For mocks, we just reuse the static mock data but adapted to ID?
            # Actually, we need to make sure IDs match.
            # Let's just use the MOCK_EVALUATION results as is.
            # IMPORTANT: To make it work with the map, we need IDs that exist in the DB.
            # If we use random IDs, they won't join with the map.
            # So we should rely on what execute_sql returned in MOCK mode.
            # Wait, _execute_sql runs normally even in mock mode? Yes, MOCK_SQL_QUERY is a real query.
            # So selected_data will have real rows.
            # We should evaluate THOSE rows.
            # For Mock mode, we'll just generate fake evaluations for the top 3 rows of selected_data.

            eval_results = []
            if not enriched_data.empty:
                for idx, row in enriched_data.head(3).iterrows():
                    item_id = row.get("id", idx)
                    # Cycle through mock results
                    mock_res = MOCK_EVALUATION.results[idx % 2]
                    # Clone and set ID
                    res = mock_res.model_copy()
                    res.id = item_id
                    eval_results.append(res)
                    time.sleep(0.5)  # Simulate per-item delay
                    self._update_progress(
                        state,
                        7,
                        f"Analisi simulata {idx+1}/{min(3, len(enriched_data))}",
                    )

            state["context"].evaluation_results = eval_results
            if "evaluation" not in state["gemini_responses"]:
                state["gemini_responses"]["evaluation"] = {}
            state["gemini_responses"]["evaluation"]["results"] = [
                r.model_dump() for r in eval_results
            ]

            self._update_progress(
                state,
                4,
                f"Valutazione completata: {len(eval_results)} risultati generati.",
            )
            return state

        eval_input_df = enriched_data.head(llm_cap).copy()
        eval_input_df["is_evaluated"] = True

        total_items = len(eval_input_df)
        self._update_progress(
            state,
            7,
            f"Avvio valutazione qualitativa su {total_items} immobili candidati...",
        )

        # Batch processing
        batch_size = 5
        batches = [
            eval_input_df[i : i + batch_size]
            for i in range(0, len(eval_input_df), batch_size)
        ]

        all_results = []
        total_batches = len(batches)
        finished_batches = 0

        # Columns relevant for LLM evaluation (reduced set for clarity and token efficiency)
        EVAL_COLUMNS = [
            "id",
            "indirizzo",
            "numero_civico",
            "zona_omi",
            "superficie_di_riferimento_mq",
            "tipologia_bene_immobile",
            "epoca_costruzione",
            "utilizzo_del_bene",
            "finalita",
            # APE data
            "classe_energetica_ape",
            "ape_score_classe",
            "ape_score_impianto",
            "ape_score_involucro",
            "ape_score_rinnovabili",
            "ape_score_total",
            # POI scores
            "sanita",
            "mobilita",
            "verde",
            "sport",
            "commerciale",
            "educazione",
            # Travel times (if enriched)
            "tempo_minuti",
            "distanza_km",
        ]

        def prepare_estates_json(batch_df: pd.DataFrame) -> str:
            """Convert DataFrame to JSON with only relevant columns for LLM evaluation."""
            # Select only columns that exist in the dataframe
            available_cols = [c for c in EVAL_COLUMNS if c in batch_df.columns]
            subset = batch_df[available_cols].copy()

            # Convert to list of dicts
            records = subset.to_dict(orient="records")

            # Clean up NaN/None values to "N/D" for readability
            for record in records:
                for key, val in list(record.items()):
                    # Check for None, NaN (float), or pandas NA
                    if val is None or (isinstance(val, float) and np.isnan(val)):
                        record[key] = "N/D"

            return json.dumps(records, indent=2, ensure_ascii=False)

        def process_batch(batch_df):
            if batch_df.empty:
                return []

            # Use JSON format instead of tabulate for better LLM comprehension
            # The `eval_input_df` is already capped by `llm_cap` (now 10)
            # and `batch_df` is a slice of `eval_input_df`.
            # So, `estates_data_str` already represents a subset of the top `llm_cap` results.
            estates_data_str = prepare_estates_json(batch_df)

            logger.info(f"Evaluating batch of {len(batch_df)} items")
            eval_payload: EvaluationAgentResponse = self.evaluation_agent.run(
                use_case=state["use_case_str"],
                estates_data=estates_data_str,
                original_query=state["query"],  # NEW: pass original query for context
                score_legend=SCORE_LEGEND,
            )
            return eval_payload

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(process_batch, batch): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(futures):
                try:
                    payload = future.result()
                    finished_batches += 1
                    # Update progress dynamically for each batch
                    self._update_progress(
                        state,
                        7,
                        f"Analizzando batch {finished_batches}/{total_batches} con {len(payload.results) if payload and payload.results else 0} valutazioni...",
                    )

                    if payload and payload.results:
                        all_results.extend(payload.results)
                        # We keep the last prompt/response for logging purposes
                        state["gemini_responses"]["evaluation"] = {
                            "prompt": (
                                payload.prompt.model_dump() if payload.prompt else None
                            ),
                            "response": payload.raw_text,
                            "results_count": len(all_results),
                        }
                except Exception:
                    # Log error silently or use a proper logger
                    pass

        state["context"].evaluation_results = all_results
        # Update full results list in log
        if "evaluation" in state["gemini_responses"]:
            state["gemini_responses"]["evaluation"]["results"] = [
                res.model_dump() for res in all_results
            ]

        self._update_progress(
            state, 4, f"Valutazione completata: {len(all_results)} risultati generati."
        )
        return state

    def _broker_review(self, state: GraphState) -> GraphState:
        self._update_progress(state, 5, "Analisi esperta (Senior Broker)...")

        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating Broker Review...")
            time.sleep(1.5)
            state["broker_summary"] = MOCK_BROKER_SUMMARY
            state["gemini_responses"]["broker_review"] = MOCK_BROKER_SUMMARY
            return state

        eval_results = state["context"].evaluation_results

        if not eval_results:
            state["broker_summary"] = "Nessun immobile analizzato in dettaglio."
            return state

        # Create structured text for the broker
        candidates = []
        for i, res in enumerate(eval_results[:5]):  # Analyze top 5 max
            candidates.append(
                f"Candidato #{i+1} (ID: {res.id}, Score: {res.score}):\n"
                f"Motivazione: {res.evaluation_text}\n"
                f"Pro: {', '.join(res.pros)}\n"
                f"Contro: {', '.join(res.cons)}\n"
            )

        candidates_text = "\n---\n".join(candidates)

        summary = self.evaluation_agent.run_synthesis(
            query=state["query"], candidates_data=candidates_text
        )

        state["broker_summary"] = summary
        state["gemini_responses"]["broker_review"] = summary
        return state

    def _finalize_results(self, state: GraphState) -> GraphState:
        self._update_progress(state, 6, "Finalizzazione...")

        if state["selected_data"].empty:
            state["status_msg"] = (
                "La ricerca non ha prodotto risultati specifici. Mostro un campione di immobili."
            )

            # Fallback: Fetch a sample from DuckDB since working_dataset is not in state
            dataset_path = state.get("dataset_path")
            fallback_query = "SELECT * FROM IMMOBILI LIMIT 500"
            # Use execute_sql_fn to get data
            fallback_data, _ = self.execute_sql_fn(
                fallback_query, None, dataset_path=dataset_path
            )

            full_df = fallback_data
            full_df["is_match"] = False
            full_df["score"] = 0
            full_df["is_selected_by_llm"] = False
            full_df["is_evaluated"] = False

            if "distanza_km" not in full_df.columns:
                full_df["distanza_km"] = np.nan

            state["selected_data"] = full_df
            state["context"].filtered_dataset_preview = []
            state["gemini_responses"]["agent_context"] = state["context"].model_dump()
            state["gemini_responses"]["agent_context"] = state["context"].model_dump()
            self._update_progress(state, 7, "Completato (Nessun risultato filtrato).")
            return state

        # Dati arricchiti dal percorso agente (solo subset selezionato dalla query)
        enriched_data = state["selected_data"]
        map_cap = self._resolve_map_cap(state["map_limit"])
        llm_cap = self._resolve_llm_cap(state["llm_limit"], state["metrics_plan"])

        # Carica SEMPRE il dataset completo da DuckDB/IMMOBILI per la mappa,
        # così l'esperto può vedere tutti gli edifici (fino al limite mappa),
        # indipendentemente da come l'agente ha filtrato i candidati.
        base_df: Optional[pd.DataFrame] = None
        dataset_path = state.get("dataset_path")
        try:
            if dataset_path:
                base_df, _ = self.execute_sql_fn(
                    "SELECT * FROM IMMOBILI", None, dataset_path=dataset_path
                )
        except Exception as e:
            logger.warning(
                f"Impossibile caricare il dataset completo per la mappa; "
                f"uso il solo subset arricchito. Dettagli: {e}"
            )
            base_df = None

        if base_df is None or base_df.empty:
            # Fallback: mantieni il comportamento precedente (solo subset arricchito)
            base_df = enriched_data.copy()

        map_df = base_df.copy()

        # Normalizza ID per i merge
        if "id" in map_df.columns:
            map_df["id"] = map_df["id"].astype(str)
        if "id" in enriched_data.columns:
            enriched_data = enriched_data.copy()
            enriched_data["id"] = enriched_data["id"].astype(str)

        # Sovrascrivi/aggiungi colonne di matching e ranking solo dove l'agente ha lavorato
        overlay_cols = [
            col
            for col in ["id", "is_match", "ranking_score", "distanza_km"]
            if col in enriched_data.columns
        ]
        if overlay_cols:
            overlay_df = enriched_data[overlay_cols].drop_duplicates("id")
            map_df = pd.merge(
                map_df, overlay_df, on="id", how="left", suffixes=("", "_ann")
            )

        # Default robusti per flag e score
        if "is_match" not in map_df.columns:
            map_df["is_match"] = False
        map_df["is_match"] = map_df["is_match"].fillna(False).astype(bool)

        if "ranking_score" in map_df.columns:
            map_df["ranking_score"] = pd.to_numeric(
                map_df["ranking_score"], errors="coerce"
            ).fillna(0)

        eval_results = state["context"].evaluation_results
        total_count = len(map_df)
        evaluated_total = 0

        if eval_results:
            # Costruisci DataFrame con le valutazioni LLM (solo per gli ID valutati)
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

            if not valutazioni_df.empty and "id" in map_df.columns:
                valutazioni_df["id"] = valutazioni_df["id"].astype(str)
                evaluated_total = len(valutazioni_df)

                map_df = pd.merge(
                    map_df,
                    valutazioni_df[
                        ["id", "score", "motivazione", "pro", "contro"]
                    ].drop_duplicates("id"),
                    on="id",
                    how="left",
                )

                map_df["score"] = pd.to_numeric(
                    map_df["score"], errors="coerce"
                ).fillna(0)
                map_df["is_evaluated"] = map_df["id"].isin(valutazioni_df["id"])
                map_df["is_selected_by_llm"] = map_df["score"] >= 60
            else:
                map_df["score"] = 0
                map_df["is_evaluated"] = False
                map_df["is_selected_by_llm"] = False
        else:
            eval_ids = (
                enriched_data.head(llm_cap)["id"]
                if "id" in enriched_data.columns and llm_cap > 0
                else []
            )
            if "id" in map_df.columns:
                map_df["is_evaluated"] = map_df["id"].isin(eval_ids)
            else:
                map_df["is_evaluated"] = False
            map_df["score"] = 0
            map_df["is_selected_by_llm"] = False

        # Normalizza flag booleani
        for col in ["is_evaluated", "is_selected_by_llm"]:
            if col in map_df.columns:
                map_df[col] = map_df[col].fillna(False).astype(bool)

        # Ordina: prima i risultati che matchano la query, poi ranking/ distanza
        sort_cols = []
        ascending = []
        if "is_match" in map_df.columns:
            sort_cols.append("is_match")
            ascending.append(False)
        if "ranking_score" in map_df.columns:
            sort_cols.append("ranking_score")
            ascending.append(False)
        if "distanza_km" in map_df.columns:
            sort_cols.append("distanza_km")
            ascending.append(True)

        if sort_cols:
            map_df = map_df.sort_values(sort_cols, ascending=ascending)

        # Applica il limite mappa globale (MAX_ITEMS_FOR_MAP o override utente)
        if len(map_df) > map_cap:
            map_df = map_df.head(map_cap)

        # Costruisci messaggio di stato coerente con i limiti applicati
        shown_count = len(map_df)
        evaluated_in_map = (
            int(map_df["is_evaluated"].sum()) if "is_evaluated" in map_df.columns else 0
        )
        selected_in_map = (
            int(map_df["is_selected_by_llm"].sum())
            if "is_selected_by_llm" in map_df.columns
            else 0
        )

        if evaluated_total > 0:
            msg = (
                f"Trovati {total_count} risultati (mostrati {shown_count} per limite mappa {map_cap}). "
                f"LLM ha valutato {evaluated_total}/{llm_cap} elementi. "
                f"Valutati visibili in mappa: {evaluated_in_map}. "
                f"Selezionati in mappa: {selected_in_map}"
            )
        else:
            msg = (
                f"Trovati {total_count} risultati (mostrati {shown_count} per limite mappa {map_cap}). "
                "Nessuna valutazione LLM disponibile."
            )

        state["status_msg"] = msg
        logger.info(msg)

        state["selected_data"] = map_df  # Risultato finale per la mappa
        state["gemini_responses"]["agent_context"] = state["context"].model_dump()
        self._update_progress(state, 8, "Completato.")
        return state

    # ------------------------------------------------------------------
    # Helpers (Copied from OrchestratorAgent)
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
        self,
        query: str,
        plan: Optional[NeedsMetricPlan],
        typology_result: Optional[TypologyAgentResult] = None,
    ) -> str:
        plan_text = ""
        if self.is_agent_mode and plan:
            filter_list = plan.dataset_strategy.filters or []
            filters = "\n".join(filter_list) if filter_list else ""
            metrics = "\n".join(
                f"- {metric.name}: {metric.goal or ''} (peso {metric.weight})"
                for metric in plan.metrics
            )
            notes = plan.dataset_strategy.notes or "Nessuna"
            ape_note = plan.ape_strategy.strategy or ""
            ape_status = (
                "usa dati APE" if plan.ape_strategy.use_ape else "APE opzionale"
            )
            filter_summary = ", ".join(filter_list) or "Nessuno"
            plan_text = (
                f"OBIETTIVO: {plan.summary}\n"
                f"METRICHE:\n{metrics or '- non specificate'}\n"
                f"FILTRI:\n{filters or '- nessuno suggerito'}\n"
                f"ORDINAMENTO: {plan.dataset_strategy.sort_by or 'non specificato'}\n"
                f"NOTE: {notes}\n"
                f"APE: {ape_status} - {ape_note}\n"
                f"FILTRI SUGGERITI: {filter_summary}\n"
                f"TOP_K: {plan.dataset_strategy.top_k or 'default'}\n"
            )

        typology_text = ""
        if typology_result and typology_result.typologies:
            joined_typologies = ", ".join(typology_result.typologies)
            typology_text = (
                "\n\nTIPOLOGIE SUGGERITE (Filtra SOLO se coerente con la richiesta):\n"
                f"{joined_typologies}"
            )

        # SQL generation instructions - respect NeedsMetric filters
        sql_instructions = (
            "\n\nISTRUZIONI PER GENERAZIONE SQL:\n"
            "1. APPLICA i filtri suggeriti nel piano metriche (vedi FILTRI SUGGERITI sopra).\n"
            "2. NON filtrare su campi soft/descrittivi: 'utilizzo_del_bene', 'finalita', 'stato_manutentivo'.\n"
            "3. Se la query implica un cambio d'uso, ignora l'uso attuale nei filtri.\n"
            "4. Il ranking successivo farà la selezione fine, ma applica vincoli hard essenziali."
        )

        return (
            f"{query} \n\nPiano di metriche e strategia:\n"
            f"{plan_text}{typology_text}{sql_instructions}"
        )

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
