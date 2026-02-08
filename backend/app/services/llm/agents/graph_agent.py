from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union

from langgraph.graph import END, StateGraph
import numpy as np
import pandas as pd
import sqlparse
import sqlparse.tokens
import tabulate
import sqlglot
from sqlglot import exp, parse_one

from app.services.analysis.ranking import calculate_ranking_score
from app.core.config import settings
from app.core.constants import SCORE_LEGEND, APE_SCORE_LEGEND, APE_AGENT_COLUMNS, NORMATIVE_AGENT_COLUMNS, POI_AGENT_COLUMNS, TYPOLOGY_AGENT_COLUMNS

MAX_ITEMS_FOR_LLM = settings.MAX_ITEMS_FOR_LLM
MAX_ITEMS_FOR_MAP = settings.MAX_ITEMS_FOR_MAP
MAX_LLM_CAP = settings.MAX_LLM_CAP
USE_MOCK_RESPONSES = settings.USE_MOCK_RESPONSES
from app.data.loaders import get_coordinates
from app.data.processors import calculate_travel_times_df
from app.services.llm.agents.ape_agent import ApeAgent
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.broker_agent import BrokerAgent
from app.services.llm.agents.evaluation_agent import EvaluationAgent
from app.services.llm.agents.location_agent import LocationAgent
from app.services.llm.agents.normative_agent import NormativeAgent
from app.services.llm.agents.poi_agent import PoiAgent
from app.services.llm.agents.schema import (
    AgentContext,
    EvaluationAgentResponse,
    NormativeAgentResult,
    TypologyAgentResult,
    RankingAgentResult,
    RankingWeights,
    NormativeResponse,
    TypologyResponse,
    LocationResponse,
    ApeResponse,
    EvaluationResult,
    EvaluationList,
)
from app.services.llm.agents.sql_agent import SQLAgent
from app.services.llm.agents.typology_agent import TypologyAgent
from app.services.llm.agents.ranking_agent import RankingAgent
from app.utils.logger import logger
from app.utils.json_parser import safe_extract_json
from app.services.llm.mocks import (
    MOCK_TYPOLOGY,
    MOCK_LOCATION,
    MOCK_SQL_QUERY,
    MOCK_EVALUATION,
    MOCK_BROKER_SUMMARY,
)
from app.utils.run_json_logger import get_run_logger
from dataclasses import dataclass


@dataclass
class OrchestratorResult:
    map_df: pd.DataFrame
    location: List[List[Union[str, float]]]
    status_msg: str
    gemini_responses: Dict[str, Any]
    where_clause: str
    context: AgentContext
    broker_summary: Optional[str] = None
    agent_trace: Optional[List[Dict[str, Any]]] = None


class GraphState(TypedDict):
    query: str
    dataset_key: str
    base_dataset: Any  # ADDED: Reference to dataset DataFrame for APE stats
    dataset_path: Optional[str]  # Path to parquet file
    db_schema: Dict[str, Any]
    db_metadata: Dict[str, Any]  # New field for metadata
    dataset_metadata: Dict[
        str, Any
    ]  # New field for lightweight metadata (columns, typologies)

    # Intermediate
    location_payload: List[List[Union[str, float]]]
    use_case_str: str
    use_case_str: str
    # metrics_plan has been removed as part of clean architecture refactor
    typology_result: Optional[TypologyAgentResult]
    poi_result: Optional[Any]
    ape_result: Optional[Any]
    normative_result: Optional[NormativeAgentResult]
    ranking_result: Optional[RankingAgentResult]
    sql_query: str
    selected_data: Any  # pd.DataFrame
    execution_error: Optional[str]
    retry_count: int
    status_msg: str
    gemini_responses: Dict[str, Any]
    context: AgentContext
    where_clause: str
    broker_summary: str  # Executive summary from Senior Broker
    sql_history: List[str]  # History of all SQL queries tried (initial + relaxations)

    agent_trace: List[Dict[str, Any]]
    
    # Config
    llm_limit: Optional[int]
    map_limit: Optional[int]
    metro_graph: Any
    analysis_mode: str

    # Progress callback
    set_progress: Optional[Callable[[Any], None]]
    step_definitions: List[Dict[str, str]]
    relax_constraints: bool  # Flag for smart relaxation
    last_retry_reason: Optional[str]  # Why we are retrying (error or few_results)

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
        sql_agent: Optional[SQLAgent] = None,
        evaluation_agent: Optional[EvaluationAgent] = None,
        typology_agent: Optional[TypologyAgent] = None,
        ape_agent: Optional[ApeAgent] = None,
        poi_agent: Optional[PoiAgent] = None,
        normative_agent: Optional[NormativeAgent] = None,
    ) -> None:
        if execute_sql_fn is None:
            raise ValueError("execute_sql_fn is required.")

        self.analysis_mode = (analysis_mode or "agent").lower()
        self.is_agent_mode = self.analysis_mode == "agent"
        self.execute_sql_fn = execute_sql_fn

        self.location_agent = location_agent or LocationAgent()
        self.sql_agent = sql_agent or SQLAgent()
        self.evaluation_agent = evaluation_agent or EvaluationAgent()
        self.broker_agent = BrokerAgent()
        self.typology_agent = typology_agent or TypologyAgent()
        self.ape_agent = ape_agent or ApeAgent()
        self.poi_agent = poi_agent or PoiAgent()
        self.normative_agent = normative_agent or NormativeAgent()
        self.ranking_agent = RankingAgent()

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
        workflow.add_node("calculate_ranking_weights", self._calculate_ranking_weights)
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
        workflow.add_edge("enrich_results", "calculate_ranking_weights")
        workflow.add_edge("calculate_ranking_weights", "rank_results")
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
            {"key": "ranking", "label": "Ranking"},
            {"key": "evaluation", "label": "Valutazione"},
            {"key": "broker", "label": "Broker"},
            {"key": "merge", "label": "Finalizzazione"},
            {"key": "complete", "label": "Completato"},
        ]

        # Load metadata
        # Load metadata (lite version for token optimization)
        # Try multiple paths to be robust against CWD
        metadata_paths = [
            os.path.join("app", "data", "db_metadata_lite.json"),
            os.path.join("backend", "app", "data", "db_metadata_lite.json"),
            os.path.join(os.path.dirname(__file__), "../../../data/db_metadata_lite.json")
        ]
        
        db_metadata = {}
        for path in metadata_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        db_metadata = json.load(f)
                    break
                except Exception:
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
            "agent_trace": [],
            "query": query,
            "dataset_key": dataset_key,
            "base_dataset": base_dataset,  # ADDED: Keep reference to dataset for APE stats
            "dataset_path": dataset_path,
            "db_schema": db_schema,
            "db_metadata": db_metadata,
            "dataset_metadata": dataset_metadata,
            "location_payload": [],
            "use_case_str": "",
            "use_case_str": "",
            # metrics_plan removed
            "typology_result": None,
            "poi_result": None,
            "ape_result": None,
            "normative_result": None,
            "ranking_result": None,
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
            "last_retry_reason": None,
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
            agent_trace=final_state.get("agent_trace", []),
        )

    def _log_execution(self, state: GraphState, agent_name: str, result: Any, duration_ms: float, mode: str = "filtering"):
        """Logs agent execution to the trace with structured input/output extraction."""
        if "agent_trace" not in state:
            state["agent_trace"] = []
            
        # Extract input from prompt record
        input_data = None
        if hasattr(result, 'prompt') and result.prompt:
            prompt = result.prompt
            if hasattr(prompt, 'model_dump'):
                prompt_dict = prompt.model_dump()
                # Prefer full_text if available, otherwise system/user
                if prompt_dict.get('full_text'):
                    input_data = prompt_dict['full_text']
                elif prompt_dict.get('system') or prompt_dict.get('user'):
                    input_data = prompt_dict
                else:
                    input_data = prompt_dict
            else:
                input_data = str(prompt)
        
        # Extract output based on agent type and mode
        output_data = None
        
        # Handle DataFrame results from ranking mode
        if isinstance(result, pd.DataFrame):
            # For ranking mode DataFrames, convert to list of records for table display
            # Limit to first 20 rows for readability
            df_preview = result.head(20)
            output_data = json.loads(df_preview.to_json(orient="records"))
            input_data = f"Ranking mode: {len(result)} records scored"
        elif agent_name.lower() == "ape-agent" and hasattr(result, 'suggested_filters'):
            output_data = result.suggested_filters
        elif agent_name == "ranking-agent":
            # For ranking agent, prefer the ordered ranking if present, otherwise weights
            if hasattr(result, 'ranking') and result.ranking:
                output_data = {"ranking": result.ranking.ranking}
            elif hasattr(result, 'weights'):
                output_data = result.weights.model_dump()
        elif agent_name == "poi-agent":
            # For POI agent (filtering), show categories and minimum scores
            if hasattr(result, 'categories') and hasattr(result, 'punteggi_minimi'):
                output_data = {
                    "ordered_categories": result.categories,
                    "min_scores": result.punteggi_minimi
                }
            elif hasattr(result, 'raw_text'):
                output_data = result.raw_text
        elif hasattr(result, 'raw_text'):
            output_data = result.raw_text
        elif isinstance(result, dict) and 'raw_text' in result:
            output_data = result['raw_text']
        elif hasattr(result, 'model_dump'):
            output_data = result.model_dump()
        else:
            output_data = str(result)
            
        entry = {
            "agent_name": agent_name,
            "agent_mode": mode,
            "timestamp": datetime.now().isoformat(),
            "execution_time_ms": duration_ms,
            "input": input_data,
            "output": output_data,
            "output_structure": None
        }
        state["agent_trace"].append(entry)

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def _update_progress(self, state: GraphState, step_index: int, message: str):
        if state["set_progress"]:
            total_steps = len(state["step_definitions"])
            percent = min(100, step_index * 100 / total_steps)

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

    def _get_column_statistics(self, columns: List[str], dataset_path: str = None, dataset_df: pd.DataFrame = None, target_not_na_col: str = None, db_metadata: dict = None) -> dict:
        """Estrae statistiche per un set di colonne per gli agenti LLM."""
        try:
            if dataset_df is not None:
                # Filtraggio colonne presenti
                available_cols = [c for c in columns if c in dataset_df.columns]
                df = dataset_df[available_cols] if available_cols else pd.DataFrame()
            elif dataset_path and os.path.exists(dataset_path):
                available_cols = [c for c in columns] # Initial list
                if dataset_path.endswith('.parquet'):
                    df = pd.read_parquet(dataset_path, columns=available_cols)
                elif dataset_path.endswith('.csv'):
                    df = pd.read_csv(dataset_path, usecols=lambda col: col in available_cols)
                else:
                    try:
                        df = pd.read_parquet(dataset_path, columns=available_cols)
                    except:
                        df = pd.read_csv(dataset_path, usecols=lambda col: col in available_cols)
            else:
                return {}

            stats = {
                "total_records": len(df),
            }
            
            if target_not_na_col and target_not_na_col in df.columns:
                stats[f"with_{target_not_na_col}_data"] = int(df[target_not_na_col].notna().sum())

            for col in columns:
                if col not in df.columns:
                    # Se la colonna non è nel DF, mostriamo 0 per ogni valore possibile dai metadati (se presenti)
                    if db_metadata and col in db_metadata and "values" in db_metadata[col]:
                        stats[col] = {str(val): 0 for val in db_metadata[col]["values"]}
                    continue

                if pd.api.types.is_numeric_dtype(df[col]):
                    valid_data = df[col].dropna()
                    if not valid_data.empty:
                        stats[col] = {
                            "min": round(float(valid_data.min()), 2),
                            "max": round(float(valid_data.max()), 2),
                            "mean": round(float(valid_data.mean()), 2),
                            "median": round(float(valid_data.median()), 2),
                            "percentiles": {
                                "25%": round(float(valid_data.quantile(0.25)), 2),
                                "50%": round(float(valid_data.quantile(0.50)), 2),
                                "75%": round(float(valid_data.quantile(0.75)), 2),
                            },
                        }
                else:
                    # Categorie - Semplificato: mostra direttamente il count per ogni valore
                    counts = df[col].value_counts().to_dict()
                    
                    real_values = []
                    if db_metadata and col in db_metadata and "values" in db_metadata[col]:
                        real_values = db_metadata[col]["values"]
                    
                    if real_values:
                        # Mostra 0 per i valori reali non presenti nel dataset
                        stats[col] = {str(val): int(counts.get(val, 0)) for val in real_values}
                        # Aggiungiamo eventuali valori nel dataset non presenti nei metadati (safety)
                        for val, count in counts.items():
                            if str(val) not in stats[col]:
                                stats[col][str(val)] = int(count)
                    else:
                        stats[col] = {str(k): int(v) for k, v in counts.items()}

            return stats
        except Exception as e:
            logger.error(f"Error calculating column statistics: {e}")
            return {"error": str(e)}

    def _get_ape_statistics(self, dataset_path: str = None, dataset_df: pd.DataFrame = None, db_metadata: dict = None) -> dict:
        """Wrapper per retrocompatibilità o logica specifica APE."""
        return self._get_column_statistics(
            columns=APE_AGENT_COLUMNS, 
            dataset_path=dataset_path, 
            dataset_df=dataset_df,
            target_not_na_col="classe_energetica_ape",
            db_metadata=db_metadata
        )

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

            # Mock Strategy - REMOVED legacy metrics_plan
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
            # needs_metric_plan removed

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
            self._update_progress(state, 1, "Analisi tipologie in corso...")
            logger.info("🔧 Executing TypologyAgent")

            base_dataset = state.get("base_dataset")
            dataset_path = state.get("dataset_path")
            typ_stats = {}
            if base_dataset is not None or dataset_path is not None:
                typ_stats = self._get_column_statistics(
                    columns=TYPOLOGY_AGENT_COLUMNS,
                    dataset_path=dataset_path,
                    dataset_df=base_dataset,
                    db_metadata=state.get("db_metadata")
                )

            result = self.typology_agent.run(
                query=query,
                mode="filtering",
                available_typologies=str(
                    state["db_metadata"]
                    .get("tipologia_bene_immobile", {})
                    .get("values", [])
                ),
                statistics=typ_stats
            )
            typ_data = safe_extract_json(result.raw_text, schema=TypologyResponse)
            typologies = typ_data.typologies if typ_data else []
            logger.info(f"✅ TypologyAgent completed: {typologies}")
            return result

        def run_location():
            self._update_progress(state, 1, "Analisi ubicazione in corso...")
            logger.info("📍 Executing LocationAgent")
            result = self.location_agent.run(query=query)
            loc_data = safe_extract_json(result.raw_text, schema=LocationResponse)
            places = loc_data.places if loc_data else []
            logger.info(f"✅ LocationAgent completed: {len(places)} places")
            return result

        def run_ape():
            # Always run APE agent if data is available
            base_dataset = state.get("base_dataset")
            dataset_path = state.get("dataset_path")
            if base_dataset is not None or dataset_path is not None:
                self._update_progress(state, 1, "Analisi energetica APE in corso...")
                logger.info("⚡ Executing ApeAgent")
                ape_stats = self._get_ape_statistics(dataset_path=dataset_path, dataset_df=base_dataset, db_metadata=state.get("db_metadata"))
                result = self.ape_agent.run(
                    query=query,
                    mode="filtering",
                    statistics=ape_stats,
                    score_legend=APE_SCORE_LEGEND,
                )
                logger.info("✅ ApeAgent completed")
                return result
            logger.info("⚠️ ApeAgent skipped: no data")
            return None

        def run_poi():
            self._update_progress(state, 1, "Analisi punti di interesse in corso...")
            logger.info("🏪 Executing PoiAgent")
            
            base_dataset = state.get("base_dataset")
            dataset_path = state.get("dataset_path")
            poi_stats = {}
            if base_dataset is not None or dataset_path is not None:
                poi_stats = self._get_column_statistics(
                    columns=POI_AGENT_COLUMNS,
                    dataset_path=dataset_path,
                    dataset_df=base_dataset,
                    db_metadata=state.get("db_metadata")
                )

            result = self.poi_agent.run(
                query=query,
                mode="filtering",
                statistics=poi_stats
            )
            logger.info("✅ PoiAgent completed")
            return result
        
        def run_normative():
            self._update_progress(state, 1, "Analisi normativa in corso...")
            logger.info("📚 Executing NormativeAgent")
            
            base_dataset = state.get("base_dataset")
            dataset_path = state.get("dataset_path")
            norm_stats = {}
            if base_dataset is not None or dataset_path is not None:
                norm_stats = self._get_column_statistics(
                    columns=NORMATIVE_AGENT_COLUMNS,
                    dataset_path=dataset_path,
                    dataset_df=base_dataset,
                    db_metadata=state.get("db_metadata")
                )

            result = self.normative_agent.run(
                query=query,
                available_columns=NORMATIVE_AGENT_COLUMNS,
                statistics=norm_stats
            )
            logger.info("✅ NormativeAgent completed")
            return result

        def run_ranking():
             self._update_progress(state, 1, "Analisi priorità in corso...")
             logger.info("⚖️ Executing RankingAgent")
             # Ranking agent needs query AND metadata
             result = self.ranking_agent.run(
                 query=query, 
                 mode="ranking",
                 db_metadata=state.get("db_metadata")
             )
             logger.info("✅ RankingAgent completed")
             return result

        # Execute in parallel
        # Increased workers to 6 to handle ranking
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_typology = executor.submit(run_typology)
            future_location = executor.submit(run_location)
            future_ape = executor.submit(run_ape)
            future_poi = executor.submit(run_poi)
            future_normative = executor.submit(run_normative)
            future_ranking = executor.submit(run_ranking)

            typology_result = future_typology.result()
            loc_result = future_location.result()
            ape_result = future_ape.result()
            poi_result = future_poi.result()
            normative_result = future_normative.result()
            ranking_result = future_ranking.result()

            state["typology_result"] = typology_result
            state["poi_result"] = poi_result
            state["ape_result"] = ape_result
            state["normative_result"] = normative_result
            state["ranking_result"] = ranking_result
            
            # Log Executions
            if typology_result: self._log_execution(state, "typology-agent", typology_result, 0)
            if loc_result: self._log_execution(state, "location-agent", loc_result, 0)
            if ape_result: self._log_execution(state, "ape-agent", ape_result, 0)
            if poi_result: self._log_execution(state, "poi-agent", poi_result, 0)
            if normative_result: self._log_execution(state, "normative-agent", normative_result, 0)
            if ranking_result: self._log_execution(state, "ranking-agent", ranking_result, 0)

        # Process Typology
        typ_data = safe_extract_json(typology_result.raw_text, schema=TypologyResponse)
        typologies = typ_data.typologies if typ_data else []
        state["typology_result"] = typology_result
        state["gemini_responses"]["typology_extraction"] = {
            "prompt": (
                typology_result.prompt.model_dump() if typology_result.prompt else None
            ),
            "response": typology_result.raw_text,
            "typologies": typologies,
        }
        state["context"].typology_result = typology_result

        # Process Location
        loc_data = safe_extract_json(loc_result.raw_text, schema=LocationResponse)
        places = loc_data.places if loc_data else []
        state["context"].locations = places
        state["gemini_responses"]["location_extraction"] = {
            "prompt": loc_result.prompt.model_dump() if loc_result.prompt else None,
            "response": loc_result.raw_text,
            "places": [p.model_dump() for p in places],
        }

        location_payload = []
        if places:
            for p in places:
                if p.lat is not None and p.lon is not None:
                    # Construct search query for payload format consistency
                    search_query = f"{p.name}, {p.city}" if p.city else p.name
                    location_payload.append([search_query, p.lat, p.lon])

        state["location_payload"] = location_payload

        # Process POI
        state["poi_result"] = poi_result
        state["context"].poi_result = poi_result
        poi_data = safe_extract_json(poi_result.raw_text) if poi_result else {}
        if poi_result is not None:
            state["gemini_responses"]["poi_analysis"] = {
                "prompt": poi_result.prompt.model_dump() if poi_result.prompt else None,
                "response": poi_result.raw_text,
                "categories": poi_data.get('categories', []),
                "punteggi_minimi": poi_data.get('punteggi_minimi', {}),
                "found": poi_data.get('found', False)
            }
        else:
            logger.warning("⚠️ POI analysis skipped: no result available")
            state["gemini_responses"]["poi_analysis"] = {
                "prompt": None,
                "response": "",
                "categories": [],
                "punteggi_minimi": {},
                "found": False
            }

        # Process APE
        state["ape_result"] = ape_result
        state["context"].ape_result = ape_result
        ape_data = safe_extract_json(ape_result.raw_text) if ape_result else {}
        if ape_result:
            state["gemini_responses"]["ape_analysis"] = {
                "prompt": ape_result.prompt.model_dump() if ape_result.prompt else None,
                "response": ape_result.raw_text,
                "suggested_filters": ape_data.get("suggested_filters", []),
                "found": ape_data.get("found", False)
            }

        # Process APE Text for Context
        ape_text = ""
        if ape_data and ape_data.get("found"):
            filters = ape_data.get("suggested_filters", [])
            if filters:
                ape_text = f"\n\nAnalisi Energetica: L'utente ha espresso necessità relative all'efficienza (APE). Filtri: {', '.join(filters)}."

        # Process POI Text for Context
        poi_text = ""
        if poi_data:
            poi_scores = poi_data.get('punteggi_minimi', {})
            # Consider high priority if score is relatively high (e.g. > 3.0)
            high_priority = [k for k, v in poi_scores.items() if v >= 3.0]
            if high_priority:
                poi_text = f"\n\nAnalisi POI: L'utente ha espresso preferenza per: {', '.join(high_priority)} con soglie di qualità (punteggi 1-5)."
            elif poi_data.get("categories"):
                poi_text = f"\n\nAnalisi POI: Categorie rilevanti: {', '.join(poi_data.get('categories'))}."

        # Save normative result in state and context
        state["normative_result"] = normative_result
        state["context"].normative_result = normative_result
        if normative_result:
            state["gemini_responses"]["normative_analysis"] = {
                "prompt": normative_result.prompt.model_dump() if normative_result.prompt else None,
                "response": normative_result.raw_text,
                "normative_info": normative_result.raw_text,
                "sources": normative_result.sources,
            }

        # Build use_case_str from agent results (no needs_metric)
        use_case_parts = [f"Query: {query}"]
        if ape_text:
            use_case_parts.append(ape_text.strip())
        if poi_text:
            use_case_parts.append(poi_text.strip())
        if normative_result:
            use_case_parts.append(f"Normative: {normative_result.raw_text[:200]}")
        state["use_case_str"] = "\n".join(use_case_parts)

        return state

    def _deterministic_relaxation(self, sql_query: str) -> str:
        """
        Relaxes the SQL query by removing the last condition from the WHERE clause.
        Uses sqlglot for robust AST manipulation (DuckDB dialect).
        """
        if not sql_query:
            return sql_query
            
        try:
            # Basic cleanup of markdown/comments
            sql_query = sql_query.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
            elif sql_query.startswith("```"):
                sql_query = sql_query.split("```")[1].split("```")[0].strip()

            # Parse the SQL query using DuckDB dialect
            # We use sqlglot because it builds a real AST, unlike sqlparse which is just a lexer.
            expression = parse_one(sql_query, read="duckdb")
            
            # Find the WHERE clause
            where = expression.find(exp.Where)
            if not where:
                logger.warning("No WHERE clause found to relax.")
                return sql_query

            # The logic is to remove the last top-level condition.
            # In SQL AST for AND/OR chains, this is usually the 'right' child of the top-level binary expression.
            predicate = where.this
            
            if isinstance(predicate, (exp.And, exp.Or)):
                # We replace the tree with its left child, effectively removing the rightmost branch.
                # Since LLMs tend to append more specific/less important conditions at the end, 
                # this correctly targets the "last" condition.
                where.set("this", predicate.left)
            else:
                # Only one condition remains in the WHERE clause, so we remove the whole clause.
                where.pop()
                
            # Generate the SQL back. Dialect="duckdb" ensures compatibility.
            # sqlglot handles spacing and quoting correctly.
            result = expression.sql(dialect="duckdb", pretty=True)
            
            logger.info(f"DETERMINISTIC RELAXATION (AST): Removed last condition. Result: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to parse or relax SQL via AST: {e}. Falling back to original query.")
            return sql_query

    def _format_agent_requirements(self, agent_result: Any) -> str:
        """Formatta i requisiti di un agente (APE o Normative) in formato compatto [col] [op] [val]."""
        if not agent_result or not agent_result.raw_text or agent_result.raw_text == "N/D":
            return "N/D"
        
        try:
            # Estrarre JSON in modo sicuro (gestisce blocchi markdown e testo extra)
            data = safe_extract_json(agent_result.raw_text)
            
            if not data or not isinstance(data, dict):
                # Se non è un dict valido, restituiamo il testo originale ma limitato
                return str(agent_result.raw_text)[:500]
                
            requisiti = data.get("requisiti", [])
            if not requisiti:
                return "Nessun requisito specifico identificato."
            
            formatted = []
            for req in requisiti:
                col = req.get("colonna_target")
                op = req.get("operatore")
                val = req.get("valore")
                if col and op and val is not None:
                    # Se valore è una lista, formattala come (val1, val2)
                    if isinstance(val, list):
                        val_str = "(" + ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in val) + ")"
                        formatted.append(f"{col} {op} {val_str}")
                    else:
                        val_str = f"'{val}'" if isinstance(val, str) else str(val)
                        formatted.append(f"{col} {op} {val_str}")
            
            return "; ".join(formatted) if formatted else "Nessun requisito specifico identificato."
        except Exception as e:
            logger.error(f"Error formatting agent requirements: {e}")
            # Fallback in caso di errore
            return str(agent_result.raw_text)[:500]

    def _generate_sql(self, state: GraphState) -> GraphState:
        retry_count = state["retry_count"]
        if "sql_history" not in state or retry_count == 0:
            state["sql_history"] = []
        self._update_progress(
            state, 2, f"Generazione SQL (tentativo {retry_count + 1})..."
        )

        query = state["query"]
        db_schema = state["db_schema"]
        location_payload = state["location_payload"]
        failed_query = state["sql_query"] if retry_count > 0 else ""
        error_msg = state.get("execution_error")

        loc_obj = None
        if isinstance(location_payload, list) and location_payload:
            _, lat, lon = location_payload[0]
            loc_obj = {"lat": lat, "lon": lon}

        # Raw agent outputs
        typology_result = state.get("typology_result")
        poi_result = state.get("poi_result")
        ape_result = state.get("ape_result")
        normative_result = state.get("normative_result")
        
        typologies_raw = typology_result.raw_text if typology_result else "N/D"
        # Formattazione compatta per POI: solo punteggi_minimi
        poi_raw = "N/D"
        if poi_result:
            try:
                poi_data = safe_extract_json(poi_result.raw_text)
                if poi_data and isinstance(poi_data, dict):
                    poi_raw = json.dumps(poi_data.get("punteggi_minimi", {}), ensure_ascii=False)
            except:
                poi_raw = str(poi_result.raw_text)[:500]
        
        # Formattazione compatta per APE e Normativa per risparmiare token e migliorare precisione
        # Per APE, diamo priorità ai suggested_filters che sono già clausole SQL valide (es. IN, LIKE)
        ape_data = safe_extract_json(ape_result.raw_text) if ape_result else {}
        if ape_data and ape_data.get("suggested_filters"):
            ape_raw = "; ".join(ape_data["suggested_filters"])
        else:
            ape_raw = self._format_agent_requirements(ape_result)
            
        normative_raw = self._format_agent_requirements(normative_result)
        

        # Format locations as JSON string for clarity: only lat, lon, radius_km
        locations_list = state["gemini_responses"].get("location_extraction", {}).get("places", [])
        filtered_locations = []
        for loc in locations_list:
            filtered_locations.append({
                "lat": loc.get("lat"),
                "lon": loc.get("lon"),
                "radius_km": loc.get("radius_km")
            })
        locations_raw = json.dumps(filtered_locations, ensure_ascii=False)

        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating SQL generation...")
            time.sleep(1.5)
            state["sql_query"] = MOCK_SQL_QUERY
            state["gemini_responses"]["sql_generation"] = {
                "response": "Mock SQL generated",
                "sql_query": MOCK_SQL_QUERY,
            }
            return state

        # Determination of whether to use Retry Prompt
        # Prepare failed query and error message for the SQL Agent.
        # This is used both for fixing SQL errors and for query relaxation.
        is_sql_error = bool(state.get("execution_error"))
        effective_failed_query = failed_query
        effective_error_msg = error_msg

        # DETERMINISTIC RELAXATION: If we are retrying because of few results (not a SQL error)
        # we prepare the relaxed query to be passed to the agent run for logging.
        relaxed_sql = None
        if state.get("relax_constraints") and not is_sql_error and failed_query:
            logger.info(f"Applying DETERMINISTIC RELAXATION (Attempt {retry_count + 1})")
            relaxed_sql = self._deterministic_relaxation(failed_query)

        if state.get("relax_constraints") and not is_sql_error:
            logger.info(f"Applying RELAXATION to SQL prompt (Attempt {retry_count + 1})")

        # Extract ranking list
        ranking_agent_result = state.get("ranking_result")
        ranking_list = []
        if ranking_agent_result and hasattr(ranking_agent_result, "ranking") and ranking_agent_result.ranking:
            ranking_list = ranking_agent_result.ranking.ranking

        sql_result = self.sql_agent.run(
            query=query, # use original query
            scheme=json.dumps(db_schema.get("types", {}), ensure_ascii=False),
            typologies=typologies_raw,
            locations=locations_raw,
            ape_requirements=ape_raw,
            poi_requirements=poi_raw,
            normative_requirements=normative_raw,
            location=loc_obj,
            failed_query=effective_failed_query,
            error_msg=effective_error_msg,
            db_metadata=json.dumps(state.get("db_metadata", {}), ensure_ascii=False),
            ranking_list=ranking_list,
            raw_response=relaxed_sql
        )

        # Append to history
        state["sql_history"].append(sql_result.raw_text)

        # sql_result.raw_text now contains the cleaned SQL
        state["sql_query"] = sql_result.raw_text
        key = (
            "sql_generation"
            if retry_count == 0
            else f"sql_generation_retry_{retry_count}"
        )
        state["gemini_responses"][key] = {
            "prompt": sql_result.prompt.model_dump() if sql_result.prompt else None,
            "response": sql_result.raw_text,
            "sql_query": sql_result.raw_text,
            "sql_history": state["sql_history"]
        }
        
        self._log_execution(state, "sql-agent", sql_result, 0)
        return state

    def _execute_sql(self, state: GraphState) -> GraphState:
        self._update_progress(state, 3, "Esecuzione query...")
        sql_query = state["sql_query"]
        dataset_path = state.get("dataset_path")
        base_dataset = state.get("base_dataset")

        logger.info(f"Executing SQL: {sql_query}")
        # Use base_dataset if available, otherwise rely on dataset_path
        pd_data = base_dataset if base_dataset is not None else None
        selected_data, error = self.execute_sql_fn(
            sql_query, pd_data, dataset_path=dataset_path
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

        if len(state["selected_data"]) >= 10:
            return "continue"

        if state["retry_count"] < 5:
            logger.warning(
                f"Retrying due to few results ({len(state['selected_data'])}). Attempt {state['retry_count'] + 1}"
            )
            return "retry_relax"

        logger.warning("Max retries reached. Activating fallback.")
        return "fallback"

    def _handle_retry(self, state: GraphState) -> GraphState:
        # Determine if it's an error retry or a relaxation retry
        error = state.get("execution_error")
        few_results = not error and len(state.get("selected_data", [])) < 10
        
        relax = state.get("relax_constraints", False)
        reason = "error" if error else "few_results" if few_results else None

        if few_results:
            relax = True
            logger.info("Relaxing constraints due to zero/few results")
        
        return {
            "retry_count": state["retry_count"] + 1, 
            "relax_constraints": relax,
            "last_retry_reason": reason
        }

    def _fallback_results(self, state: GraphState) -> GraphState:
        """
        Fallback when SQL queries fail after max retries.
        Returns top results from full dataset so user always gets something.
        """
        self._update_progress(
            state, 3, "Nessun risultato trovato. Generazione alternative..."
        )
        logger.warning("Fallback activated: loading top results from full dataset")

        dataset_path = state.get("dataset_path")
        base_dataset = state.get("base_dataset")
        
        if not dataset_path and base_dataset is None:
            logger.error("No dataset path or base_dataset for fallback")
            state["status_msg"] = "Errore: impossibile generare alternative."
            return state

        try:
            if dataset_path:
                full_df = pd.read_parquet(dataset_path)
                logger.info(f"Fallback loaded {len(full_df)} rows from dataset file")
            else:
                full_df = base_dataset.copy()
                logger.info(f"Fallback using base_dataset ({len(full_df)} rows)")

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
        self._update_progress(state, 4, "Arricchimento dati...")
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

    def _calculate_ranking_weights(self, state: GraphState) -> GraphState:
        self._update_progress(state, 5, "Analisi pesi per ranking...")
        query = state["query"]
        
        # In mock mode, use defaults or simulated weights
        if USE_MOCK_RESPONSES:
            weights = RankingWeights(location=0.3, normative=0.1, ape=0.2, typology=0.2, poi=0.2)
            state["ranking_result"] = RankingAgentResult(raw_text="{}", weights=weights)
        else:
            # Check if ranking was already computed in parallel phase
            ranking_result = state.get("ranking_result")
            already_ran = ranking_result is not None

            if not ranking_result:
                ranking_result = self.ranking_agent.run(
                    query=query, 
                    mode="ranking", 
                    db_metadata=state.get("db_metadata")
                )
                state["ranking_result"] = ranking_result

            state["context"].ranking_result = ranking_result
            
            state["gemini_responses"]["ranking_weights"] = {
                "prompt": ranking_result.prompt.model_dump() if ranking_result.prompt else None,
                "response": ranking_result.raw_text,
                "weights": ranking_result.weights.model_dump()
            }
        
            # Only log trace if it wasn't already logged in parallel phase
            if not already_ran:
                self._log_execution(state, "ranking-agent", ranking_result, 0, mode="ranking")
        
        return state


    def _rank_results(self, state: GraphState) -> GraphState:
        self._update_progress(state, 5, "Ranking parallelo e pesatura...")
        df = state["selected_data"]
        if df is None or df.empty:
            return state

        # Fix: Ensure ID is string for matching with agent results (which use string IDs from JSON)
        if "id" in df.columns:
            df["id"] = df["id"].astype(str)

        ranking_res = state.get("ranking_result")
        weights = ranking_res.weights if ranking_res else RankingWeights()

        # Define ranking tasks for parallel execution
        def rank_typology():
            res = state.get("typology_result")
            if res:
                data = safe_extract_json(res.raw_text, schema=TypologyResponse)
                if data and data.typologies:
                    tmp = self.typology_agent.run(mode="ranking", df=df.copy(), ranked_typologies=data.typologies)
                    return tmp[["id", "typology_score"]]
            tmp = df.copy()
            tmp["typology_score"] = 0.0
            return tmp[["id", "typology_score"]]

        def rank_location():
            if state["context"].locations:
                 tmp = self.location_agent.run(mode="ranking", df=df.copy(), places=state["context"].locations)
                 return tmp[["id", "location_score"]]
            tmp = df.copy()
            tmp["location_score"] = 0.0
            return tmp[["id", "location_score"]]

        def rank_ape():
            res = state.get("ape_result")
            requirements = None
            if res:
                data = safe_extract_json(res.raw_text, schema=ApeResponse)
                if data and data.found:
                    requirements = data.requisiti
            
            tmp = self.ape_agent.run(mode="ranking", df=df.copy(), requirements=requirements)
            return tmp[["id", "ape_score"]]

        def rank_normative():
            res = state.get("normative_result")
            if res:
                data = safe_extract_json(res.raw_text, schema=NormativeResponse)
                if data and data.found:
                    tmp = self.normative_agent.run(mode="ranking", df=df.copy(), requirements=data.requisiti, available_columns=NORMATIVE_AGENT_COLUMNS)
                    return tmp[["id", "normative_score"]]
            tmp = df.copy()
            tmp["normative_score"] = 0.0
            return tmp[["id", "normative_score"]]

        def rank_poi():
            res = state.get("poi_result")
            if res:
                data = safe_extract_json(res.raw_text)
                if data and data.get("categories"):
                    tmp = self.poi_agent.run(mode="ranking", df=df.copy(), ranked_categories=data.get("categories"))
                    return tmp[["id", "poi_score"]]
            tmp = df.copy()
            tmp["poi_score"] = 0.0
            return tmp[["id", "poi_score"]]


        # Execute parallel ranking tasks
        with ThreadPoolExecutor(max_workers=5) as executor:
            task_map = {
                executor.submit(rank_typology): "typology",
                executor.submit(rank_location): "location",
                executor.submit(rank_ape): "ape",
                executor.submit(rank_normative): "normative",
                executor.submit(rank_poi): "poi",
            }
            
            for future in as_completed(task_map):
                name = task_map[future]
                try:
                    res_df = future.result()
                    
                    # Log ranking results as JSON for UI visualization
                    if not res_df.empty:
                        # Transform to clean JSON (handles NaNs by converting to null)
                        # and put it at the top level for the UI to show an accordion
                        clean_json = res_df.to_json(orient="records")
                        state["gemini_responses"][f"{name}_ranking"] = {
                            "response": json.loads(clean_json)
                        }
                        
                        # Log this ranking agent execution to the trace
                        self._log_execution(state, f"{name}-agent", res_df, 0, mode="ranking")

                    # Aggiungiamo solo le colonne di score evitando duplicazioni (usiamo 'id' come chiave)
                    df = df.merge(res_df, on="id", how="left")
                except Exception as e:
                    logger.error(f"Error in parallel ranking part {name}: {e}")
                    col = "ape_score" if name == "ape" else f"{name}_score"
                    if col not in df.columns:
                        df[col] = 0.0

        # Calculate final weighted score
        df["final_ranking_score"] = (
            weights.location * df.get("location_score", 0.0) +
            weights.normative * df.get("normative_score", 0.0) +
            weights.ape * df.get("ape_score", 0.0) +
            weights.typology * df.get("typology_score", 0.0) +
            weights.poi * df.get("poi_score", 0.0)
        )

        # Sort by total score
        df = df.sort_values(by="final_ranking_score", ascending=False)
        state["selected_data"] = df
        
        return state

    def _evaluate_results(self, state: GraphState) -> GraphState:
        enriched_data = state["selected_data"]

        llm_cap = self._resolve_llm_cap(state.get("llm_limit"))

        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating Evaluation...")
            self._update_progress(
                state, 6, f"Avvio valutazione qualitativa simulata..."
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
                mock_data = json.loads(MOCK_EVALUATION.raw_text)
                for idx, item_id in enumerate(enriched_data.head(3)["id"].tolist()):
                    if idx < len(mock_data):
                        res_dict = mock_data[idx]
                        res = EvaluationResult(**res_dict)
                        res.id = item_id
                        eval_results.append(res)
                        time.sleep(0.5)
                        self._update_progress(
                            state,
                            6,
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
                6,
                f"Valutazione completata: {len(eval_results)} risultati generati.",
            )
            return state

        # Limit evaluation to top results defined by llm_cap
        eval_input_df = enriched_data.head(llm_cap).copy()
        eval_input_df["is_evaluated"] = True

        total_items = len(eval_input_df)
        self._update_progress(
            state,
            6,
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
            "distanza_km",
            # Agent scores
            "ape_score",
            "location_score",
            "normative_score",
            "typology_score",
            "poi_score",
            # Calculated Score
            "final_ranking_score"
        ]

        def prepare_estates_json(batch_df: pd.DataFrame) -> str:
            """Convert DataFrame to JSON with only relevant columns for LLM evaluation."""
            # Select only columns that exist in the dataframe
            available_cols = [c for c in EVAL_COLUMNS if c in batch_df.columns]
            subset = batch_df[available_cols].copy()

            # Identify columns that are numeric scores to be rounded to nearest int
            # Includes explicit scores (ending in _score or score_*) and POI pillars (1-5 range)
            poi_pillars = ["sanita", "mobilita", "verde", "sport", "commerciale", "educazione"]
            score_cols_to_round = []
            
            for col in subset.columns:
                if not pd.api.types.is_numeric_dtype(subset[col]):
                    continue
                    
                is_score = (
                    col.endswith("score") or 
                    "_score_" in col or 
                    col == "final_ranking_score" or 
                    col == "score" or
                    col in poi_pillars
                )
                
                if is_score:
                    score_cols_to_round.append(col)

            # Round to nearest integer and cast to int
            for col in score_cols_to_round:
                # fillna(0) for safety on scores, though some might naturally be NaN. 
                # For presentation to LLM as "rounded score", 0 is reasonable default for missing.
                subset[col] = pd.to_numeric(subset[col], errors='coerce').fillna(0).round().astype(int)

            # We DO NOT rename final_ranking_score to score anymore, as per user request.
            # LLM prompt now expects 'final_ranking_score'.
            
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
                    
                    # Parse results from raw_text using EvaluationList schema
                    eval_data = safe_extract_json(payload.raw_text, schema=EvaluationList)
                    batch_results = []
                    if eval_data and eval_data.evaluations:
                        batch_results = eval_data.evaluations
                    else:
                        # Fallback for unexpected formats
                        raw_data = safe_extract_json(payload.raw_text)
                        if isinstance(raw_data, list):
                            batch_results = [EvaluationResult(**r) if isinstance(r, dict) else r for r in raw_data]
                        elif isinstance(raw_data, dict) and "evaluations" in raw_data:
                            batch_results = [EvaluationResult(**r) if isinstance(r, dict) else r for r in raw_data["evaluations"]]
                    
                    # Update progress dynamically for each batch
                    self._update_progress(
                        state,
                        6,
                        f"Analizzando batch {finished_batches}/{total_batches} con {len(batch_results)} valutazioni...",
                    )
                    
                    self._log_execution(state, "evaluation-agent", payload, 0, mode="evaluation")

                    if batch_results:
                        all_results.extend(batch_results)
                        # We keep the last prompt/response for logging purposes
                        state["gemini_responses"]["evaluation"] = {
                            "prompt": (
                                payload.prompt.model_dump() if payload.prompt else None
                            ),
                            "response": payload.raw_text,
                            "results_count": len(all_results),
                        }
                except Exception as e:
                    logger.error(f"Error parsing evaluation batch: {e}")
                    pass

        state["context"].evaluation_results = all_results
        # Update full results list in log
        if "evaluation" in state["gemini_responses"]:
            state["gemini_responses"]["evaluation"]["results"] = [
                res.model_dump() if hasattr(res, "model_dump") else res for res in all_results
            ]

        self._update_progress(
            state, 6, f"Valutazione completata: {len(all_results)} risultati generati."
        )
        return state

    def _broker_review(self, state: GraphState) -> GraphState:
        self._update_progress(state, 7, "Analisi esperta (Senior Broker)...")

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
            if hasattr(res, "id") and hasattr(res, "final_ranking_score"):
                # Handle as Pydantic model
                candidates.append(
                    f"Candidato #{i+1} (ID: {res.id}, Score: {res.final_ranking_score}):\n"
                    f"Motivazione: {res.evaluation_text}\n"
                    f"Pro: {', '.join(res.pros)}\n"
                    f"Contro: {', '.join(res.cons)}\n"
                )
            elif isinstance(res, dict):
                # Handle as dictionary
                score_val = res.get("final_ranking_score") or res.get("score")
                candidates.append(
                    f"Candidato #{i+1} (ID: {res.get('id')}, Score: {score_val}):\n"
                    f"Motivazione: {res.get('evaluation_text')}\n"
                    f"Pro: {', '.join(res.get('pros', []))}\n"
                    f"Contro: {', '.join(res.get('cons', []))}\n"
                )

        candidates_text = "\n---\n".join(candidates)

        summary = self.broker_agent.run(
            query=state["query"], candidates_data=candidates_text
        )

        state["broker_summary"] = summary
        state["gemini_responses"]["broker_review"] = summary
        return state

    def _finalize_results(self, state: GraphState) -> GraphState:
        trace_len = len(state.get("agent_trace", []))
        logger.info(f"Finalizing results. Agent trace size: {trace_len}")
        self._update_progress(state, 8, "Finalizzazione...")

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
            self._update_progress(state, 9, "Completato (Nessun risultato filtrato).")
            return state

        # Dati arricchiti dal percorso agente (solo subset selezionato dalla query)
        enriched_data = state["selected_data"]
        map_cap = self._resolve_map_cap(state.get("map_limit"))
        llm_cap = self._resolve_llm_cap(state.get("llm_limit"))
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
            for col in ["id", "is_match", "final_ranking_score", "distanza_km"]
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

        if "final_ranking_score" in map_df.columns:
            map_df["final_ranking_score"] = pd.to_numeric(
                map_df["final_ranking_score"], errors="coerce"
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
                        "final_ranking_score": res.final_ranking_score,
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
                        ["id", "motivazione", "pro", "contro"]
                    ].drop_duplicates("id"),
                    on="id",
                    how="left",
                )

                map_df["final_ranking_score"] = pd.to_numeric(
                    map_df.get("final_ranking_score"), errors="coerce"
                ).fillna(0)
                map_df["is_evaluated"] = map_df["id"].isin(valutazioni_df["id"])
                map_df["is_selected_by_llm"] = map_df["final_ranking_score"] >= 60
            else:
                map_df["final_ranking_score"] = 0
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
            map_df["final_ranking_score"] = 0
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
        if "final_ranking_score" in map_df.columns:
            sort_cols.append("final_ranking_score")
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
        self._update_progress(state, 9, "Completato.")
        return state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resolve_llm_cap(self, llm_limit: Optional[int]) -> int:
        try:
            val = int(llm_limit) if llm_limit else MAX_ITEMS_FOR_LLM
            return min(max(1, val), MAX_LLM_CAP)
        except (TypeError, ValueError):
            return MAX_ITEMS_FOR_LLM

    def _resolve_map_cap(self, map_limit: Optional[int]) -> int:
        try:
            m_val = int(map_limit) if map_limit else MAX_ITEMS_FOR_MAP
            return max(1, m_val)
        except (TypeError, ValueError):
            return MAX_ITEMS_FOR_MAP
