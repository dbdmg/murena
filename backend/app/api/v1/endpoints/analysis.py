"""Analysis API endpoints.

Provides endpoints for starting and managing real estate analysis.
"""

import uuid
import ast
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker
import pandas as pd
import logging

from app.api.deps import get_current_user_optional
from app.database.connection import get_db
from app.database.models import User
from app.models.requests import AnalysisRequest
from app.models.responses import AnalysisResponse, AnalysisResults, AgentStepsResponse, AnalysisHistoryItem
from app.repositories import RunRepository
from app.core.config import settings
from app.utils.json_sanitizer import make_json_safe

logger = logging.getLogger(__name__)

router = APIRouter()


def _label_for_step_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return ""

    base_labels = {
        "location_extraction": "Location extraction",
        "property_technical_extraction": "Technical features",
        "needs_metric_plan": "Metrics and strategy",
        "use_case_generation": "Use case generation",
        "sql_generation": "SQL generation",
        "ape_analysis": "Energy analysis",
        "poi_analysis": "POI analysis",
        "evaluation": "Evaluation",
        "merge": "Result finalization",
        "broker_review": "Broker review",
        "agent_context": "Agent context",
        "_demo": "Demo metadata",
    }

    if key in base_labels:
        return base_labels[key]

    if key.startswith("sql_generation_retry_"):
        suffix = key.replace("sql_generation_retry_", "")
        return f"SQL generation (retry {suffix})"

    return key.replace("_", " ")


def _normalize_agent_step(
    key: str, value: object, *, include_prompt: bool, include_raw: bool
) -> dict:
    """Normalize one gemini_responses entry into a stable shape for the frontend."""

    step: dict = {
        "key": key,
        "label": _label_for_step_key(key),
        "prompt": None,
        "response": None,
        "data": None,
    }

    if not isinstance(value, dict):
        step["response"] = value
        return step

    prompt = value.get("prompt")
    if include_prompt and isinstance(prompt, dict):
        step["prompt"] = prompt

    # Try to pick a reasonable "response" field.
    response_candidate = None
    for k in (
        "response",
        "response_text",
        "raw_text",
        "raw",
        "text",
        "sql_query",
        "answer",
    ):
        if k in value and value.get(k) not in (None, ""):
            response_candidate = value.get(k)
            break

    if response_candidate is None and "results" in value:
        response_candidate = value.get("results")

    if include_raw:
        step["response"] = response_candidate
    else:
        # If response is huge/structured, keep it minimal unless explicitly requested.
        if isinstance(response_candidate, (dict, list)):
            step["response"] = None
        else:
            step["response"] = response_candidate

    data = {
        k: v
        for k, v in value.items()
        if k not in {"prompt", "raw_text", "raw", "response", "response_text", "text"}
    }
    if data:
        step["data"] = data

    return step


def generate_run_id() -> str:
    """Generate a unique run ID."""
    return str(uuid.uuid4()).replace("-", "")[:16]


def _find_repo_root(start: Path) -> Optional[Path]:
    for parent in start.parents:
        if (parent / "runs").exists():
            return parent
    return None


def _parse_bool(value: object) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _parse_float(value: object) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _parse_list_literal(value: object) -> Optional[list]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (list, tuple)):
            return list(parsed)
    except Exception:
        return None
    return None


def _load_demo_artifacts(demo_id: str, limit: int = 50) -> dict:
    """Load a demo run from runs/admin/<demo_id> (metadata.json + results.csv + optional gemini_responses.json).

    Returns an AnalysisResults-compatible dict.
    """

    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    repo_root = _find_repo_root(Path(__file__).resolve())
    if not repo_root:
        raise FileNotFoundError("Repository root with runs/ not found")

    run_dir = repo_root / "runs" / "admin" / demo_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"Demo run folder not found: {demo_id}")

    metadata_path = run_dir / "metadata.json"
    results_path = run_dir / "results.csv"
    gemini_path = run_dir / "gemini_responses.json"
    query_path = run_dir / "query.txt"
    if not metadata_path.exists():
        raise FileNotFoundError("metadata.json not found")
    if not results_path.exists():
        raise FileNotFoundError("results.csv not found")

    metadata = {}
    try:
        import json

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        metadata = {}

    query = metadata.get("query") or f"Demo: {demo_id}"
    if (not metadata.get("query")) and query_path.exists():
        try:
            query_text = query_path.read_text(encoding="utf-8").strip()
            if query_text:
                query = query_text
        except Exception:
            pass
    location_data = metadata.get("location_data")
    broker_summary = metadata.get("status_message")

    gemini_responses: dict = {"demo": True, "source": demo_id}
    if gemini_path.exists():
        try:
            import json

            parsed = json.loads(gemini_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                # Keep a small provenance marker while preserving the original structure.
                gemini_responses = {"_demo": {"source": demo_id}, **parsed}
        except Exception:
            gemini_responses = {
                "demo": True,
                "source": demo_id,
                "_error": "invalid gemini_responses.json",
            }

    city_from_location: Optional[str] = None
    if isinstance(location_data, list) and location_data:
        first_name = None
        if isinstance(location_data[0], list) and location_data[0]:
            first_name = location_data[0][0]
        if isinstance(first_name, str) and "," in first_name:
            city_from_location = first_name.split(",")[-1].strip() or None

    from app.models.responses import (
        EnergyScores,
        ProximityScores,
        Coordinates,
        BuildingResponse,
    )

    buildings: list[BuildingResponse] = []
    with results_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        for row in reader:
            if len(buildings) >= limit:
                break

            building_id = str(row.get("id") or "")
            if not building_id:
                continue

            lat = _parse_float(row.get("latitudine"))
            lon = _parse_float(row.get("longitudine"))
            if lat is None or lon is None:
                continue

            address = (row.get("indirizzo") or "").strip()
            civic = (row.get("numero_civico") or "").strip()
            full_address = (address + (f" {civic}" if civic else "")).strip() or None

            ape_scores = None
            ape_total = _parse_float(row.get("ape_score_total"))
            if ape_total is not None:

                def _to_int(x: object) -> Optional[int]:
                    val = _parse_float(x)
                    if val is None:
                        return None
                    return int(val)

                cls = _to_int(row.get("ape_score_classe"))
                sys_score = _to_int(row.get("ape_score_impianto"))
                env = _to_int(row.get("ape_score_involucro"))
                ren = _to_int(row.get("ape_score_rinnovabili"))
                if None not in {cls, sys_score, env, ren}:
                    ape_scores = EnergyScores(
                        total=float(ape_total),
                        class_score=cls,
                        system_score=sys_score,
                        envelope_score=env,
                        renewables_score=ren,
                    )

            poi_scores = None
            poi_any = any(
                row.get(k) not in (None, "")
                for k in [
                    "sanita",
                    "mobilita",
                    "verde",
                    "educazione",
                    "commerciale",
                    "sport",
                ]
            )
            if poi_any:
                poi_scores = ProximityScores(
                    healthcare=_parse_float(row.get("sanita")),
                    mobility=_parse_float(row.get("mobilita")),
                    greenery=_parse_float(row.get("verde")),
                    education=_parse_float(row.get("educazione")),
                    commerce=_parse_float(row.get("commerciale")),
                    sport=_parse_float(row.get("sport")),
                )

            ape_files = _parse_list_literal(row.get("lista_file_ape"))
            if not ape_files:
                ape_files = _parse_list_literal(row.get("list_file_ape_filtered"))

            buildings.append(
                BuildingResponse(
                    id=building_id,
                    address=full_address,
                    city=city_from_location,
                    coordinates=Coordinates(lat=float(lat), lon=float(lon)),
                    surface_area=_parse_float(row.get("superficie_di_riferimento_mq")),
                    construction_year=(row.get("epoca_costruzione") or None),
                    energy_class=(row.get("classe_energetica_ape") or None),
                    score=_parse_float(row.get("score"))
                    or _parse_float(row.get("ranking_score"))
                    or _parse_float(row.get("final_ranking_score")),
                    property_type=(row.get("tipologia_bene_immobile") or None),
                    legal_nature=(row.get("natura_giuridica_del_bene") or None),
                    cultural_constraint=(
                        row.get("vincolo_culturale_paesaggistico") or None
                    ),
                    purpose=(row.get("finalita") or None),
                    omi_zone=(row.get("zona_omi") or None),
                    cadastral_sheet=(row.get("foglio") or None),
                    cadastral_parcel=(row.get("particella") or None),
                    is_evaluated=bool(_parse_bool(row.get("is_evaluated")) or False),
                    meta_building=bool(_parse_bool(row.get("meta_immobile")) or False),
                    # New metadata fields
                    meta_immobile=bool(_parse_bool(row.get("meta_immobile")) or False),
                    canone_annuale=_parse_float(row.get("canone_annuale")),
                    tipo_detenzione_a_terzi=(
                        row.get("tipo_detenzione_a_terzi") or None
                    ),
                    data_decorrenza=(row.get("data_decorrenza") or None),
                    numero_immobili_per_catasto=_parse_float(
                        row.get("numero_immobili_per_catasto")
                    ),
                    id_list=(row.get("id_list") or None),
                    energy_scores=ape_scores,
                    proximity_scores=poi_scores,
                    energy_files=ape_files,
                    distance_km=_parse_float(row.get("distance_km") or row.get("distanza_km")),
                    energy_score=_parse_float(row.get("energy_score")),
                    location_score=_parse_float(row.get("location_score")),
                    regulatory_score=_parse_float(row.get("regulatory_score")),
                    building_score=_parse_float(row.get("building_score")),
                    proximity_score=_parse_float(row.get("proximity_score")),
                    description=(row.get("motivazione") or None),
                )
            )

    now = datetime.utcnow()
    created_at = now
    try:
        ts = metadata.get("timestamp")
        if isinstance(ts, str):
            created_at = datetime.fromisoformat(ts)
    except Exception:
        created_at = now

    return {
        "run_id": demo_id,
        "query": query,
        "status": "completed",
        "buildings": buildings,
        "location": location_data,
        "filters_applied": {"demo_source": demo_id},
        "gemini_responses": gemini_responses,
        "broker_summary": broker_summary or "Demo loaded",
        "created_at": created_at,
        "completed_at": now,
    }


@router.get("/{run_id}/gemini_responses")
async def get_run_gemini_responses(
    run_id: str,
    keys: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Return the stored gemini_responses for a run.

    - If `keys` is provided (comma-separated), returns only those top-level keys.
    """

    repo = RunRepository(db)
    run = repo.get_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    payload = run.gemini_responses or {}
    if not keys:
        return payload

    requested = [k.strip() for k in keys.split(",") if k.strip()]
    if not requested:
        return payload

    if not isinstance(payload, dict):
        return {}
    return {k: payload.get(k) for k in requested}


@router.get("/{run_id}/agent_steps", response_model=AgentStepsResponse)
async def get_run_agent_steps(
    run_id: str,
    keys: Optional[str] = None,
    include_prompt: bool = True,
    include_raw: bool = False,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Return a normalized, UI-friendly view of a run's gemini_responses.

    - `include_prompt`: include prompt blocks (system/user/full_text) when present.
    - `include_raw`: include raw/structured payloads in `response` (can be large).
    - `keys`: optional comma-separated list of top-level keys to include.
    """

    repo = RunRepository(db)
    run = repo.get_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    payload = run.gemini_responses or {}
    if not isinstance(payload, dict):
        payload = {}

    requested = None
    if keys:
        req = [k.strip() for k in keys.split(",") if k.strip()]
        if req:
            requested = set(req)

    # Prefer a sensible order, then append remaining keys.
    preferred_order = [
        "location_extraction",
        "property_technical_extraction",
        "needs_metric_plan",
        "use_case_generation",
        "sql_generation",
        "ape_analysis",
        "poi_analysis",
        "evaluation",
        "broker_review",
        "agent_context",
        "_demo",
    ]

    ordered_keys: list[str] = []
    for k in preferred_order:
        if k in payload:
            ordered_keys.append(k)

    for k in payload.keys():
        if k not in ordered_keys:
            ordered_keys.append(k)

    if requested is not None:
        ordered_keys = [k for k in ordered_keys if k in requested]

    steps = [
        _normalize_agent_step(
            k, payload.get(k), include_prompt=include_prompt, include_raw=include_raw
        )
        for k in ordered_keys
    ]

    return AgentStepsResponse(run_id=run_id, steps=steps)


@router.get("/demos")
async def list_demo_runs():
    """List available demo runs under runs/admin/* (best-effort)."""

    repo_root = _find_repo_root(Path(__file__).resolve())
    if not repo_root:
        return []

    admin_dir = repo_root / "runs" / "admin"
    if not admin_dir.exists() or not admin_dir.is_dir():
        return []

    demos: list[dict] = []
    for child in admin_dir.iterdir():
        if not child.is_dir():
            continue
        metadata_path = child / "metadata.json"
        if not metadata_path.exists():
            continue
        try:
            import json

            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

        demos.append(
            {
                "demo_id": child.name,
                "query": meta.get("query"),
                "timestamp": meta.get("timestamp"),
                "results_count": meta.get("results_count"),
                "location_data": meta.get("location_data"),
            }
        )

    demos.sort(key=lambda d: d.get("timestamp") or "", reverse=True)
    return demos


@router.post("/demos/{demo_id}", response_model=AnalysisResponse)
async def start_demo_run(
    demo_id: str,
    limit: int = 50,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a demo analysis run with simulated progress updates.

    The demo artifacts are loaded from runs/admin/<demo_id> but progress
    updates are streamed over ~15 seconds to simulate a real analysis.
    """
    import asyncio
    from app.services.progress_manager import progress_manager
    from app.models.responses import ProgressUpdate, StepState

    run_id = generate_run_id()

    # Persist as a normal run; demo results are loaded immediately.
    RunRepository(db).create_run(
        run_id=run_id,
        query=f"[DEMO:{demo_id}]",
        user_id=current_user.id if current_user else None,
        dataset_key="full",
        analysis_mode="demo",
    )

    try:
        raw_results = _load_demo_artifacts(demo_id=demo_id, limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load demo artifacts: {e}"
        )

    # Normalize results for later storage
    results_model = AnalysisResults.model_validate(
        {
            **raw_results,
            "run_id": run_id,
        }
    )
    results_json = results_model.model_dump(mode="json")

    # Persist results immediately so the demo endpoint is synchronous and reliable.
    RunRepository(db).save_complete_results(
        run_id=run_id,
        results=results_json,
        gemini_responses=results_json.get("gemini_responses") or {},
        location_data=results_json.get("location"),
        status_message=results_json.get("broker_summary") or "Demo loaded",
        results_count=len(results_json.get("buildings") or []),
    )

    # Define simulated steps for demo progress
    demo_steps = [
        ("Location extraction", 10),
        ("Technical features", 20),
        ("Metrics and strategy", 35),
        ("SQL generation", 50),
        ("Energy analysis", 65),
        ("POI analysis", 75),
        ("Evaluation", 85),
        ("Broker review", 95),
        ("Result finalization", 100),
    ]

    async def simulate_demo_progress():
        """Simulate progress updates (UI-only). Does not affect persisted results."""
        try:
            for i, (step_label, percent) in enumerate(demo_steps):
                steps_state = []
                for j, (s_label, _s_pct) in enumerate(demo_steps):
                    if j < i:
                        steps_state.append(
                            {"label": s_label, "state": "done", "detail": ""}
                        )
                    elif j == i:
                        steps_state.append(
                            {
                                "label": s_label,
                                "state": "current",
                                "detail": f"Processing {s_label}...",
                            }
                        )
                    else:
                        steps_state.append(
                            {"label": s_label, "state": "pending", "detail": ""}
                        )

                update = ProgressUpdate(
                    type="progress",
                    progress=percent,
                    step=step_label,
                    detail=f"Processing {step_label}...",
                    steps_state=[StepState(**s) for s in steps_state],
                )
                await progress_manager.publish(run_id, update)

                # Total ~15 seconds.
                await asyncio.sleep(1.5 + (0.5 if percent < 50 else 0))

            await progress_manager.complete(run_id)
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Demo progress simulation error: {e}")
            await progress_manager.complete(run_id)

    # Fire-and-forget progress simulation (BackgroundTasks does not run async callables).
    try:
        asyncio.create_task(simulate_demo_progress())
    except RuntimeError:
        # No running loop (edge-case); skip progress simulation.
        pass

    return AnalysisResponse(
        run_id=run_id,
        status="completed",
        message=f"Demo run '{demo_id}' loaded (limit={limit})",
        created_at=datetime.utcnow(),
    )


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Start a new real estate analysis.

    This endpoint initiates an asynchronous analysis process that:
    1. Parses the natural language query
    2. Extracts location, typology, and requirements
    3. Generates SQL query
    4. Filters and ranks results
    5. Evaluates top candidates with LLM

    The analysis runs in the background. Use the WebSocket endpoint
    to receive real-time progress updates, or poll GET /analysis/{run_id}
    for the final results.

    Args:
        request: Analysis request parameters
        background_tasks: FastAPI background tasks manager

    Returns:
        AnalysisResponse with run_id and status
    """
    # Generate unique run ID
    run_id = generate_run_id()

    # Validate dataset_key
    valid_datasets = list(settings.dataset_options.keys())
    if request.dataset_key not in valid_datasets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid dataset_key. Must be one of: {valid_datasets}",
        )

    # Apply model configuration if specified
    if request.model_type:
        settings.set_llm_model(request.model_type)
        logger.info(f"Using model configuration: {request.model_type}")

    # Create run record (status=processing)
    RunRepository(db).create_run(
        run_id=run_id,
        query=request.query,
        user_id=current_user.id if current_user else None,
        dataset_key=request.dataset_key,
        analysis_mode=request.analysis_mode,
    )

    # Import analysis service
    from app.services.analysis_service import analysis_service

    # Start analysis in background
    async def run_analysis_task():
        """Background task that runs the analysis."""
        # Use the same engine as the request-scoped session (works with dependency overrides in tests)
        engine = db.get_bind()
        BackgroundSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=engine
        )

        # Persist a full agent trace for this run so every step is
        # inspectable afterwards from the frontend (/api/v1/logs/traces).
        from app.services.agent_logger import AgentLogger, set_active_evaluation_logger
        trace_logger = AgentLogger(log_dir=Path(settings.AGENT_LOGS_DIR))
        trace_logger.start_evaluation(
            use_case="app",
            prompt_id=run_id,
            run_number=1,
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
            user_query=request.query,
        )
        set_active_evaluation_logger(trace_logger)

        try:
            raw_results = await analysis_service.run_analysis(
                run_id=run_id,
                query=request.query,
                dataset_key=request.dataset_key,
                map_limit=request.map_limit,
                llm_limit=request.llm_limit,
                analysis_mode=request.analysis_mode,
                output_language=request.output_language,
                use_relaxation=request.use_relaxation,
                model_type=request.model_type,
            )

            # Defensive: ensure we don't persist unserializable scientific types.
            raw_results = make_json_safe(raw_results)

            # Validate/normalize results and persist
            results_model = AnalysisResults.model_validate(raw_results)
            results_json = results_model.model_dump(mode="json")

            with BackgroundSessionLocal() as bg_db:
                repo = RunRepository(bg_db)
                repo.save_complete_results(
                    run_id=run_id,
                    results=results_json,
                    gemini_responses=results_json.get("gemini_responses") or {},
                    location_data=results_json.get("location"),
                    status_message=results_json.get("broker_summary")
                    or "Analysis completed",
                    results_count=results_json.get("results_count") or 0,
                )
            
            # Now signal completion to WebSocket subscribers (data is ready in DB)
            from app.services.progress_manager import progress_manager
            await progress_manager.complete(run_id)
            trace_logger.end_evaluation(success=True)
        except Exception as e:
            logger.error(f"Analysis task failed for run {run_id}: {e}", exc_info=True)
            with BackgroundSessionLocal() as bg_db:
                repo = RunRepository(bg_db)
                repo.update_status(
                    run_id=run_id,
                    status="failed",
                    results=None,
                    status_message=f"Analysis failed: {str(e)}",
                )
            
            # Signal completion even on failure so the frontend knows to stop waiting
            try:
                from app.services.progress_manager import progress_manager
                await progress_manager.complete(run_id)
            except:
                pass
            trace_logger.end_evaluation(success=False, error_msg=str(e))
        finally:
            set_active_evaluation_logger(None)

    background_tasks.add_task(run_analysis_task)

    return AnalysisResponse(
        run_id=run_id,
        status="processing",
        message=f"Analysis started for query: '{request.query}'",
        created_at=datetime.utcnow(),
    )


@router.get("/history", response_model=list[AnalysisHistoryItem])
async def get_analysis_history(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get user's analysis history (lightweight summary).

    Returns a paginated list of past analyses for the current user,
    ordered by creation date (most recent first).
    """
    from app.models.responses import AnalysisHistoryItem

    repo = RunRepository(db)
    if current_user:
        runs = repo.get_user_runs(user_id=current_user.id, limit=limit + offset)
    else:
        # Without auth, return recent runs across users (dev-mode convenience)
        runs = repo.get_recent_runs(limit=limit + offset)

    # Apply offset in memory (repository doesn't support offset yet)
    paginated_runs = runs[offset : offset + limit]

    history_items: list[AnalysisHistoryItem] = []
    for run in paginated_runs:
        try:
            # Create history item directly from run columns, AVOIDING invalid JSON parsing
            # of the heavy 'results' or 'gemini_responses' columns.
            item = AnalysisHistoryItem(
                run_id=run.run_id,
                query=run.query,
                status=run.status,
                created_at=run.created_at,
                completed_at=run.completed_at,
                # Use the explicitly stored count if available, otherwise 0
                buildings_count=run.results_count or 0,
                analysis_mode=run.analysis_mode or "agent",
            )
            history_items.append(item)
        except Exception as e:
            logger.error(f"Error mapping run {run.run_id} to history item: {e}")
            continue

    return history_items




@router.get("/{run_id}", response_model=AnalysisResults)
async def get_analysis(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get analysis results by run ID.

    Returns the complete results of an analysis, including:
    - List of matching buildings
    - Location information
    - Applied filters
    - LLM responses
    - Broker summary

    Args:
        run_id: Unique analysis run identifier

    Returns:
        AnalysisResults with complete data

    Raises:
        404: If run_id not found
        403: If run belongs to different user
    """
    repo = RunRepository(db)
    run = repo.get_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # If user is authenticated, enforce ownership when available
    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # If results are available, return them
    if run.results:
        try:
            results = AnalysisResults.model_validate(run.results)

            # Enrich buildings with missing fields from dataset
            # This handles legacy runs stored before certain fields were implemented
            from app.services.real_estate_service import RealEstateService
            from app.models.responses import SubProperty, EnergyScores, ProximityScores
            from app.data.loaders import load_and_merge_data

            real_estate_svc = RealEstateService()

            # Load dataset if not cached (needed for field lookups)
            df = RealEstateService._dataset_cache.get("full")
            indexed_cache = RealEstateService._dataset_indexed_cache.get("full")

            if df is None:
                try:
                    dataset_path = settings.dataset_options.get("full")
                    if dataset_path:
                        logger.info(
                            f"Loading dataset for enrichment from {dataset_path}"
                        )
                        df = load_and_merge_data(dataset_path)
                        RealEstateService._dataset_cache["full"] = df
                        logger.info(f"Loaded {len(df)} rows for enrichment")
                except Exception as load_err:
                    logger.warning(f"Could not load dataset for enrichment: {load_err}")

            # Build indexed cache if not present (same format as _load_dataset)
            if df is not None and indexed_cache is None:
                try:
                    logger.info("Building indexed cache for enrichment...")
                    if "id" in df.columns:
                        df_indexed = df.copy()
                        df_indexed["id_str"] = df_indexed["id"].astype(str)
                        df_indexed = df_indexed.drop_duplicates(subset=["id_str"])
                        df_indexed.set_index("id_str", inplace=True)
                        indexed_cache = df_indexed
                        RealEstateService._dataset_indexed_cache["full"] = indexed_cache
                        logger.info(
                            f"Built indexed cache with {len(indexed_cache)} entries"
                        )
                except Exception as idx_err:
                    logger.warning(f"Could not build indexed cache: {idx_err}")

            for building in results.buildings:
                # Try to enrich from indexed cache (DataFrame with id as index)
                building_id_str = str(building.id)
                if indexed_cache is not None and building_id_str in indexed_cache.index:
                    try:
                        row = indexed_cache.loc[building_id_str]
                        if isinstance(row, pd.DataFrame):
                            row = row.iloc[0]

                        # Enrich surface_area if missing
                        if building.surface_area is None:
                            val = row.get("surface_area")
                            if pd.notna(val):
                                building.surface_area = float(val)

                        # Enrich property_type if missing
                        if building.property_type is None:
                            val = row.get("property_type")
                            if pd.notna(val):
                                building.property_type = str(val)

                        # Enrich construction_year if missing
                        if building.construction_year is None:
                            val = row.get("construction_period")
                            if pd.notna(val):
                                building.construction_year = str(val)

                        # Enrich energy_class if missing
                        if building.energy_class is None:
                            val = row.get("energy_class")
                            if pd.notna(val):
                                building.energy_class = str(val)

                        # Enrich energy_scores if missing or if total is 0 but sub-scores exist
                        need_energy_enrich = (
                            building.energy_scores is None or
                            (building.energy_scores.total == 0.0 and
                             any([
                                 building.energy_scores.class_score,
                                 building.energy_scores.system_score,
                                 building.energy_scores.envelope_score,
                                 building.energy_scores.renewables_score,
                             ]))
                        )
                        if need_energy_enrich:
                            # Try multiple column name variants (dataset uses ape_score_* names)
                            def _get_energy_val(row, *keys):
                                for k in keys:
                                    v = row.get(k)
                                    if v is not None and pd.notna(v):
                                        return v
                                return None

                            energy_total = _get_energy_val(
                                row, "ape_score_total", "energy_score_total", "energy_total_points"
                            )
                            cls_score = _get_energy_val(row, "ape_score_classe", "energy_score_class")
                            plant_score = _get_energy_val(row, "ape_score_impianto", "energy_score_plant")
                            env_score = _get_energy_val(row, "ape_score_involucro", "energy_score_envelope")
                            ren_score = _get_energy_val(row, "ape_score_rinnovabili", "energy_score_renewables")

                            if cls_score is not None and plant_score is not None and env_score is not None and ren_score is not None:
                                computed_total = float(cls_score) + float(plant_score) + float(env_score) + float(ren_score)
                                building.energy_scores = EnergyScores(
                                    total=float(energy_total) if energy_total is not None else computed_total,
                                    class_score=int(float(cls_score)),
                                    system_score=int(float(plant_score)),
                                    envelope_score=int(float(env_score)),
                                    renewables_score=int(float(ren_score)),
                                )

                        # Enrich proximity_scores if missing
                        if building.proximity_scores is None:
                            # Use Italian column names from dataset
                            proximity_fields = {
                                "healthcare": ["healthcare", "sanita"],
                                "mobility": ["mobility", "mobilita"],
                                "greenery": ["greenery", "verde"],
                                "education": ["education", "educazione"],
                                "commerce": ["commerce", "commerciale"],
                                "sport": ["sport"],
                            }
                            proximity_values = {}
                            has_any = False
                            for prox_key, col_variants in proximity_fields.items():
                                val = None
                                for col in col_variants:
                                    v = row.get(col)
                                    if v is not None and pd.notna(v):
                                        val = float(v)
                                        break
                                if val is not None:
                                    proximity_values[prox_key] = val
                                    has_any = True
                                else:
                                    proximity_values[prox_key] = None

                            if has_any:
                                building.proximity_scores = ProximityScores(**proximity_values)

                        # Enrich energy_files if missing
                        if not building.energy_files:
                            energy_files_raw = None
                            for col in ["energy_files", "lista_file_ape", "list_file_ape_filtered", "list_file_ape_filtered_parsed"]:
                                v = row.get(col)
                                if v is not None and pd.notna(v) and v:
                                    energy_files_raw = v
                                    break
                            if energy_files_raw:
                                try:
                                    if isinstance(energy_files_raw, list):
                                        building.energy_files = [str(f) for f in energy_files_raw if f]
                                    else:
                                        building.energy_files = ast.literal_eval(str(energy_files_raw))
                                except Exception:
                                    pass
                    except Exception as enrich_err:
                        logger.warning(
                            f"Error enriching building {building.id}: {enrich_err}"
                        )

                # Dynamically calculate sub-scores and final score if missing or 0
                # Proximity Score
                p_score = building.proximity_score
                if p_score is None or pd.isna(p_score) or p_score == 0.0:
                    if building.proximity_scores:
                        vals = [
                            getattr(building.proximity_scores, attr)
                            for attr in ["healthcare", "mobility", "greenery", "education", "commerce", "sport"]
                            if getattr(building.proximity_scores, attr) is not None
                        ]
                        if vals:
                            p_score = sum(vals) / len(vals)
                    if p_score is None or pd.isna(p_score) or p_score == 0.0:
                        p_score = 70.0
                building.proximity_score = float(p_score)

                # Energy Score
                e_score = building.energy_score
                if e_score is None or pd.isna(e_score) or e_score == 0.0:
                    if building.energy_scores and building.energy_scores.total is not None:
                        e_score = (building.energy_scores.total / 20.0) * 100.0
                    if e_score is None or pd.isna(e_score) or e_score == 0.0:
                        e_score = 60.0
                building.energy_score = float(e_score)

                # Location Score
                l_score = building.location_score
                if l_score is None or pd.isna(l_score) or l_score == 0.0:
                    if building.distance_km is not None:
                        l_score = max(0.0, 1.0 - (float(building.distance_km) / 6.0)) * 100.0
                    if l_score is None or pd.isna(l_score) or l_score == 0.0:
                        l_score = 80.0
                building.location_score = float(l_score)

                if building.regulatory_score is None or pd.isna(building.regulatory_score):
                    building.regulatory_score = 0.0
                if building.building_score is None or pd.isna(building.building_score):
                    building.building_score = 0.0

                # Recalculate main score if missing or zero
                if building.score is None or building.score == 0.0 or pd.isna(building.score):
                    building.score = round(
                        building.proximity_score * 0.5 +
                        building.location_score * 0.3 +
                        building.energy_score * 0.2
                    )

                # Enrich meta properties with sub_properties if missing
                if (
                    building.meta_building
                    and building.id_list
                    and not building.sub_properties
                ):
                    try:
                        # Parse id_list
                        id_list_raw = building.id_list
                        if isinstance(id_list_raw, str):
                            id_list_parsed = ast.literal_eval(id_list_raw)
                        elif isinstance(id_list_raw, list):
                            id_list_parsed = id_list_raw
                        else:
                            continue

                        if id_list_parsed and len(id_list_parsed) > 0:
                            sub_properties = []
                            logger.debug(
                                f"Enriching sub_properties for meta {building.id}: {id_list_parsed[:5]}..."
                            )

                            for sub_id in id_list_parsed[:20]:  # Limit to 20
                                sub_id_str = str(sub_id)
                                sub_prop = SubProperty(id=sub_id_str)

                                # Use indexed cache for O(1) lookup (cache is DataFrame with id as index)
                                if (
                                    indexed_cache is not None
                                    and sub_id_str in indexed_cache.index
                                ):
                                    try:
                                        sub_row = indexed_cache.loc[sub_id_str]
                                        if isinstance(sub_row, pd.DataFrame):
                                            sub_row = sub_row.iloc[0]
                                        # Extract surface_area
                                        if (
                                            "surface_area"
                                            in sub_row.index
                                        ):
                                            val = sub_row.get(
                                                "surface_area"
                                            )
                                            if pd.notna(val):
                                                sub_prop.surface_area = float(val)
                                        # Extract property_type
                                        if "property_type" in sub_row.index:
                                            val = sub_row.get("property_type")
                                            if pd.notna(val):
                                                sub_prop.property_type = str(val)
                                        # Extract energy_class
                                        if "energy_class" in sub_row.index:
                                            val = sub_row.get("energy_class")
                                            if pd.notna(val):
                                                sub_prop.energy_class = str(val)
                                    except Exception as sub_err:
                                        logger.debug(
                                            f"Error getting sub-property {sub_id_str}: {sub_err}"
                                        )
                                elif indexed_cache is None:
                                    logger.debug(
                                        "No indexed cache available for sub_properties lookup"
                                    )

                                sub_properties.append(sub_prop)

                            building.sub_properties = sub_properties
                            logger.debug(
                                f"Enriched {len(sub_properties)} sub_properties for {building.id}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Error enriching sub_properties for building {building.id}: {e}"
                        )

            return results
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Stored results are invalid: {e}"
            )

    # Otherwise return current run status (still processing/failed)
    return AnalysisResults(
        run_id=run.run_id,
        query=run.query,
        status=run.status,
        buildings=[],
        location=run.location_data,
        filters_applied=None,
        gemini_responses=run.gemini_responses,
        broker_summary=run.status_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Delete an analysis run.

    Removes the analysis and all associated data from the database.

    Args:
        run_id: Unique analysis run identifier

    Raises:
        404: If run_id not found
        403: If run belongs to different user
    """
    repo = RunRepository(db)
    run = repo.get_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    repo.delete(run.id)
    return None
