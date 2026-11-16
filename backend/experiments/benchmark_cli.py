"""Run MURENA analyses from a scenario file without starting the web UI/API."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import hashlib
import os
import platform
import sys
import time
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def quiet_known_warnings() -> None:
    """Hide recurring dependency/deprecation warnings during CLI benchmark runs."""
    warnings.filterwarnings(
        "ignore",
        message=r"The default value of `allowed_objects` will change.*",
        category=Warning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"DataFrame columns are not unique.*",
        category=UserWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"datetime\.datetime\.utcnow\(\) is deprecated.*",
        category=DeprecationWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"The copy keyword is deprecated.*|'future\.no_silent_downcasting' is deprecated.*|The default 'epoch' date format is deprecated.*",
        category=Warning,
    )


def initialize_analysis_agent(analysis_service: Any) -> Any:
    """Import LangGraph quietly, then replay any warning outside our known noisy set."""
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        agent = analysis_service._init_graph_agent(force=True)

    quiet_known_warnings()
    for item in captured:
        message = str(item.message)
        known_noise = (
            message.startswith("The default value of `allowed_objects` will change")
            or message.startswith("DataFrame columns are not unique")
            or "datetime.datetime.utcnow() is deprecated" in message
            or "The copy keyword is deprecated" in message
            or "'future.no_silent_downcasting' is deprecated" in message
            or "The default 'epoch' date format is deprecated" in message
        )
        if not known_noise:
            warnings.showwarning(item.message, item.category, item.filename, item.lineno)
    return agent


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    try:
        source = path.read_text(encoding="utf-8")
        if path.suffix.lower() in {".yaml", ".yml"}:
            import yaml

            raw = yaml.safe_load(source)
        elif path.suffix.lower() == ".json":
            raw = json.loads(source)
        else:
            raise ValueError("Scenario files must use .json, .yaml, or .yml.")
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read scenario file {path}: {exc}") from exc
    except Exception as exc:
        if path.suffix.lower() in {".yaml", ".yml"}:
            raise ValueError(f"Cannot parse YAML scenario file {path}: {exc}") from exc
        raise
    if not isinstance(raw, list) or not raw:
        raise ValueError("Scenario file must contain a non-empty JSON array.")

    seen: set[str] = set()
    for index, scenario in enumerate(raw, start=1):
        if not isinstance(scenario, dict):
            raise ValueError(f"Scenario #{index} must be a JSON object.")
        scenario_id = scenario.get("id")
        initial_query = scenario.get("initial_query")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ValueError(f"Scenario #{index} needs a non-empty string 'id'.")
        if scenario_id in seen:
            raise ValueError(f"Duplicate scenario id: {scenario_id}")
        if not isinstance(initial_query, str) or not initial_query.strip():
            raise ValueError(f"Scenario '{scenario_id}' needs a non-empty string 'initial_query'.")
        expected_initial_missing = scenario.get("expected_initial_missing")
        dimensions = {"I", "D", "L", "Cb", "Ce", "Cp"}
        if (
            not isinstance(expected_initial_missing, list)
            or not expected_initial_missing
            or not all(isinstance(item, str) and item in dimensions for item in expected_initial_missing)
            or len(set(expected_initial_missing)) != len(expected_initial_missing)
        ):
            raise ValueError(f"Scenario '{scenario_id}' needs a non-empty, unique 'expected_initial_missing' dimension list.")
        clarifications = scenario.get("clarifications")
        if not isinstance(clarifications, dict) or not clarifications:
            raise ValueError(f"Scenario '{scenario_id}' needs non-empty 'clarifications' keyed by dimension.")
        unknown_dimensions = set(clarifications) - dimensions
        if unknown_dimensions:
            raise ValueError(f"Scenario '{scenario_id}' has unknown clarification dimensions: {', '.join(sorted(unknown_dimensions))}")
        if not all(isinstance(answer, str) and answer.strip() for answer in clarifications.values()):
            raise ValueError(f"Scenario '{scenario_id}' clarification answers must be non-empty strings.")
        unanswered_expected = set(expected_initial_missing) - set(clarifications)
        if unanswered_expected:
            raise ValueError(
                f"Scenario '{scenario_id}' is missing simulated answers for: "
                + ", ".join(sorted(unanswered_expected))
            )
        expected_mapping = scenario.get("expected_mapping", {})
        if not isinstance(expected_mapping, dict) or not expected_mapping or set(expected_mapping) - dimensions:
            raise ValueError(f"Scenario '{scenario_id}' has invalid 'expected_mapping' dimension keys.")
        if set(expected_initial_missing) - set(expected_mapping):
            raise ValueError(f"Scenario '{scenario_id}' expected_mapping must include every initially missing dimension.")
        allowed_statuses = {"SPECIFIED", "NOT_REQUESTED", "UNCONFIRMED_ABSENT", "AMBIGUOUS", "MISSING_CRITICAL"}
        if any(not isinstance(status, str) or status not in allowed_statuses for status in expected_mapping.values()):
            raise ValueError(f"Scenario '{scenario_id}' has invalid expected mapping status.")
        if "reviewed_query" in scenario and (
            not isinstance(scenario["reviewed_query"], str) or not scenario["reviewed_query"].strip()
        ):
            raise ValueError(f"Scenario '{scenario_id}' 'reviewed_query' must be a non-empty string when provided.")
        seen.add(scenario_id)
        repeats = scenario.get("repeats", 1)
        if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats < 1:
            raise ValueError(f"Scenario '{scenario_id}' has invalid 'repeats' (expected integer >= 1).")
        expected_ids = scenario.get("expected_ids", [])
        if not isinstance(expected_ids, list) or not all(isinstance(item, (str, int)) for item in expected_ids):
            raise ValueError(f"Scenario '{scenario_id}' has invalid 'expected_ids'.")
        options = scenario.get("options", {})
        if not isinstance(options, dict):
            raise ValueError(f"Scenario '{scenario_id}' 'options' must be an object.")
        allowed_options = {
            "dataset_key", "map_limit", "llm_limit", "analysis_mode",
            "use_relaxation", "use_data_knowledge", "architecture", "disabled_agents",
        }
        unknown = set(options) - allowed_options
        if unknown:
            raise ValueError(f"Scenario '{scenario_id}' has unknown options: {', '.join(sorted(unknown))}")
    return raw


def scenario_digest(scenario: dict[str, Any]) -> str:
    """Hash one normalized scenario definition independently of file ordering/formatting."""
    canonical = json.dumps(scenario, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def result_metrics(buildings: list[dict[str, Any]], expected_ids: list[str | int]) -> dict[str, Any]:
    returned = [str(item.get("id")) for item in buildings]
    expected = {str(item) for item in expected_ids}
    if not expected:
        return {"expected_count": 0, "matched_expected": None, "precision_at_returned": None, "recall": None}
    matched = expected.intersection(returned)
    return {
        "expected_count": len(expected),
        "matched_expected": len(matched),
        "precision_at_returned": round(len(matched) / len(returned), 4) if returned else 0.0,
        "recall": round(len(matched) / len(expected), 4),
    }


def simulate_conversation(scenario: dict[str, Any]) -> dict[str, Any]:
    """Drive the same SAGE clarification service used by the frontend, in an isolated DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.database.models import Base, ClarificationSession
    from app.services.sage_clarification import SageClarifier

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    messages: list[dict[str, str]] = [{"role": "user", "content": scenario["initial_query"]}]
    turns: list[dict[str, Any]] = []
    clarifier = SageClarifier()
    language = "en"

    def snapshot(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            dimension: {
                "status": data.get("status"),
                "value": data.get("value"),
                "evidence": data.get("evidence"),
            }
            for dimension, data in (state.get("dimensions") or {}).items()
        }

    try:
        with Session(engine) as db:
            response = clarifier.process(
                db=db,
                user_input=scenario["initial_query"],
                language=language,
            )
            session_id = response.session_id
            row = db.get(ClarificationSession, session_id)
            initial_dimension_state = snapshot(row.state if row is not None else {})
            initial_missing = sorted(
                dimension
                for dimension, data in initial_dimension_state.items()
                if data["status"] in {"UNCONFIRMED_ABSENT", "AMBIGUOUS", "MISSING_CRITICAL"}
            )
            expected_missing = set(scenario["expected_initial_missing"])
            predicted_missing = set(initial_missing)
            overlap = expected_missing & predicted_missing
            precision = len(overlap) / len(predicted_missing) if predicted_missing else 0.0
            recall = len(overlap) / len(expected_missing) if expected_missing else 0.0
            missing_f1 = round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0

            while response.status == "ASK":
                row = db.get(ClarificationSession, session_id)
                state = row.state if row is not None else {}
                pending = clarifier._select_question(state)
                targets = pending.get("target_dimensions", []) if pending else []
                question = response.question or (pending or {}).get("question", "")
                messages.append({"role": "assistant", "content": question})
                missing_answers = [dimension for dimension in targets if dimension not in scenario["clarifications"]]
                if missing_answers:
                    return {
                        "status": "INCOMPLETE",
                        "session_id": session_id,
                        "initial_dimension_state": initial_dimension_state,
                        "initial_missing": initial_missing,
                        "expected_initial_missing": sorted(expected_missing),
                        "missing_detection": {"precision": round(precision, 4), "recall": round(recall, 4), "f1": missing_f1},
                        "turns": turns,
                        "messages": messages,
                        "error": "No simulated user answer configured for dimension(s): " + ", ".join(missing_answers),
                    }

                answer = " ".join(scenario["clarifications"][dimension] for dimension in targets)
                messages.append({"role": "user", "content": answer})
                turns.append({
                    "question": question,
                    "target_dimensions": targets,
                    "answer": answer,
                    "question_source": (pending or {}).get("question_source", "llm_query_parser"),
                })
                response = clarifier.process(
                    db=db,
                    user_input=scenario["initial_query"],
                    session_id=session_id,
                    clarification_response=answer,
                    language=language,
                )
                row = db.get(ClarificationSession, session_id)
                turns[-1].update({
                    "status_after": response.status,
                    "turn_after": response.turn,
                    "dimension_state_after": snapshot(row.state if row is not None else {}),
                })
                if response.status == "BLOCKED" and response.message:
                    messages.append({"role": "assistant", "content": response.message})

            row = db.get(ClarificationSession, session_id)
            state = row.state if row is not None else {}
            dimension_state = snapshot(state)
            mapping = {
                dimension: data["status"]
                for dimension, data in dimension_state.items()
            }
            expected = scenario.get("expected_mapping", {})
            mapping_accuracy = (
                round(sum(mapping.get(key) == value for key, value in expected.items()) / len(expected), 4)
                if expected else None
            )
            if response.status == "READY":
                if not turns:
                    return {
                        "status": "INCOMPLETE",
                        "session_id": session_id,
                        "initial_dimension_state": initial_dimension_state,
                        "initial_missing": initial_missing,
                        "expected_initial_missing": sorted(expected_missing),
                        "missing_detection": {"precision": round(precision, 4), "recall": round(recall, 4), "f1": missing_f1},
                        "turns": turns,
                        "messages": messages,
                        "error": "The initial query triggered no clarification turn; add an intentional omission.",
                    }
                reviewed_query = scenario.get("reviewed_query") or response.refined_query
                messages.append({
                    "role": "assistant",
                    "content": "Query submitted for review: " + (response.refined_query or ""),
                })
                messages.append({
                    "role": "user",
                    "content": "Confirmed." if reviewed_query == response.refined_query else reviewed_query,
                })
                return {
                    "status": "READY",
                    "session_id": session_id,
                    "turns": turns,
                    "messages": messages,
                    "initial_dimension_state": initial_dimension_state,
                    "initial_missing": initial_missing,
                    "expected_initial_missing": sorted(expected_missing),
                    "missing_detection": {"precision": round(precision, 4), "recall": round(recall, 4), "f1": missing_f1},
                    "dimension_state": dimension_state,
                    "mapping": mapping,
                    "expected_mapping": expected,
                    "mapping_accuracy": mapping_accuracy,
                    "refined_query": response.refined_query,
                    "reviewed_query": reviewed_query,
                }
            if response.status == "BLOCKED" and response.message and messages[-1]["content"] != response.message:
                messages.append({"role": "assistant", "content": response.message})
            return {
                "status": response.status,
                "session_id": session_id,
                "turns": turns,
                "messages": messages,
                "initial_dimension_state": initial_dimension_state,
                "initial_missing": initial_missing,
                "expected_initial_missing": sorted(expected_missing),
                "missing_detection": {"precision": round(precision, 4), "recall": round(recall, 4), "f1": missing_f1},
                "dimension_state": dimension_state,
                "mapping": mapping,
                "expected_mapping": expected,
                "mapping_accuracy": mapping_accuracy,
                "error": response.message or f"Clarification ended with status {response.status}.",
            }
    finally:
        engine.dispose()


async def run(args: argparse.Namespace) -> int:
    env_file = BACKEND / ".env"
    if not env_file.exists():
        raise ValueError(f"Missing {env_file}. Create it from backend/.env.example and configure the dataset and LLM provider.")

    # Keep benchmark traces in the run artifact instead of creating UI history files.
    os.environ["_AGENT_LOGGER_ACTIVE"] = "true"
    quiet_known_warnings()
    from app.core.config import settings
    from app.services.analysis_service import analysis_service
    from app.utils.json_sanitizer import make_json_safe
    # Imports may install their own default warning filters; reapply our CLI-specific filters.
    quiet_known_warnings()

    # Backend paths are defined relative to backend/, while this command runs from the repository root.
    for attribute in (
        "DATASET_FULL", "APE_DETAILED_DATA_PATH", "STATIC_DIR", "DATA_DIR", "APE_DIR",
        "META_DIR", "AGENT_LOGS_DIR",
    ):
        value = getattr(settings, attribute, None)
        if isinstance(value, str) and value and not Path(value).is_absolute():
            setattr(settings, attribute, str((BACKEND / value).resolve()))

    scenarios = load_scenarios(args.scenarios.resolve())
    scenario_ids = {scenario["id"] for scenario in scenarios}
    unknown_rerun_scenarios = set(args.rerun_scenario) - scenario_ids
    if unknown_rerun_scenarios:
        raise ValueError(
            "Cannot rerun unknown scenario(s): " + ", ".join(sorted(unknown_rerun_scenarios))
        )
    scenarios_sha256 = hashlib.sha256(args.scenarios.read_bytes()).hexdigest()
    scenario_hashes = {scenario["id"]: scenario_digest(scenario) for scenario in scenarios}
    # The frontend omits model_type in its request, so the backend uses this same configured default.
    models = [settings.LLM_MODEL]
    dataset_path = settings.dataset_options.get(args.dataset)
    if not dataset_path:
        raise ValueError(f"Dataset '{args.dataset}' is not configured by the backend.")
    if not Path(dataset_path).is_file():
        raise ValueError(
            f"Configured dataset is missing: {dataset_path}. "
            "For a local demo, generate it with: uv run python backend/data/metadata/create_demo_dataset.py"
        )
    output_dir = args.output.resolve()
    if output_dir.exists() and not args.resume:
        raise ValueError(f"Output directory already exists: {output_dir}. Choose another path or use --resume.")
    output_dir.mkdir(parents=True, exist_ok=args.resume)
    runs_path = output_dir / "runs.jsonl"
    run_artifacts_dir = output_dir / "runs"
    summary_path = output_dir / "summary.csv"
    manifest_path = output_dir / "manifest.json"

    completed: set[tuple[str, str, int]] = set()
    latest_status: dict[tuple[str, str, int], str] = {}
    latest_index_record: dict[tuple[str, str, int], dict[str, Any]] = {}
    attempt_counts: dict[tuple[str, str, int, str], int] = {}
    previous_manifest: dict[str, Any] | None = None
    if args.resume and manifest_path.exists():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.retry_failed and (not runs_path.exists() or not manifest_path.exists()):
        raise ValueError("Cannot retry failed runs: the output directory needs an existing manifest.json and runs.jsonl.")
    if args.resume and runs_path.exists():
        with runs_path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    key = (row["model"], row["scenario_id"], row["repeat"])
                    latest_status[key] = row.get("status", "")
                    latest_index_record[key] = row
                    row_scenario_hash = row.get("scenario_sha256")
                    if row_scenario_hash is None:
                        artifact_file = row.get("artifact_file")
                        legacy_record = None
                        if artifact_file:
                            artifact_path = output_dir / artifact_file
                            if artifact_path.is_file():
                                try:
                                    legacy_record = json.loads(artifact_path.read_text(encoding="utf-8"))
                                except json.JSONDecodeError:
                                    pass
                        if legacy_record is None and "scenario_definition" in row:
                            legacy_record = row
                        definition = (legacy_record or {}).get("scenario_definition")
                        row_scenario_hash = (
                            scenario_digest(definition) if isinstance(definition, dict)
                            else (previous_manifest or {}).get("scenarios_sha256", "legacy")
                        )
                    attempt_key = (*key, row_scenario_hash or "legacy")
                    attempt_counts[attempt_key] = attempt_counts.get(attempt_key, 0) + 1
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        for key, row in latest_index_record.items():
            if row.get("status") != "completed":
                continue
            artifact_file = row.get("artifact_file")
            if artifact_file and not (output_dir / artifact_file).is_file():
                continue
            completed.add(key)

    manifest = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scenario_file": str(args.scenarios.resolve()),
        "models": models,
        "clarification_mode": "SageClarifier",
        "review_policy": "auto_accept_refined_query_unless_scenario_overrides_it",
        "dataset_key_default": args.dataset,
        "repeat_default": args.repeat,
        "scenarios_sha256": scenarios_sha256,
        "scenario_hash_history": [scenarios_sha256],
        "resume_actions": [],
        "python": platform.python_version(),
        "run_artifacts_directory": "runs",
        "run_artifact_schema_version": 1,
        "options": {
            "map_limit": args.map_limit,
            "llm_limit": args.llm_limit,
            "concurrency": args.concurrency,
        },
    }
    if args.resume and manifest_path.exists():
        for field in ("models", "dataset_key_default", "repeat_default"):
            if previous_manifest.get(field) != manifest.get(field):
                raise ValueError(f"Cannot resume: benchmark setting '{field}' differs from the existing manifest.")
        scenario_hash_history = previous_manifest.get(
            "scenario_hash_history", [previous_manifest.get("scenarios_sha256")]
        )
        manifest["scenario_hash_history"] = list(dict.fromkeys(
            [value for value in scenario_hash_history if value] + [scenarios_sha256]
        ))
        previous_options = dict(previous_manifest.get("options", {}))
        # Language remains fixed internally to English but is no longer persisted as metadata.
        previous_options.pop("output_language", None)
        # Manifests produced before bounded concurrency represented sequential runs.
        previous_options.setdefault("concurrency", 1)
        if previous_options != manifest["options"]:
            raise ValueError("Cannot resume: benchmark setting 'options' differs from the existing manifest.")
        manifest["resume_actions"] = list(previous_manifest.get("resume_actions", []))
        if args.rerun_scenario:
            manifest["resume_actions"].append({
                "at": manifest["started_at"],
                "action": "rerun_scenarios",
                "scenario_ids": sorted(set(args.rerun_scenario)),
            })
        elif args.retry_failed:
            manifest["resume_actions"].append({
                "at": manifest["started_at"],
                "action": "retry_failed",
            })
        else:
            manifest["resume_actions"].append({
                "at": manifest["started_at"],
                "action": "resume_pending",
            })
    elif args.resume and runs_path.exists():
        raise ValueError("Cannot safely resume: runs.jsonl exists but manifest.json is missing.")
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    new_runs: list[dict[str, Any]] = []
    total = sum(max(args.repeat, scenario.get("repeats", 1)) for scenario in scenarios) * len(models)
    step = 0
    output_lock = asyncio.Lock()
    concurrency_limit = asyncio.Semaphore(args.concurrency)

    # Load the shared dataset and graph before scheduling workers. This avoids
    # concurrent cache initialization and keeps model selection fixed per batch.
    await asyncio.to_thread(analysis_service._get_or_load_dataset, args.dataset)

    async def execute_one(
        index: int,
        model: str,
        scenario: dict[str, Any],
        repeat_index: int,
        options: dict[str, Any],
        output: Any,
    ) -> dict[str, Any]:
        run_id = f"bench_{uuid.uuid4().hex[:12]}"
        started = time.perf_counter()
        record: dict[str, Any] = {
            "run_id": run_id,
            "scenario_id": scenario["id"],
            "scenario_name": scenario.get("name"),
            "tags": scenario.get("tags", []),
            "model": model,
            "repeat": repeat_index,
            "attempt": attempt_counts.get(
                (model, scenario["id"], repeat_index, scenario_hashes[scenario["id"]]), 0
            ) + 1,
            "scenario_sha256": scenario_hashes[scenario["id"]],
            "initial_query": scenario["initial_query"],
            "options": {key: value for key, value in options.items() if key != "output_language"},
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"[{index}/{total}] start {model} / {scenario['id']} / repeat {repeat_index}", flush=True)
        try:
            conversation = await asyncio.to_thread(
                simulate_conversation,
                scenario,
            )
            record["conversation"] = conversation
            if conversation["status"] != "READY":
                raise ValueError(conversation.get("error", "Clarification did not reach review."))

            record["submitted_query"] = conversation["reviewed_query"]
            result = await analysis_service.run_analysis(
                run_id=run_id, query=conversation["reviewed_query"], **options
            )
            api_response = make_json_safe(result)
            buildings = api_response.get("buildings", [])
            record.update({
                "status": "completed",
                "api_response": api_response,
                "results_count": api_response.get("results_count", len(buildings)),
                "top_ids": [str(item.get("id")) for item in buildings[:10]],
                "quality": result_metrics(buildings, scenario.get("expected_ids", [])),
                "final_sql": (api_response.get("filters_applied") or {}).get("final_sql"),
            })
        except Exception as exc:  # Preserve failed runs in the artifact and continue the batch.
            record.update({"status": "error", "error": str(exc)})

        record["duration_seconds"] = round(time.perf_counter() - started, 3)
        record["scenario_definition"] = scenario
        record["artifact_file"] = f"runs/{run_id}.json"
        async with output_lock:
            artifact_path = run_artifacts_dir / f"{run_id}.json"
            try:
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = artifact_path.with_suffix(".json.tmp")
                temporary_path.write_text(
                    json.dumps(make_json_safe(record), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                temporary_path.replace(artifact_path)
            except Exception as exc:
                record["status"] = "error"
                record["artifact_file"] = None
                record["error"] = f"Failed to save per-run JSON artifact: {exc}"

            index_record = {
                "run_id": run_id,
                "scenario_id": scenario["id"],
                "model": model,
                "repeat": repeat_index,
                "attempt": record["attempt"],
                "scenario_sha256": record["scenario_sha256"],
                "status": record["status"],
                "duration_seconds": record["duration_seconds"],
                "artifact_file": record.get("artifact_file"),
            }
            if record.get("error"):
                index_record["error"] = record["error"]
            output.write(json.dumps(index_record, ensure_ascii=False) + "\n")
            output.flush()
            new_runs.append(record)
            state = "OK" if record["status"] == "completed" else "ERR"
            print(f"[{index}/{total}] {state} {model} / {scenario['id']} / repeat {repeat_index} ({record['duration_seconds']} s)", flush=True)
            if record.get("error"):
                print(f"  {record['error']}", flush=True)
        return record

    async def bounded_execute(*job: Any) -> dict[str, Any]:
        async with concurrency_limit:
            return await execute_one(*job)

    with runs_path.open("a", encoding="utf-8") as output:
        for model in models:
            settings.set_llm_model(model)
            initialize_analysis_agent(analysis_service)
            jobs: list[tuple[int, str, dict[str, Any], int, dict[str, Any], Any]] = []
            for scenario in scenarios:
                repeats = max(args.repeat, scenario.get("repeats", 1))
                options = {
                    "dataset_key": args.dataset,
                    "map_limit": args.map_limit,
                    "llm_limit": args.llm_limit,
                    "analysis_mode": "agent",
                    "output_language": "en",
                    "use_relaxation": args.use_relaxation,
                    "use_data_knowledge": True,
                    "architecture": "multiagent",
                    "disabled_agents": None,
                    **scenario.get("options", {}),
                }
                for repeat_index in range(1, repeats + 1):
                    step += 1
                    key = (model, scenario["id"], repeat_index)
                    if args.rerun_scenario and scenario["id"] not in args.rerun_scenario:
                        print(f"[{step}/{total}] cached (outside selected scenarios) {model} / {scenario['id']} / repeat {repeat_index}")
                        continue
                    if args.retry_failed and latest_status.get(key) != "error":
                        print(f"[{step}/{total}] cached (not failed) {model} / {scenario['id']} / repeat {repeat_index}")
                        continue
                    if scenario["id"] not in args.rerun_scenario and not args.retry_failed and key in completed:
                        print(f"[{step}/{total}] cached {model} / {scenario['id']} / repeat {repeat_index}")
                        continue
                    jobs.append((step, model, scenario, repeat_index, options, output))
            await asyncio.gather(*(bounded_execute(*job) for job in jobs))

    all_runs: list[dict[str, Any]] = []
    if runs_path.exists():
        for line in runs_path.read_text(encoding="utf-8").splitlines():
            try:
                index_record = json.loads(line)
                artifact_file = index_record.get("artifact_file")
                if artifact_file:
                    artifact_path = output_dir / artifact_file
                    if artifact_path.is_file():
                        run_record = json.loads(artifact_path.read_text(encoding="utf-8"))
                        run_record.setdefault(
                            "scenario_sha256",
                            index_record.get("scenario_sha256")
                            or (
                                scenario_digest(run_record["scenario_definition"])
                                if isinstance(run_record.get("scenario_definition"), dict)
                                else (previous_manifest or {}).get("scenarios_sha256", "legacy")
                            ),
                        )
                        all_runs.append(run_record)
                else:
                    # Older runs stored the complete record directly in JSONL.
                    index_record.setdefault(
                        "scenario_sha256",
                        index_record.get("scenario_sha256")
                        or (
                            scenario_digest(index_record["scenario_definition"])
                            if isinstance(index_record.get("scenario_definition"), dict)
                            else (previous_manifest or {}).get("scenarios_sha256", "legacy")
                        ),
                    )
                    all_runs.append(index_record)
            except json.JSONDecodeError:
                continue
    latest_runs: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for row in all_runs:
        key = (
            row.get("model", ""), row.get("scenario_id", ""),
            row.get("repeat", 0), row.get("scenario_sha256", "legacy"),
        )
        latest_runs[key] = row
    all_runs = list(latest_runs.values())
    summary_rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in all_runs:
        groups.setdefault((
            row.get("model", ""), row.get("scenario_id", ""),
            row.get("scenario_sha256", "legacy"),
        ), []).append(row)
    for (model, scenario_id, scenario_hash), rows in groups.items():
        successes = [row for row in rows if row.get("status") == "completed"]
        durations = [row["duration_seconds"] for row in successes]
        recalls = [row["quality"]["recall"] for row in successes if row.get("quality", {}).get("recall") is not None]
        mapping_accuracies = [
            row["conversation"]["mapping_accuracy"]
            for row in successes
            if row.get("conversation", {}).get("mapping_accuracy") is not None
        ]
        missing_f1_values = [
            row["conversation"]["missing_detection"]["f1"]
            for row in successes
            if row.get("conversation", {}).get("missing_detection") is not None
        ]
        summary_rows.append({
            "model": model,
            "scenario_id": scenario_id,
            "scenario_sha256": scenario_hash,
            "runs": len(rows),
            "successes": len(successes),
            "errors": len(rows) - len(successes),
            "mean_duration_seconds": round(sum(durations) / len(durations), 3) if durations else "",
            "mean_results_count": round(sum(row.get("results_count", 0) for row in successes) / len(successes), 2) if successes else "",
            "mean_expected_recall": round(sum(recalls) / len(recalls), 4) if recalls else "",
            "mean_clarification_turns": round(sum(len(row.get("conversation", {}).get("turns", [])) for row in successes) / len(successes), 2) if successes else "",
            "mean_mapping_accuracy": round(sum(mapping_accuracies) / len(mapping_accuracies), 4) if mapping_accuracies else "",
            "mean_initial_missing_f1": round(sum(missing_f1_values) / len(missing_f1_values), 4) if missing_f1_values else "",
        })
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        fields = ["model", "scenario_id", "scenario_sha256", "runs", "successes", "errors", "mean_duration_seconds", "mean_results_count", "mean_expected_recall", "mean_clarification_turns", "mean_mapping_accuracy", "mean_initial_missing_f1"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["scenario_count"] = len(scenarios)
    manifest["result_runs"] = len(all_runs)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Benchmark artifacts: {output_dir}")
    return 1 if any(row.get("status") == "error" for row in new_runs) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run conversational MURENA benchmark scenarios directly against the analysis service.")
    parser.add_argument("--scenarios", type=Path, required=True, help="YAML or JSON file containing multi-turn benchmark scenarios.")
    parser.add_argument("--output", type=Path, default=ROOT / "backend/experiments/results/cli-benchmark", help="Directory for manifest, JSONL runs, and CSV summary.")
    parser.add_argument("--dataset", default="full", choices=["full"], help="Configured dataset key (currently only 'full' is available).")
    parser.add_argument("--repeat", type=int, default=1, help="Minimum repeat count per scenario (scenario 'repeats' can request more).")
    parser.add_argument("--concurrency", type=int, default=2, help="Maximum number of scenario runs in flight (default: 2). Use 1 for sequential execution.")
    parser.add_argument("--map-limit", type=int, default=1000)
    parser.add_argument("--llm-limit", type=int, default=10)
    parser.add_argument("--use-relaxation", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--resume", action="store_true", help="Append to existing output, skip tuples whose latest attempt completed, and continue pending or failed tuples. Scenario revisions are tracked by hash.")
    parser.add_argument("--retry-failed", action="store_true", help="With --resume, rerun only tuples whose latest recorded attempt failed; can use changed scenarios and keeps results separate by scenario hash.")
    parser.add_argument("--rerun-scenario", action="append", default=[], metavar="SCENARIO_ID", help="With --resume, run only every configured repeat of this scenario, even if earlier attempts completed. May be repeated.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.repeat < 1 or args.map_limit < 1 or args.llm_limit < 1 or args.concurrency < 1:
        parser.error("--repeat, --map-limit, --llm-limit and --concurrency must be positive integers.")
    if args.retry_failed and not args.resume:
        parser.error("--retry-failed requires --resume.")
    if args.rerun_scenario and not args.resume:
        parser.error("--rerun-scenario requires --resume.")
    if args.retry_failed and args.rerun_scenario:
        parser.error("--retry-failed and --rerun-scenario cannot be used together.")
    try:
        exit_code = asyncio.run(run(args))
    except ValueError as exc:
        parser.error(str(exc))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
