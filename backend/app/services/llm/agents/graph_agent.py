from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union

from langgraph.graph import END, StateGraph
import numpy as np
import pandas as pd
import tabulate

from app.services.analysis.ranking import calculate_ranking_score
from app.core.config import settings
from app.core.constants import SCORE_LEGEND, APE_SCORE_LEGEND, APE_AGENT_COLUMNS, NORMATIVE_AGENT_COLUMNS, POI_AGENT_COLUMNS, PROPERTY_TECHNICAL_AGENT_COLUMNS, ALL_AGENT_COLUMNS

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
    PropertyTechnicalAgentResult,
    RankingAgentResult,
    RankingWeights,
    NormativeResponse,
    PropertyTechnicalResponse,
    LocationResponse,
    ApeResponse,
    EvaluationResult,
    EvaluationList,
    ApeAgentResult,
    PoiAgentResult,
    Place,
)
from app.services.llm.agents.sql_agent import SQLAgent
from app.services.llm.agents.property_technical_agent import PropertyTechnicalAgent
from app.services.llm.agents.ranking_agent import RankingAgent
from app.utils.logger import logger
from app.utils.json_parser import safe_extract_json
from app.services.llm.mocks import (
    MOCK_PROPERTY_TECHNICAL,
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
    sql_query: str
    context: AgentContext
    match_count: int = 0
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
    # metrics_plan has been removed as part of clean architecture refactor
    property_technical_result: Optional[PropertyTechnicalAgentResult]
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
    sql_history: List[str]  # History of all SQL queries tried (initial + retry)

    match_count: int
    agent_trace: List[Dict[str, Any]]
    
    # Config
    llm_limit: Optional[int]
    map_limit: Optional[int]
    metro_graph: Any
    analysis_mode: str
    disabled_agents: List[str] # List of agents to skip during execution

    # Progress callback
    set_progress: Optional[Callable[[Any], None]]
    step_definitions: List[Dict[str, str]]
    steps_state: List[Dict[str, Any]]
    last_retry_reason: Optional[str]  # Why we are retrying (error)
    use_data_knowledge: bool  # Whether to pass data distribution statistics to agents

class GraphOrchestratorAgent(BaseAgent):
    """
    Orchestrator implemented using LangGraph.
    """

    name = "graph-orchestrator-agent"

    def __init__(
        self,
        *,
        analysis_mode: str = "agent",
        architecture: str = "multiagent",
        execute_sql_fn: Optional[
            Callable[[str, pd.DataFrame], tuple[pd.DataFrame, Optional[str]]]
        ] = None,
        location_agent: Optional[LocationAgent] = None,
        sql_agent: Optional[SQLAgent] = None,
        evaluation_agent: Optional[EvaluationAgent] = None,
        property_technical_agent: Optional[PropertyTechnicalAgent] = None,
        ape_agent: Optional[ApeAgent] = None,
        poi_agent: Optional[PoiAgent] = None,
        normative_agent: Optional[NormativeAgent] = None,
    ) -> None:
        if execute_sql_fn is None:
            raise ValueError("execute_sql_fn is required.")

        self.analysis_mode = (analysis_mode or "agent").lower()
        self.architecture = (architecture or "multiagent").lower()
        self.is_agent_mode = self.analysis_mode == "agent"
        self.execute_sql_fn = execute_sql_fn

        self.location_agent = location_agent or LocationAgent()
        self.sql_agent = sql_agent or SQLAgent()
        self.evaluation_agent = evaluation_agent or EvaluationAgent()
        self.broker_agent = BrokerAgent()
        self.property_technical_agent = property_technical_agent or PropertyTechnicalAgent()
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
                "continue": "enrich_results",
                "fallback": "fallback_results",  # NEW: route to fallback instead of empty
            },
        )

        # Fallback continues to enrich (so ranking/evaluation still happen)
        workflow.add_edge("fallback_results", "enrich_results")
        workflow.add_edge("enrich_results", "calculate_ranking_weights")
        workflow.add_edge("calculate_ranking_weights", "rank_results")
        workflow.add_edge("rank_results", "evaluate_results")
        workflow.add_conditional_edges(
            "evaluate_results",
            self._should_broker_review,
            {
                "continue": "broker_review",
                "skip": "finalize_results",
            },
        )
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
        disabled_agents: Optional[List[str]] = None,
        use_data_knowledge: bool = True,
    ) -> OrchestratorResult:
        # Step definitions per la UI (comuni)
        step_definitions = [
            {"key": "ranking_init", "label": "Analizzo la richiesta utente..."},
            {"key": "property_technical", "label": "Valuto le caratteristiche planimetriche e tecniche degli immobili..."},
            {"key": "location", "label": "Individuo una posizione geografica di ricerca..."},
            {"key": "ape", "label": "Analizzo le prestazioni energetiche degli edifici..."},
            {"key": "normative", "label": "Verifico i requisiti normativi..."},
            {"key": "poi", "label": "Esamino la disponibilità di servizi nelle vicinanze..."},
            {"key": "ranking", "label": "Calcolo gli score..."},
            {"key": "evaluation", "label": "Fornisco delle motivazioni a supporto delle mie scelte..."},
            {"key": "broker", "label": "Descrivo la scelta migliore..."},
        ]

        # Load metadata
        # Load metadata from centralized memory (constants.py)
        from app.core.constants import DB_METADATA
        db_metadata = DB_METADATA

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
            "property_technical_result": None,
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
            "match_count": 0,
            "broker_summary": "",
            "llm_limit": llm_limit,
            "map_limit": map_limit,
            "metro_graph": metro_graph,
            "analysis_mode": self.analysis_mode,
            "set_progress": set_progress,
            "step_definitions": step_definitions,
            "steps_state": [
                {"label": s["label"], "state": "pending", "detail": ""}
                for s in step_definitions
            ],
            "last_retry_reason": None,
            "sql_history": [],
            "disabled_agents": disabled_agents or [],
            "use_data_knowledge": use_data_knowledge,
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
                logger.info(" Run successfully exported to JSON")
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
            sql_query=final_state["sql_query"],
            context=final_state["context"],
            match_count=final_state["match_count"],
            broker_summary=final_state.get("broker_summary", ""),
            agent_trace=final_state.get("agent_trace", []),
            relaxation_applied=final_state.get("relaxation_applied", False) or final_state.get("relax_constraints", False),
        )

    def _unified_analysis(self, state: GraphState) -> GraphState:
        """Esegue l'analisi tramite un singolo prompt unificato (Baseline Planner)."""
        from app.services.llm.langchain_client import get_llm
        from langchain_core.messages import HumanMessage
        
        query = state["query"]
        self._update_progress(state, "ranking_init", "Generazione piano di analisi unificato...")

        # 1. Caricamento Metadati e Prompt
        # Path robusto al template configurato
        prompt_path = os.path.join(os.path.dirname(__file__), "../../../../../docs/gemini_pipeline_prompt.txt")
        template = ""
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()
        except Exception as e:
            logger.error(f"Errore lettura template baseline: {e}")
            template = "Genera un JSON con 'sql' (query DuckDB) e 'layer2' (pesi ranking)."

        # Stats di supporto (data knowledge)
        stats = {}
        if state.get("use_data_knowledge", True):
            stats = self._get_column_statistics(
                columns=["superficie_di_riferimento_mq", "tipologia_bene_immobile", "classe_energetica_ape"],
                dataset_df=state.get("base_dataset"),
                dataset_path=state.get("dataset_path"),
                db_metadata=state.get("db_metadata")
            )

        # 1.5 Caricamento Normativa
        from app.services.llm.agents.normative_agent import load_normative_documents
        normativa_text, _, _ = load_normative_documents()

        # 2. Invocazione LLM (Unified Architect)
        prompt_text = (
            "========================================\nQUERY UTENTE (INPUT)\n"
            f"{query}\n========================================\n"
            f"METADATI DATASET:\n{json.dumps(state.get('db_metadata'), ensure_ascii=False)}\n\n"
            f"STATISTICHE DISTRIBUZIONE:\n{json.dumps(stats, ensure_ascii=False)}\n\n"
            f"NORMATIVA DI RIFERIMENTO:\n{normativa_text}\n\n"
            f"ISTRUZIONI DI RAGIONAMENTO & OUTPUT FORMAT:\n{template}"
        )

        llm = get_llm()
        start_t = time.time()
        response = llm.invoke([HumanMessage(content=prompt_text)])
        duration_ms = (time.time() - start_t) * 1000
        llm_output = response.content if hasattr(response, "content") else str(response)

        # 3. Parsing e popolamento dello Stato
        data = safe_extract_json(llm_output) or {}
        
        # SQL Query
        sql_query = data.get("sql", {}).get("query", "")
        if sql_query:
            # Fix literal escape characters sometimes generated by LLMs
            sql_query = sql_query.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
            # Basic validation: ensure it's not empty and looks like SQL
            if "SELECT" not in sql_query.upper():
                logger.warning(f"Baseline planner generated invalid SQL: {sql_query}")
        state["sql_query"] = sql_query
        
        # Ranking Weights (Mappa i nomi del prompt a quelli dello schema)
        weights_data = data.get("layer2", {}).get("pesi", {})
        weights = RankingWeights(
            location=weights_data.get("localizzazione", 0.2),
            normative=weights_data.get("normativa", 0.2),
            ape=weights_data.get("energia", 0.2),
            property_technical=weights_data.get("tipologia", 0.2),
            poi=weights_data.get("servizi", 0.2)
        )
        state["ranking_result"] = RankingAgentResult(raw_text=llm_output, weights=weights)

        # 4. Popolamento dei risultati tecnici (layer1) per compatibilità con il ranking deterministico
        # Questo assicura che i pesi non vengano azzerati in _rank_results se l'agente non ha girato.
        layer1 = data.get("layer1", {}).get("analisi", {})
        if layer1:
            # Helper per estrarre parametri o filtri in modo agnostico
            def get_reqs(obj):
                if not isinstance(obj, dict): return {}
                return obj.get("parametri") or obj.get("parameters") or obj.get("filters") or obj.get("requirements") or {}

            # 1. Tipologia -> PropertyTechnicalAgentResult
            tip = layer1.get("tipologia", {})
            if tip.get("found"):
                reqs = get_reqs(tip)
                # Tentativo di recupero tipologie
                typs = reqs.get("tipologia_bene_immobile", []) if isinstance(reqs, dict) else []
                # Se non è una lista ma una stringa (comune errore LLM), convertila
                if isinstance(typs, str): typs = [typs]
                
                payload = {
                    "typologies": typs if typs else ["Abitazione"], # Fallback a valore sicuro se found=True
                    "found": True,
                    "requisiti": [{"colonna": "superficie_di_riferimento_mq"}] 
                }
                state["property_technical_result"] = PropertyTechnicalAgentResult(
                    raw_text=json.dumps(payload),
                    prompt=None
                )

            # 2. Localizzazione -> context.locations
            loc = layer1.get("localizzazione", {})
            if loc.get("found"):
                params = get_reqs(loc)
                if isinstance(params, dict) and (params.get("latitudine") or params.get("coordinate")):
                    lat = params.get("latitudine")
                    lon = params.get("longitudine")
                    if not lat and params.get("coordinate"):
                         coord = params.get("coordinate")
                         if isinstance(coord, dict):
                            lat, lon = coord.get("lat"), coord.get("lon")
                    
                    if lat and lon:
                        place = Place(
                            name="Coordinate Planner",
                            lat=lat,
                            lon=lon,
                            radius_km=params.get("raggio_km", 3.0)
                        )
                        state["context"].locations = [place]

            # 3. Energia -> ApeAgentResult
            en = layer1.get("energia", {})
            if en.get("found"):
                payload = {"found": True, "requisiti": [{"colonna": "classe_energetica_ape"}]}
                state["ape_result"] = ApeAgentResult(raw_text=json.dumps(payload))

            # 4. Servizi -> PoiAgentResult
            ser = layer1.get("servizi", {})
            if ser.get("found"):
                r_list = get_reqs(ser).get("prossimita_servizi") or ["sanita"] if isinstance(get_reqs(ser), dict) else ["sanita"]
                payload = {"found": True, "requisiti": [{"servizio": s} for s in r_list]}
                state["poi_result"] = PoiAgentResult(raw_text=json.dumps(payload))

            # 5. Normativa -> NormativeAgentResult
            norm = layer1.get("normativa", {})
            if norm.get("found"):
                dest = get_reqs(norm).get("destinazione_uso") if isinstance(get_reqs(norm), dict) else "Altro"
                payload = {"found": True, "requisiti": [{"note": dest or "Analisi normativa"}]}
                state["normative_result"] = NormativeAgentResult(raw_text=json.dumps(payload))

        # Trace e Gemini Responses per compatibilità UI
        state["gemini_responses"]["baseline_planner"] = data
        self._log_execution(state, "baseline-planner", llm_output, duration_ms)
        
        # Mocking dei tecnici per evitare che i nodi successivi falliscano se li cercano
        # (Opzionale: potremmo mappare layer1 qui se utile)
        self._update_progress(state, "ranking_init", "Piano generato con successo.", status="done")
        
        return state

    # ------------------------------------------------------------------
    # Shared Pipeline Nodes
    # ------------------------------------------------------------------

    def _log_execution(
        self,
        state: GraphState,
        agent_name: str,
        result: Any,
        duration_ms: float,
        mode: str = "extraction",
        global_stats: Optional[Dict[str, Any]] = None,
    ) -> None:
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
        
        # Extract output based
        output_data = None
        
        # Handle DataFrame results from ranking mode or filtering mode
        if isinstance(result, pd.DataFrame):
            # Per agent di ranking, vogliamo mostrare le colonne che hanno influenzato il punteggio
            agent_type = agent_name.replace("-agent", "").replace("-extractor", "").replace("-extraction", "").replace("_", "-")
            
            # Mappa prefissi colonne per ogni agente
            prefix_map = {
                "property_technical": "property_technical_",
                "location": "location_",
                "ape": "ape_",
                "normative": "normative_",
                "poi": "poi_"
            }
            prefix = None
            for k, v in prefix_map.items():
                if k in agent_type:
                    prefix = v
                    break
            
            if mode == "ranking" and prefix:
                # Colonne "Involved": score, rank_position, multiplier, weight e colonne sorgente
                involved_cols = ["id"]
                score_col = f"{prefix}score"
                
                # Cerchiamo tutte le colonne che iniziano con il prefisso dell'agente (transparency cols)
                transparency_cols = [c for c in result.columns if c.startswith(prefix) or c.startswith(f"{prefix}rank_") or c.startswith(f"{prefix}weight_")]
                involved_cols.extend([c for c in transparency_cols if c not in involved_cols])
                
                # Aggiungiamo colonne di input rilevanti definite nelle costanti
                from app.core.constants import APE_AGENT_COLUMNS, PROPERTY_TECHNICAL_AGENT_COLUMNS, NORMATIVE_AGENT_COLUMNS, POI_AGENT_COLUMNS
                source_cols_map = {
                    "property_technical": PROPERTY_TECHNICAL_AGENT_COLUMNS,
                    "location": ["distanza_km", "poi_riferimento"],
                    "ape": APE_AGENT_COLUMNS,
                    "normative": NORMATIVE_AGENT_COLUMNS,
                    "poi": POI_AGENT_COLUMNS
                }
                
                agent_key = next((k for k in source_cols_map if k in agent_type), None)
                source_cols = []
                if agent_key:
                    source_cols = [c for c in source_cols_map[agent_key] if c in result.columns]
                    involved_cols.extend([c for c in source_cols if c not in involved_cols])
                
                # INPUT: Nomi delle colonne coinvolte (solo sorgenti)
                input_data = ", ".join(source_cols) if source_cols else ", ".join([c for c in involved_cols if c != "id"])
                
                # OUTPUT: Formula per immobile (primi 20)
                ranking_entries = []
                for _, row in result.iterrows():
                    formula_parts = []
                    
                    if agent_name == "ranking-agent":
                        # Final global ranking score
                        scores = []
                        for agent in ["location", "normative", "ape", "property_technical", "poi"]:
                            sc = row.get(f"{agent}_score", 0.0)
                            w = row.get(f"ranking_weight_{agent}", 0.0)
                            scores.append(f"{agent}_score({sc}) * Weight({w})")
                        
                        formula_list = ["RankingSum("] + [f"  {s}," for s in scores[:-1]] + [f"  {scores[-1]}", ")"]
                    elif "property_technical" in agent_type:
                        rank_pos = row.get(f"{prefix}rank_position", "N/A")
                        formula_list = [f"100 / Position({rank_pos})" if rank_pos != "N/A" else "0 (Non corrispondente)"]
                    elif "location" in agent_type:
                        dist = row.get("distanza_km")
                        poi = row.get("poi_riferimento")
                        score = row.get(score_col, 0)
                        if dist is not None and not pd.isna(dist) and poi and score > 0:
                            # Formula: 100 * exp(-(dist/2.5)^3)
                            formula_list = [f"100 * exp(-({dist:.2f}/2.5)^3)"]
                        else:
                            if score == 0:
                                if not poi or pd.isna(dist):
                                    formula_list = ["Località non identificata -> 0"]
                                else:
                                    formula_list = [f"Distanza eccessiva ({dist:.2f}km) -> 0"]
                            else:
                                formula_list = [f"Score: {score}"]
                    elif "poi" in agent_type or "ape" in agent_type or "normative" in agent_type:
                        # Queste logiche usano mediamente dei partial scores (0-100)
                        partial_cols = [c for c in result.columns if f"{prefix}partial_score_" in c]
                        
                        if partial_cols:
                            weighted_parts = []
                            for pc in partial_cols:
                                col_name = pc.replace(f"{prefix}partial_score_", "")
                                if col_name not in result.columns:
                                    continue
                                
                                val_raw = row.get(col_name)
                                score_pt = row.get(pc)
                                weight = row.get(f"{prefix}weight_{col_name}", 1.0 / len(partial_cols))
                                
                                # Caso Speciale: Classe Energetica (Categorico)
                                if col_name == "classe_energetica_ape":
                                    rank_pos = row.get(f"ape_rank_position_{col_name}", "N/A")
                                    if rank_pos != "N/A":
                                        desc = f"{col_name}({val_raw})[Rank {rank_pos}/10]: 100*(1-{int(rank_pos)-1}/9)={score_pt}"
                                    else:
                                        desc = f"{col_name}({val_raw}): {score_pt}"
                                
                                # Caso Speciale: Normative Typology Rank
                                elif col_name == "tipologia_bene_immobile" and "normative" in agent_type:
                                    rank_pos = row.get(f"normative_rank_position_{col_name}", "N/A")
                                    if rank_pos != "N/A":
                                        desc = f"{col_name}({val_raw})[Rank {rank_pos}]: {score_pt}"
                                    else:
                                        desc = f"{col_name}({val_raw}): {score_pt}"

                                # Caso Numerico (Min-Max Scaling relativo al dataset via global_stats o locale)
                                else:
                                    try:
                                        if pd.api.types.is_numeric_dtype(result[col_name]):
                                            # Prefer GLOBAL stats if available (deterministic reference)
                                            col_stats = global_stats.get(col_name) if global_stats else None
                                            if col_stats and isinstance(col_stats, dict) and "min" in col_stats and "max" in col_stats:
                                                c_min = float(col_stats["min"])
                                                c_max = float(col_stats["max"])
                                                ref_type = "[Global Ref]"
                                            else:
                                                c_vals = pd.to_numeric(result[col_name], errors='coerce').dropna()
                                                c_min = c_vals.min()
                                                c_max = c_vals.max()
                                                ref_type = "[Local Range]"
                                                
                                            val_num = float(val_raw) if val_raw not in [None, "N/D", "N/A"] else 0
                                            
                                            if c_max == c_min:
                                                desc = f"{col_name}({val_raw}): 100 {ref_type}"
                                            else:
                                                f_up = round(100 * (val_num - c_min) / (c_max - c_min), 1)
                                                f_down = round(100 * (c_max - val_num) / (c_max - c_min), 1)
                                                
                                                if abs(f_up - score_pt) < 1.0:
                                                    desc = f"{col_name}: 100*({val_num}-{c_min})/({c_max}-{c_min})={score_pt} {ref_type}"
                                                elif abs(f_down - score_pt) < 1.0:
                                                    desc = f"{col_name}: 100*({c_max}-{val_num})/({c_max}-{c_min})={score_pt} {ref_type}"
                                                else:
                                                    desc = f"{col_name}({val_num}) [Min {c_min}, Max {c_max}]: {score_pt} {ref_type}"
                                        else:
                                            desc = f"{col_name}({val_raw}): {score_pt} (Match)"
                                    except:
                                        desc = f"{col_name}({val_raw}): {score_pt}"
                                
                                weighted_parts.append(f"{desc} * Weight({weight:.3f})")

                            if len(weighted_parts) > 1:
                                formula_list = ["Sum("] + [f"  {p}," for p in weighted_parts[:-1]] + [f"  {weighted_parts[-1]}", ")"]
                            else:
                                formula_list = [f"{weighted_parts[0]}"]
                        else:
                            # Fallback generico
                            val_main = row.get(source_cols[0], "N/D") if source_cols else "N/D"
                            formula_list = [f"Score({val_main})"]
                    else:
                        formula_list = ["Logic Default"]

                    ranking_entries.append({
                        "id": row["id"],
                        "score": row.get(score_col, 0),
                        "formula": formula_list
                    })
                
                output_data = ranking_entries
            else:
                # Comportamento standard per DataFrame (es. filtraggio)
                output_data = json.loads(result.to_json(orient="records"))
                input_data = f"{mode.capitalize()} mode: {len(result)} records"
        elif agent_name == "relaxation-agent":
            # Per l'agente di rilassamento, mostriamo i tentativi effettuati come input
            # e la query finale scelta come output
            if hasattr(result, 'attempts') and result.attempts:
                input_data = result.attempts
                output_data = result.final_sql or result.raw_text
            else:
                input_data = result.raw_text
                output_data = "Nessuna proposta applicata"
        elif agent_name == "ranking-agent":
            # For ranking agent, include both ranking and weights for transparency
            output_data = {}
            if hasattr(result, 'ranking') and result.ranking:
                output_data["ranking"] = [r.model_dump() for r in result.ranking.ranking] if hasattr(result.ranking.ranking[0], 'model_dump') else result.ranking.ranking
            if hasattr(result, 'weights'):
                output_data["weights"] = result.weights.model_dump()
            if hasattr(result, 'reasoning'):
                output_data["reasoning"] = result.reasoning
        elif agent_name == "poi-agent":
            # For POI agent (filtering), show requirements
            if hasattr(result, 'requisiti'):
                output_data = {
                    "requisiti": result.requisiti
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
            "output": output_data
        }
        state["agent_trace"].append(entry)

        # SE esiste un logger di valutazione attivo (es. durante i test sintetici), propaga il log
        from app.services.agent_logger import get_active_evaluation_logger
        eval_logger = get_active_evaluation_logger()
        if eval_logger:
            eval_logger.log_agent_execution(
                agent_name=agent_name,
                input_data=input_data,
                output_data=result, # Passiamo il result originale per permettere al logger di estrarre ciò che gli serve
                execution_time_ms=duration_ms,
                agent_mode=mode
            )

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def _update_progress(self, state: GraphState, key: str, message: str, status: str = "current"):
        if state["set_progress"]:
            # Find index by key in step_definitions
            idx = -1
            for i, step in enumerate(state["step_definitions"]):
                if step["key"] == key:
                    idx = i
                    break

            if idx != -1:
                state["steps_state"][idx]["state"] = status
                state["steps_state"][idx]["detail"] = message
                
                # If we are marking something as current/done, ensure previous ones are done
                # (but only if they are not already current - to support parallel)
                if status in ["current", "done"]:
                    for i in range(idx):
                        if state["steps_state"][i]["state"] == "pending":
                            state["steps_state"][i]["state"] = "done"
                            state["steps_state"][i]["detail"] = ""
            
            total_steps = len(state["step_definitions"])
            # Use found index + 1 for percentage calculation
            step_num = idx + 1 if idx != -1 else 1 # Fallback to 1 if not found
            percent = min(100, step_num * 100 / total_steps) if total_steps > 0 else 0

            state["set_progress"]((percent, state["steps_state"]))

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

                if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
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
                    # Categorie - Gestione smart per evitare prompt troppo grandi
                    unique_count = df[col].nunique()
                    
                    if unique_count > 100:
                        # Troppi valori unici (es. IDs, particelle), mostriamo solo statistiche aggregate
                        stats[col] = {
                            "unique_values_count": int(unique_count),
                            "top_10_values": df[col].value_counts().head(10).to_dict(),
                            "note": f"Colonna con alta cardinalità ({unique_count} valori). Mostrati solo i primi 10 per brevità."
                        }
                        continue

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
                        # Limita a primi 50 valori se non ci sono metadati
                        top_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:50]
                        stats[col] = {str(k): int(v) for k, v in top_items}
                        if len(counts) > 50:
                            stats[col]["_other_count"] = int(sum(v for k, v in list(counts.items())[50:]))

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
        self._update_progress(state, "ranking_init", "Agente di Analisi & Priorità in ascolto...")
        query = state["query"]
        logger.info(f"Starting analysis for query: {query} (Architecture: {self.architecture})")

        # --- BASELINE PATH: Unified Planner ---
        if self.architecture == "baseline":
            return self._unified_analysis(state)

        # --- MULTIAGENT PATH: Parallel Technical Agents ---
        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating request analysis...")
            time.sleep(2)

            # Mock Typology
            state["property_technical_result"] = MOCK_PROPERTY_TECHNICAL
            state["context"].property_technical_result = MOCK_PROPERTY_TECHNICAL

            # Mock Location
            state["context"].locations = MOCK_LOCATION.places

            # Mock Strategy - REMOVED legacy metrics_plan
            state["use_case_str"] = "Mock Use Case Strategy"

            # Populate Gemini responses needed for UI
            state["gemini_responses"]["property_technical_extraction"] = {
                "response": MOCK_PROPERTY_TECHNICAL.raw_text,
                "typologies": MOCK_PROPERTY_TECHNICAL.typologies if hasattr(MOCK_PROPERTY_TECHNICAL, 'typologies') else [],
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

        # 1. Define ALL tasks (Ranking + 5 Technicians) in Parallel
        # We run Ranking simultaneously with the others to save the sequential delay,
        # as all agents are usually active per system instructions.
        
        base_dataset = state.get("base_dataset")
        dataset_path = state.get("dataset_path")

        def run_ranking():
            start_t = time.time()
            self._update_progress(state, "ranking_init", "Analizzo la priorità dei requisiti...")
            logger.info("Executing RankingAgent (Parallel)")
            result = self.ranking_agent.run(query=query, mode="filtering")
            logger.info("RankingAgent completed")
            return result, (time.time() - start_t) * 1000

        def run_property_technical():
            start_t = time.time()
            self._update_progress(state, "property_technical", "Analisi tecnica...")
            prop_stats = {}
            if state.get("use_data_knowledge", True):
                prop_stats = self._get_column_statistics(
                    columns=PROPERTY_TECHNICAL_AGENT_COLUMNS,
                    dataset_path=dataset_path, dataset_df=base_dataset,
                    db_metadata=state.get("db_metadata")
                )
            result = self.property_technical_agent.run(
                query=query, mode="filtering",
                available_typologies=str(state["db_metadata"].get("tipologia_bene_immobile", {}).get("values", [])),
                statistics=prop_stats
            )
            logger.info("PropertyTechnicalAgent completed")
            return result, (time.time() - start_t) * 1000

        def run_location():
            start_t = time.time()
            self._update_progress(state, "location", "Ricerca geografica...")
            result = self.location_agent.run(query=query)
            logger.info("LocationAgent completed")
            return result, (time.time() - start_t) * 1000

        def run_ape():
            start_t = time.time()
            if base_dataset is not None or dataset_path is not None:
                self._update_progress(state, "ape", "Valutazione energetica...")
                ape_stats = {}
                if state.get("use_data_knowledge", True):
                    ape_stats = self._get_column_statistics(
                        columns=APE_AGENT_COLUMNS, 
                        dataset_path=dataset_path, 
                        dataset_df=base_dataset,
                        target_not_na_col="classe_energetica_ape",
                        db_metadata=state.get("db_metadata")
                    )
                result = self.ape_agent.run(
                    query=query, mode="filtering",
                    statistics=ape_stats, score_legend=APE_SCORE_LEGEND,
                )
                logger.info("ApeAgent completed")
                return result, (time.time() - start_t) * 1000
            return None, 0

        def run_poi():
            start_t = time.time()
            self._update_progress(state, "poi", "Analisi servizi...")
            poi_stats = {}
            if state.get("use_data_knowledge", True):
                poi_stats = self._get_column_statistics(
                    columns=POI_AGENT_COLUMNS,
                    dataset_path=dataset_path, dataset_df=base_dataset,
                    db_metadata=state.get("db_metadata")
                )
            result = self.poi_agent.run(query=query, mode="filtering", statistics=poi_stats)
            logger.info("PoiAgent completed")
            return result, (time.time() - start_t) * 1000
        
        def run_normative():
            start_t = time.time()
            self._update_progress(state, "normative", "Verifica norme...")
            norm_stats = {}
            if state.get("use_data_knowledge", True) and (base_dataset is not None or dataset_path is not None):
                norm_stats = self._get_column_statistics(
                    columns=NORMATIVE_AGENT_COLUMNS,
                    dataset_path=dataset_path, dataset_df=base_dataset,
                    db_metadata=state.get("db_metadata")
                )
            result = self.normative_agent.run(query=query, available_columns=NORMATIVE_AGENT_COLUMNS, statistics=norm_stats)
            logger.info("NormativeAgent completed")
            return result, (time.time() - start_t) * 1000

        # 2. Execute all in parallel
        # We start EVERYTHING since prompt_config enforces all agents in ranking anyway.
        active_tasks = {
            "ranking": run_ranking,
            "property_technical": run_property_technical,
            "location": run_location,
            "ape": run_ape,
            "poi": run_poi,
            "normative": run_normative
        }
        
        # Filter out disabled agents for ablation study
        disabled = state.get("disabled_agents", [])
        if disabled:
            logger.info(f"Ablation mode: Disabling agents: {disabled}")
            active_tasks = {k: v for k, v in active_tasks.items() if k not in disabled}

        results = {k: None for k in active_tasks.keys()}
        logger.info(f"Executing active agents in parallel: {', '.join(active_tasks.keys())}")
        
        with ThreadPoolExecutor(max_workers=len(active_tasks)) as executor:
            future_to_name = {executor.submit(task): name for name, task in active_tasks.items()}
            for future in as_completed(future_to_name):
                agent_name = future_to_name[future]
                try:
                    res, duration = future.result()
                    results[agent_name] = res
                    if res:
                        # Map to correct trace name
                        trace_name = "ranking-agent" if agent_name == "ranking" else f"{agent_name}-agent"
                        self._log_execution(state, trace_name, res, duration)
                        
                    # Mark step as done
                    ui_key = "ranking_init" if agent_name == "ranking" else agent_name
                    self._update_progress(state, ui_key, "", status="done")
                except Exception as e:
                    logger.error(f"Error executing {agent_name}: {e}")

        # 3. Collect Results
        ranking_result = results.get("ranking")
        state["ranking_result"] = ranking_result
        
        property_technical_result = results.get("property_technical")
        loc_result = results.get("location")
        ape_result = results.get("ape")
        poi_result = results.get("poi")
        normative_result = results.get("normative")

        # Process PropertyTechnical
        typologies = []
        if property_technical_result:
            prop_data = safe_extract_json(property_technical_result.raw_text, schema=PropertyTechnicalResponse)
            typologies = prop_data.typologies if prop_data else []
            state["gemini_responses"]["property_technical_extraction"] = {
                "prompt": (
                    property_technical_result.prompt.model_dump() if property_technical_result.prompt else None
                ),
                "response": property_technical_result.raw_text,
                "typologies": typologies,
            }
        else:
            state["gemini_responses"]["property_technical_extraction"] = {
                "prompt": None,
                "response": "Agente disattivato per irrilevanza",
                "typologies": [],
            }
        state["property_technical_result"] = property_technical_result
        state["context"].property_technical_result = property_technical_result

        # Process Location
        places = []
        if loc_result:
            loc_data = safe_extract_json(loc_result.raw_text, schema=LocationResponse)
            places = loc_data.places if loc_data else []
            state["gemini_responses"]["location_extraction"] = {
                "prompt": loc_result.prompt.model_dump() if loc_result.prompt else None,
                "response": loc_result.raw_text,
                "places": [p.model_dump() for p in places],
            }
        else:
            state["gemini_responses"]["location_extraction"] = {
                "prompt": None,
                "response": "Agente disattivato per irrilevanza",
                "places": [],
            }
        state["context"].locations = places
        
        # If no places found after execution, remove step from UI
        if loc_result and not places:
             logger.info(" LocationAgent non ha trovato luoghi: rimuovo lo step dalla UI.")
             state["step_definitions"] = [s for s in state["step_definitions"] if s["key"] != "location"]
             state["steps_state"] = [s for s in state["steps_state"] if s["label"] != "Individuo una posizione geografica di ricerca..."]
             # Force update to refresh UI
             self._update_progress(state, "ranking_init", "", status="done")

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
                "requisiti": poi_data.get('requisiti', []),
                "found": poi_data.get('found', False)
            }
        else:
            state["gemini_responses"]["poi_analysis"] = {
                "prompt": None,
                "response": "Agente disattivato per irrilevanza",
                "requisiti": [],
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
                "requisiti": ape_data.get('requisiti', []),
                "found": ape_data.get("found", False)
            }
        else:
            state["gemini_responses"]["ape_analysis"] = {
                "prompt": None,
                "response": "Agente disattivato per irrilevanza",
                "requisiti": [],
                "found": False
            }

        # Process APE Text for Context
        ape_text = ""
        if ape_data and ape_data.get("found"):
            ape_reqs = ape_data.get("requisiti", [])
            if ape_reqs:
                target_cols = [r.get('colonna_target') for r in ape_reqs if isinstance(r, dict)]
                ape_text = f"\n\nAnalisi Energetica: L'utente ha espresso necessità relative all'efficienza (APE). Requisiti su: {', '.join(target_cols)}."

        # Process POI Text for Context
        poi_text = ""
        if poi_data:
            poi_requisiti = poi_data.get('requisiti', [])
            # Consider high priority if value is relatively high (e.g. >= 3.0)
            def safe_float_compare(v, threshold):
                if isinstance(v, list):
                    v = v[0] if v else 0
                try:
                    return float(v) >= threshold
                except (ValueError, TypeError):
                    return False

            high_priority = [r.get('colonna_target') for r in poi_requisiti if isinstance(r, dict) and safe_float_compare(r.get('valore', 0), 3.0)]
            if high_priority:
                poi_text = f"\n\nAnalisi POI: L'utente ha espresso preferenza per: {', '.join(high_priority)} con soglie di qualità elevate."
            elif poi_requisiti:
                all_targets = [r.get('colonna_target') for r in poi_requisiti if isinstance(r, dict)]
                poi_text = f"\n\nAnalisi POI: Categorie rilevanti: {', '.join(all_targets)}."

        # Save normative result in state and context
        state["normative_result"] = normative_result
        state["context"].normative_result = normative_result
        norm_data = safe_extract_json(normative_result.raw_text, schema=NormativeResponse) if normative_result else None
        if normative_result:
            state["gemini_responses"]["normative_analysis"] = {
                "prompt": normative_result.prompt.model_dump() if normative_result.prompt else None,
                "response": normative_result.raw_text,
                "normative_info": normative_result.raw_text,
                "sources": normative_result.sources,
                "found": norm_data.found if norm_data else False
            }
        else:
            state["gemini_responses"]["normative_analysis"] = {
                "prompt": None,
                "response": "Agente disattivato per irrilevanza",
                "normative_info": "",
                "sources": [],
            }

        # Build use_case_str from agent results (no needs_metric)
        use_case_parts = []
        if ape_text:
            use_case_parts.append(ape_text.strip())
        if poi_text:
            use_case_parts.append(poi_text.strip())
        if normative_result:
            use_case_parts.append(f"Normative: {normative_result.raw_text[:200]}")
        state["use_case_str"] = "\n".join(use_case_parts)

        return state

    def _fix_sql_quotes(self, sql: str) -> str:
        """
        Riparazione euristica di errori comuni di quotatura degli LLM.
        Gestisce casi come 'valore'' (doppio apice finale errato) o apici mancanti.
        """
        if not sql:
            return sql
        
        sql = sql.strip()
        
        # Caso 1: Doppio apice finale con conteggio totale dispari (hallucination di escaping)
        if sql.endswith("''") and sql.count("'") % 2 != 0:
             sql = sql[:-1]
             
        # Caso 2: Conteggio dispari di apici (apice mancante alla fine)
        # Se l'ultimo apice è seguito da testo o chiusura parentesi senza un apice di chiusura
        if sql.count("'") % 2 != 0:
            # Proviamo a chiudere la stringa se sembra sensato
            if sql[-1] not in ["'", ";", " "]:
                sql += "'"
                
        return sql

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
                        if len(val) == 1:
                            val_str = f"'{val[0]}'" if isinstance(val[0], str) else str(val[0])
                            formatted.append(f"{col} {op} {val_str}")
                        else:
                            val_str = "(" + ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in val) + ")"
                            # Se l'operatore non è IN/NOT IN, l'uso di una lista potrebbe essere tecnicamente errato per l'agente SQL
                            # ma lo passiamo comunque confidando nella sua capacità di correzione.
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
            state, "sql", ""
        )

        if state.get("sql_query") and retry_count == 0:
            logger.info("SQL already generated by Baseline Planner, skipping SQLAgent.")
            return state

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
        property_technical_result = state.get("property_technical_result")
        poi_result = state.get("poi_result")
        ape_result = state.get("ape_result")
        normative_result = state.get("normative_result")
        
        # Format locations as JSON string for clarity: only lat, lon, radius_km
        locations_list = state["gemini_responses"].get("location_extraction", {}).get("places", [])
        filtered_locations = []
        for loc in locations_list:
            filtered_locations.append({
                "lat": loc.get("lat"),
                "lon": loc.get("lon"),
                "radius_km": loc.get("radius_km"),
                "threshold": loc.get("threshold")
            })

        # Aggregate all requirements into a single list
        all_reqs = []
        # 1. Property Technical
        if property_technical_result and property_technical_result.raw_text != "N/D":
            try:
                t_data = safe_extract_json(property_technical_result.raw_text)
                if t_data and isinstance(t_data, dict) and t_data.get("typologies"):
                    typs = t_data['typologies']
                    all_reqs.append(f"tipologia_bene_immobile: {', '.join(typs)}")
            except: pass
            
            # PropertyTechnicalAgent now also extracts structured requirements (ID, contracts, surfaces)
            prop_fmt = self._format_agent_requirements(property_technical_result)
            if prop_fmt != "N/D" and "Nessun requisito" not in prop_fmt:
                all_reqs.append(prop_fmt)

        # 2. Locations
        if filtered_locations:
            for loc in filtered_locations:
                radius_str = f"raggio {loc['radius_km']}km"
                if loc.get("threshold"):
                    radius_str += f", threshold {loc['threshold']}km"
                all_reqs.append(f"Coordinate: {loc['lat']}, {loc['lon']} ({radius_str})")

        # 3. Structured requirements (APE, POI, Normative)
        # Use helper for APE, Normative, and POI
        ape_fmt = self._format_agent_requirements(ape_result)
        if ape_fmt != "N/D" and "Nessun requisito" not in ape_fmt:
            all_reqs.append(ape_fmt)
            
        norm_fmt = self._format_agent_requirements(normative_result)
        if norm_fmt != "N/D" and "Nessun requisito" not in norm_fmt:
             all_reqs.append(norm_fmt)

        poi_fmt = self._format_agent_requirements(poi_result)
        if poi_fmt != "N/D" and "Nessun requisito" not in poi_fmt:
            all_reqs.append(poi_fmt)

        all_requirements_str = "\n".join([f"- {r}" for r in all_reqs]) if all_reqs else "N/D"

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
        is_sql_error = bool(state.get("execution_error"))
        effective_failed_query = failed_query
        effective_error_msg = error_msg

        # Prepare technical scheme (all columns and their types)
        db_schema_obj = state.get("db_schema", {})
        col_types = db_schema_obj.get("types", {})
        scheme_str = "\n".join([f"{col}: {dtype}" for col, dtype in col_types.items()])

        start_t = time.time()
        sql_result = self.sql_agent.run(
            query=query, # use original query
            scheme=scheme_str,
            all_requirements=all_requirements_str,
            location=loc_obj,
            failed_query=effective_failed_query,
            error_msg=effective_error_msg,
            db_metadata=json.dumps(state.get("db_metadata", {}), ensure_ascii=False),
            raw_response=None
        )
        duration_ms = (time.time() - start_t) * 1000

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
        
        self._log_execution(state, "sql-agent", sql_result, duration_ms)
        return state

    def _execute_sql(self, state: GraphState) -> GraphState:
        self._update_progress(state, "sql", "")
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
            if state["retry_count"] < 3:
                return "retry"
            return "fallback"

        if state["selected_data"] is not None and not state["selected_data"].empty:
            return "continue"

        return "fallback"

    def _should_broker_review(self, state: GraphState) -> str:
        """Route to broker only if there are evaluation results."""
        if state["context"].evaluation_results:
            return "continue"
        return "skip"

    def _handle_retry(self, state: GraphState) -> GraphState:
        return {
            "retry_count": state["retry_count"] + 1, 
            "last_retry_reason": "error"
        }

    def _fallback_results(self, state: GraphState) -> GraphState:
        """
        Fallback when SQL queries fail after max retries.
        Returns top results from full dataset so user always gets something.
        """
        self._update_progress(
            state, "sql", ""
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
        self._update_progress(state, "sql", "")
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

        state["selected_data"] = enriched_data # Update state
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
        self._update_progress(state, "ranking", "")
        query = state["query"]
        
        # In mock mode, use defaults or simulated weights
        if USE_MOCK_RESPONSES:
            weights = RankingWeights(location=0.3, normative=0.1, ape=0.2, property_technical=0.2, poi=0.2)
            state["ranking_result"] = RankingAgentResult(raw_text="{}", weights=weights)
        else:
            # Check if ranking was already computed in baseline phase
            ranking_result = state.get("ranking_result")
            if ranking_result and self.architecture == "baseline":
                logger.info("Ranking weights already provided by Baseline Planner, skipping RankingAgent call.")
                state["context"].ranking_result = ranking_result
                return state

            already_ran = ranking_result is not None

            if not ranking_result:
                start_t = time.time()
                ranking_result = self.ranking_agent.run(
                    query=query, 
                    mode="filtering", 
                    db_metadata=state.get("db_metadata")
                )
                duration_ms = (time.time() - start_t) * 1000
                state["ranking_result"] = ranking_result
            else:
                duration_ms = 0 # Already ran

            state["context"].ranking_result = ranking_result
            
            state["gemini_responses"]["ranking_weights"] = {
                "prompt": ranking_result.prompt.model_dump() if ranking_result.prompt else None,
                "response": ranking_result.raw_text,
                "weights": ranking_result.weights.model_dump()
            }
        
            # Only log trace if it wasn't already logged in parallel phase
            if not already_ran:
                self._log_execution(state, "ranking-agent", ranking_result, duration_ms, mode="ranking")
        
        return state


    def _rank_results(self, state: GraphState) -> GraphState:
        self._update_progress(state, "ranking", "")
        df = state["selected_data"]
        if df is None or df.empty:
            return state

        # Fix: Ensure ID is string for matching with agent results (which use string IDs from JSON)
        if "id" in df.columns:
            df["id"] = df["id"].astype(str)

        ranking_res = state.get("ranking_result")
        weights = ranking_res.weights if ranking_res else RankingWeights()
        
        # Get active agents from ranking result
        active_agents = []
        if ranking_res and ranking_res.ranking:
            # Extract agent names from RankedAgent list
            active_agents = [r.agent_name for r in ranking_res.ranking.ranking]
        else:
            # Fallback to all if ranking failed
            active_agents = ["location", "normative", "ape", "property_technical", "poi"]
        
        logger.info(f"Active agents for ranking: {active_agents}")

        # Identify agents that actually found something during filtering phase
        # to exclude those that returned nothing from final ranking determination.
        really_found_agents = []
        
        # 1. Location
        if state["context"].locations:
            really_found_agents.append("location")
            
        # 2. Property Technical
        if state.get("property_technical_result"):
            t_data = safe_extract_json(state["property_technical_result"].raw_text, schema=PropertyTechnicalResponse)
            if t_data and (t_data.typologies or t_data.requisiti):
                really_found_agents.append("property_technical")
                
        # 3. APE
        if state.get("ape_result"):
            a_data = safe_extract_json(state["ape_result"].raw_text, schema=ApeResponse)
            if a_data and (a_data.found or (a_data.requisiti and len(a_data.requisiti) > 0)):
                really_found_agents.append("ape")
                
        # 4. POI
        if state.get("poi_result"):
            p_data = safe_extract_json(state["poi_result"].raw_text)
            if p_data and (p_data.get("found") or (p_data.get("requisiti") and len(p_data["requisiti"]) > 0)):
                really_found_agents.append("poi")
                
        # 5. Normative
        if state.get("normative_result"):
            n_data = safe_extract_json(state["normative_result"].raw_text, schema=NormativeResponse)
            if n_data and (n_data.found or (n_data.requisiti and len(n_data.requisiti) > 0)):
                really_found_agents.append("normative")

        logger.info("Agents with found requirements in filtering phase: {}", really_found_agents)

        # Check for agents that are in active_agents (selected by query) but didn't find anything
        agents_to_exclude = [a for a in active_agents if a not in really_found_agents and getattr(weights, a, 0.0) > 0]
        
        if agents_to_exclude:
            logger.info(" Excluding agents from ranking due to no results in filtering: {}", agents_to_exclude)
            
            # Copy weights and identify target for redistribution
            current_weights_dict = weights.model_dump()
            
            # Remaining agents from active_agents that found something
            active_and_found = [a for a in active_agents if a in really_found_agents]
            
            # Sum of weights of agents to be kept
            remaining_weight_sum = sum(current_weights_dict[a] for a in active_and_found)
            
            if remaining_weight_sum > 0:
                # Redistribute the total weight of excluded agents to remaining found agents
                new_weights_dict = {}
                for a in ["location", "property_technical", "ape", "poi", "normative"]:
                    if a in active_and_found:
                        # Proportional redistribution
                        new_weights_dict[a] = round(current_weights_dict[a] / remaining_weight_sum, 2)
                    else:
                        new_weights_dict[a] = 0.0

                # Adjustment for rounding to ensure sum is exactly 1.0
                current_total = sum(new_weights_dict.values())
                diff = round(1.0 - current_total, 2)
                if diff != 0 and active_and_found:
                    # Adjust the agent with the highest new weight
                    max_agent = max(active_and_found, key=lambda a: new_weights_dict[a])
                    new_weights_dict[max_agent] = round(new_weights_dict[max_agent] + diff, 2)
                
                weights = RankingWeights(**new_weights_dict)
                logger.info(" Adjusted ranking weights: {}", new_weights_dict)
                
                # Update active_agents to only include those that really found something
                # This avoids running ranking mode for agents with 0 weight
                active_agents = active_and_found
            else:
                logger.warning("All active agents returned no requirements. Forcing all weights to 0.0 as requested.")
                # AZZERAMENTO TOTALE: se nessun agente produce risultati di filtro, i pesi di ranking
                # per il calcolo devono essere portati matematicamente a 0.0
                zero_weights_dict = {a: 0.0 for a in ["location", "property_technical", "ape", "poi", "normative"]}
                weights = RankingWeights(**zero_weights_dict)
                active_agents = []  # Nessun agente deve girare in modalità ranking part-2

        # Compute global statistics for all relevant columns for ranking
        # This allows agents to normalize scores against the entire dataset instead of the current subset.
        all_ranking_cols = list(set(APE_AGENT_COLUMNS + NORMATIVE_AGENT_COLUMNS + POI_AGENT_COLUMNS + PROPERTY_TECHNICAL_AGENT_COLUMNS))
        global_stats = self._get_column_statistics(
            columns=all_ranking_cols,
            dataset_path=state.get("dataset_path"),
            dataset_df=state.get("base_dataset"),
            db_metadata=state.get("db_metadata")
        )

        # Define ranking tasks for parallel execution
        def rank_property_technical():
            start_t = time.time()
            res = state.get("property_technical_result")
            if res:
                data = safe_extract_json(res.raw_text, schema=PropertyTechnicalResponse)
                if data and (data.typologies or data.requisiti):
                    # For ranking, typologies is the main driver, but we pass requirements for numerical scoring
                    tmp = self.property_technical_agent.run(
                        mode="ranking", 
                        df=df.copy(), 
                        ranked_typologies=data.typologies,
                        requirements=data.requisiti,
                        global_stats=global_stats
                    )
                    return tmp, (time.time() - start_t) * 1000
            tmp = df.copy()
            tmp["property_technical_score"] = 0.0
            return tmp[["id", "property_technical_score"]], (time.time() - start_t) * 1000

        def rank_location():
            start_t = time.time()
            if state["context"].locations:
                 tmp = self.location_agent.run(mode="ranking", df=df.copy(), places=state["context"].locations)
                 return tmp, (time.time() - start_t) * 1000
            tmp = df.copy()
            tmp["location_score"] = 0.0
            return tmp[["id", "location_score"]], (time.time() - start_t) * 1000

        def rank_ape():
            start_t = time.time()
            res = state.get("ape_result")
            requirements = None
            if res:
                data = safe_extract_json(res.raw_text, schema=ApeResponse)
                if data and data.found:
                    requirements = data.requisiti
            
            tmp = self.ape_agent.run(mode="ranking", df=df.copy(), requirements=requirements, global_stats=global_stats)
            return tmp, (time.time() - start_t) * 1000

        def rank_normative():
            start_t = time.time()
            res = state.get("normative_result")
            if res:
                data = safe_extract_json(res.raw_text, schema=NormativeResponse)
                if data and data.found:
                    tmp = self.normative_agent.run(mode="ranking", df=df.copy(), requirements=data.requisiti, available_columns=NORMATIVE_AGENT_COLUMNS, global_stats=global_stats)
                    return tmp, (time.time() - start_t) * 1000
            tmp = df.copy()
            tmp["normative_score"] = 0.0
            return tmp[["id", "normative_score"]], (time.time() - start_t) * 1000

        def rank_poi():
            start_t = time.time()
            res = state.get("poi_result")
            if res:
                poi_data = safe_extract_json(res.raw_text)
                if poi_data and poi_data.get("requisiti"):
                    tmp = self.poi_agent.run(mode="ranking", df=df.copy(), requirements=poi_data.get("requisiti"), global_stats=global_stats)
                    return tmp, (time.time() - start_t) * 1000
            tmp = df.copy()
            tmp["poi_score"] = 0.0
            return tmp[["id", "poi_score"]], (time.time() - start_t) * 1000

        # Build active ranking tasks based on active_agents
        ranking_tasks = {}
        if "property_technical" in active_agents:
            ranking_tasks["property_technical"] = rank_property_technical
        if "location" in active_agents:
            ranking_tasks["location"] = rank_location
        if "ape" in active_agents:
            ranking_tasks["ape"] = rank_ape
        if "normative" in active_agents:
            ranking_tasks["normative"] = rank_normative
        if "poi" in active_agents:
            ranking_tasks["poi"] = rank_poi

        # Execute parallel ranking tasks (only for active agents)
        with ThreadPoolExecutor(max_workers=len(ranking_tasks) if ranking_tasks else 1) as executor:
            task_map = {
                executor.submit(task): name 
                for name, task in ranking_tasks.items()
            }
            
            for future in as_completed(task_map):
                name = task_map[future]
                try:
                    res_df, duration = future.result()
                    
                    # Log ranking results as JSON for UI visualization
                    if not res_df.empty:
                        # Transform to clean JSON (handles NaNs by converting to null)
                        # and put it at the top level for the UI to show an accordion
                        clean_json = res_df.to_json(orient="records")
                        state["gemini_responses"][f"{name}_ranking"] = {
                            "response": json.loads(clean_json)
                        }
                        
                        # Log this ranking agent execution to the trace
                        self._log_execution(state, f"{name}-agent", res_df, duration, mode="ranking", global_stats=global_stats)

                    # Aggiungiamo solo nuove colonne evitando duplicazioni
                    new_cols = [c for c in res_df.columns if c not in df.columns or c == "id"]
                    df = df.merge(res_df[new_cols], on="id", how="left")
                except Exception as e:
                    logger.error(f"Error in parallel ranking part {name}: {e}")
                    col = "ape_score" if name == "ape" else f"{name}_score"
                    if col not in df.columns:
                        df[col] = 0.0

        # Ensure all agent score columns exist (set to 0.0 for inactive agents)
        all_possible_agents = ["location", "normative", "ape", "property_technical", "poi"]
        for agent in all_possible_agents:
            score_col = "ape_score" if agent == "ape" else f"{agent}_score"
            if score_col not in df.columns:
                logger.info(f"Agent '{agent}' not active, setting {score_col} to 0.0")
                df[score_col] = 0.0

        # Calculate final weighted score via RankingAgent (ranking mode)
        start_t = time.time()
        df = self.ranking_agent.run(mode="ranking", df=df, weights=weights)
        duration_ms = (time.time() - start_t) * 1000
        
        # Log this final ranking step
        self._log_execution(state, "ranking-agent", df, duration_ms, mode="ranking")
        self._update_progress(state, "ranking", "", status="done")

        # Sort by total score
        df = df.sort_values(by="final_ranking_score", ascending=False)
        state["selected_data"] = df
        
        return state

    def _evaluate_results(self, state: GraphState) -> GraphState:
        enriched_data = state["selected_data"]

        # Restore top 10 as per user request
        llm_cap = MAX_LLM_CAP

        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating Evaluation...")
            self._update_progress(
                state, "evaluation", ""
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
                for idx, item_id in enumerate(enriched_data.head(llm_cap)["id"].tolist()):
                    if idx < len(mock_data):
                        res_dict = mock_data[idx]
                        res = EvaluationResult(**res_dict)
                        res.id = item_id
                        eval_results.append(res)
                        time.sleep(0.5)
                        self._update_progress(
                            state,
                            "evaluation",
                            "",
                        )

            state["context"].evaluation_results = eval_results
            if "evaluation" not in state["gemini_responses"]:
                state["gemini_responses"]["evaluation"] = {}
            state["gemini_responses"]["evaluation"]["results"] = [
                r.model_dump() for r in eval_results
            ]

            self._update_progress(
                state,
                "evaluation",
                "",
            )
            return state

        # Limit evaluation to top results defined by llm_cap
        eval_input_df = enriched_data.head(llm_cap).copy()
        eval_input_df["is_evaluated"] = True

        total_items = len(eval_input_df)
        self._update_progress(
            state,
            "evaluation",
            "",
        )

        # Evaluation batching
        # Increased batch size for faster models to reduce sequential overhead
        # Process one by one (batch size 1) as per user request
        batch_size = 1
        
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
            "property_technical_score",
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

            start_t = time.time()
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
            return eval_payload, (time.time() - start_t) * 1000

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(process_batch, batch): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(futures):
                try:
                    payload, duration = future.result()
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
                        "evaluation",
                        "",
                    )
                    
                    self._log_execution(state, "evaluation-agent", payload, duration, mode="evaluation")

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
            state, "evaluation", "", status="done"
        )
        return state

    def _broker_review(self, state: GraphState) -> GraphState:
        self._update_progress(state, "broker", "")

        if USE_MOCK_RESPONSES:
            logger.info("MOCK MODE: Simulating Broker Review...")
            time.sleep(1.5)
            state["broker_summary"] = MOCK_BROKER_SUMMARY
            state["gemini_responses"]["broker_review"] = MOCK_BROKER_SUMMARY
            return state

        eval_results = state["context"].evaluation_results

        # Create structured text for the broker
        candidates = []
        for i, res in enumerate(eval_results[:MAX_LLM_CAP]):  # Analyze top candidates
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
        self._update_progress(state, "broker", "", status="done")
        return state

    def _finalize_results(self, state: GraphState) -> GraphState:
        trace_len = len(state.get("agent_trace", []))
        logger.info(f"Finalizing results. Agent trace size: {trace_len}")

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
            state["match_count"] = 0
            state["context"].filtered_dataset_preview = []
            state["gemini_responses"]["agent_context"] = state["context"].model_dump()
            self._update_progress(state, "complete", "")
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
        overlay_cols = ["id", "is_match", "final_ranking_score", "distanza_km"]
        
        # Drop existing columns from map_df to avoid suffix collisions and ensure overlay wins
        cols_to_drop = [c for c in overlay_cols if c != "id" and c in map_df.columns]
        if cols_to_drop:
            map_df = map_df.drop(columns=cols_to_drop)

        if not enriched_data.empty:
            actual_overlay_cols = [c for c in overlay_cols if c in enriched_data.columns]
            overlay_df = enriched_data[actual_overlay_cols].drop_duplicates("id")
            map_df = pd.merge(map_df, overlay_df, on="id", how="left")

        # Default robusti per flag e score
        if "is_match" not in map_df.columns:
            map_df["is_match"] = False
        map_df["is_match"] = map_df["is_match"].fillna(False).astype(bool)

        if "final_ranking_score" in map_df.columns:
            map_df["final_ranking_score"] = pd.to_numeric(
                map_df["final_ranking_score"], errors="coerce"
            ).fillna(0)

        eval_results = state["context"].evaluation_results
        
        # The true "found" count is the number of matching properties
        total_matches = len(enriched_data)
        state["match_count"] = total_matches
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
                # Caso in cui eval_results esiste ma valutazioni_df è vuoto
                # (es. errore nel parsing dei singoli item)
                if "final_ranking_score" not in map_df.columns:
                    map_df["final_ranking_score"] = 0
                map_df["is_evaluated"] = False
                map_df["is_selected_by_llm"] = False
        else:
            # Caso in cui NON sono state proprio effettuate valutazioni (classico fallback)
            eval_ids = (
                enriched_data.head(llm_cap)["id"]
                if "id" in enriched_data.columns and llm_cap > 0
                else []
            )
            if "id" in map_df.columns:
                map_df["is_evaluated"] = map_df["id"].isin(eval_ids)
            else:
                map_df["is_evaluated"] = False
            
            # CRITICAL: Preserve existing final_ranking_score if it exists (from ranking_agent)
            if "final_ranking_score" not in map_df.columns:
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
                f"Trovati {total_matches} immobili corrispondenti. "
                f"Punti visibili in mappa: {shown_count} (limite {map_cap}). "
                f"LLM ha valutato {evaluated_total}/{llm_cap} elementi. "
            )
        else:
            msg = (
                f"Trovati {total_matches} immobili corrispondenti. "
                f"Punti visibili in mappa: {shown_count} (limite {map_cap}). "
                "Nessuna valutazione LLM disponibile."
            )

        state["status_msg"] = msg
        logger.info(msg)

        state["selected_data"] = map_df  # Risultato finale per la mappa
        state["gemini_responses"]["agent_context"] = state["context"].model_dump()
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
