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
            "dataset_key", "map_limit", "llm_limit", "analysis_mode", "output_language",
            "use_relaxation", "use_data_knowledge", "architecture", "disabled_agents",
        }
        unknown = set(options) - allowed_options
        if unknown:
            raise ValueError(f"Scenario '{scenario_id}' has unknown options: {', '.join(sorted(unknown))}")
    return raw


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


def simulate_conversation(scenario: dict[str, Any], language: str) -> dict[str, Any]:
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
                    "content": "Query proposta per la revisione: " + (response.refined_query or ""),
                })
                messages.append({
                    "role": "user",
                    "content": "Confermo." if reviewed_query == response.refined_query else reviewed_query,
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
    summary_path = output_dir / "summary.csv"
    manifest_path = output_dir / "manifest.json"

    completed: set[tuple[str, str, int]] = set()
    if args.resume and runs_path.exists():
        with runs_path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    if row.get("status") == "completed":
                        completed.add((row["model"], row["scenario_id"], row["repeat"]))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

    manifest = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scenario_file": str(args.scenarios.resolve()),
        "models": models,
        "clarification_mode": "SageClarifier",
        "review_policy": "auto_accept_refined_query_unless_scenario_overrides_it",
        "dataset_key_default": args.dataset,
        "repeat_default": args.repeat,
        "scenarios_sha256": hashlib.sha256(args.scenarios.read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "options": {"map_limit": args.map_limit, "llm_limit": args.llm_limit, "output_language": args.language},
    }
    if args.resume and manifest_path.exists():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for field in ("scenarios_sha256", "models", "dataset_key_default", "repeat_default", "options"):
            if previous_manifest.get(field) != manifest.get(field):
                raise ValueError(f"Cannot resume: benchmark setting '{field}' differs from the existing manifest.")
    elif args.resume and runs_path.exists():
        raise ValueError("Cannot safely resume: runs.jsonl exists but manifest.json is missing.")
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    new_runs: list[dict[str, Any]] = []
    total = sum(max(args.repeat, scenario.get("repeats", 1)) for scenario in scenarios) * len(models)
    step = 0
    with runs_path.open("a", encoding="utf-8") as output:
        for model in models:
            settings.set_llm_model(model)
            initialize_analysis_agent(analysis_service)
            for scenario in scenarios:
                repeats = max(args.repeat, scenario.get("repeats", 1))
                options = {
                    "dataset_key": args.dataset,
                    "map_limit": args.map_limit,
                    "llm_limit": args.llm_limit,
                    "analysis_mode": "agent",
                    "output_language": args.language,
                    "use_relaxation": args.use_relaxation,
                    "use_data_knowledge": True,
                    "architecture": "multiagent",
                    "disabled_agents": None,
                    **scenario.get("options", {}),
                }
                for repeat_index in range(1, repeats + 1):
                    key = (model, scenario["id"], repeat_index)
                    step += 1
                    if key in completed:
                        print(f"[{step}/{total}] cached {model} / {scenario['id']} / repeat {repeat_index}")
                        continue
                    run_id = f"bench_{uuid.uuid4().hex[:12]}"
                    started = time.perf_counter()
                    record: dict[str, Any] = {
                        "run_id": run_id,
                        "scenario_id": scenario["id"],
                        "scenario_name": scenario.get("name"),
                        "tags": scenario.get("tags", []),
                        "model": model,
                        "repeat": repeat_index,
                        "initial_query": scenario["initial_query"],
                        "options": options,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    }
                    print(f"[{step}/{total}] {model} / {scenario['id']} / repeat {repeat_index}", flush=True)
                    try:
                        conversation = await asyncio.to_thread(
                            simulate_conversation,
                            scenario,
                            options["output_language"],
                        )
                        record["conversation"] = conversation
                        if conversation["status"] != "READY":
                            raise ValueError(conversation.get("error", "Clarification did not reach review."))

                        record["submitted_query"] = conversation["reviewed_query"]
                        result = await analysis_service.run_analysis(
                            run_id=run_id, query=conversation["reviewed_query"], **options
                        )
                        elapsed = round(time.perf_counter() - started, 3)
                        buildings = [
                            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                            for item in result.get("buildings", [])
                        ]
                        record.update({
                            "status": "completed",
                            "duration_seconds": elapsed,
                            "results_count": result.get("results_count", len(buildings)),
                            "top_ids": [str(item.get("id")) for item in buildings[:10]],
                            "quality": result_metrics(buildings, scenario.get("expected_ids", [])),
                            "final_sql": (result.get("filters_applied") or {}).get("final_sql"),
                            "broker_summary": result.get("broker_summary"),
                            "agent_trace": result.get("agent_trace"),
                        })
                    except Exception as exc:  # Keep batch progress and preserve failed cases in the artifact.
                        record.update({"status": "error", "duration_seconds": round(time.perf_counter() - started, 3), "error": str(exc)})
                    output.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    output.flush()
                    new_runs.append(record)
                    state = "OK" if record["status"] == "completed" else "ERR"
                    print(f"  {state} ({record['duration_seconds']} s)", flush=True)
                    if record.get("error"):
                        print(f"  {record['error']}", flush=True)

    all_runs: list[dict[str, Any]] = []
    if runs_path.exists():
        for line in runs_path.read_text(encoding="utf-8").splitlines():
            try:
                all_runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    summary_rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in all_runs:
        groups.setdefault((row.get("model", ""), row.get("scenario_id", "")), []).append(row)
    for (model, scenario_id), rows in groups.items():
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
        fields = ["model", "scenario_id", "runs", "successes", "errors", "mean_duration_seconds", "mean_results_count", "mean_expected_recall", "mean_clarification_turns", "mean_mapping_accuracy", "mean_initial_missing_f1"]
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
    parser.add_argument("--map-limit", type=int, default=1000)
    parser.add_argument("--llm-limit", type=int, default=10)
    parser.add_argument("--language", choices=["en", "it"], default="it")
    parser.add_argument("--use-relaxation", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--resume", action="store_true", help="Append to an existing run and skip completed model/scenario/repeat tuples.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.repeat < 1 or args.map_limit < 1 or args.llm_limit < 1:
        parser.error("--repeat, --map-limit and --llm-limit must be positive integers.")
    try:
        exit_code = asyncio.run(run(args))
    except ValueError as exc:
        parser.error(str(exc))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
