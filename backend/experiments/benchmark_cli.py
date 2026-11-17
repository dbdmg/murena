"""Run MURENA analyses from a scenario file without starting the web UI/API.

Three experimental conditions share the same ``analysis_service.run_analysis``
call with identical options; they differ only in the submitted query:

* ``refined``  - SAGE clarification dialogue from ``initial_query`` (simulated
  user answers from ``clarifications``); the reviewed refined query is analysed.
  Units: every scenario, including k=0 controls.
* ``one_shot`` - ``one_shot_query`` (or ``initial_query``) submitted directly.
  Units: scenarios with ``missing_count`` >= 1.
* ``oracle``   - ``oracle_query`` submitted directly. Units: one per
  ``base_case_id`` (deduplicated), repeated ``--oracle-repeat`` times.

Jobs follow the requested condition order, scenario file order and repetition order.
Each run is keyed by (condition, model, unit_id, repeat, input_sha256), where
input_sha256 is the scenario digest for ``refined`` and the SHA-256 of the
submitted query plus analysis options otherwise. ``runs.jsonl`` holds one
compact, self-contained row per attempt (see ``compact_row``).
``runs/<run_id>.json`` retains metadata, dialogue, extraction outputs and the
complete matching-ID ranking, without full property records or ranking traces.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import hashlib
import os
import platform
import subprocess
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

CONDITIONS = ("refined", "one_shot", "oracle")
ROW_SCHEMA_VERSION = 2
DIMENSIONS = {"I", "D", "L", "Cb", "Ce", "Cp"}
EXTRACTION_AGENTS = {
    "building-agent": "building",
    "energy-agent": "energy",
    "proximity-agent": "proximity",
    "location-agent": "location",
    "ranking-agent": "ranking",
    "regulatory-agent": "regulatory",
    "sql-agent": "sql",
}
# Fallback when agent_trace is absent: gemini_responses keys holding the same outputs.
GEMINI_RESPONSE_KEYS = {
    "building": "building_extraction",
    "energy": "energy_analysis",
    "proximity": "proximity_analysis",
    "location": "location_extraction",
    "regulatory": "regulatory_analysis",
    "ranking": "ranking_weights",
    "sql": "sql_generation",
}


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


# ---------------------------------------------------------------------------
# Scenario loading and job construction (no LLM, no app imports)
# ---------------------------------------------------------------------------

def scenario_missing_count(scenario: dict[str, Any]) -> int:
    """Explicit ``missing_count`` (v3) or the number of expected missing dimensions (v1/v2)."""
    value = scenario.get("missing_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return len(scenario.get("expected_initial_missing") or [])


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
    disabled_ids = set()
    if isinstance(raw, dict) and 'scenarios' in raw:
        groups = raw['scenarios']
        if not isinstance(groups, list) or not groups:
            raise ValueError("'scenarios' must be a non-empty list of base scenarios.")
        raw = []
        group_ids = set()
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('id'), str) or not group['id'].strip():
                raise ValueError("Each base scenario needs a non-empty id.")
            if group['id'] in group_ids:
                raise ValueError(f"Duplicate base scenario id: {group['id']}")
            group_ids.add(group['id'])
            if type(group.get('enabled')) is not bool:
                raise ValueError(f"Base scenario {group['id']} needs boolean enabled.")
            variants = group.get('variants')
            if not isinstance(variants, list) or not variants:
                raise ValueError(f"Base scenario {group['id']} needs non-empty variants.")
            for variant in variants:
                if not isinstance(variant, dict) or variant.get('base_case_id') != group['id']:
                    raise ValueError(f"Variant base_case_id must match {group['id']}.")
                if not group['enabled']:
                    disabled_ids.add(variant.get('id'))
                raw.append(variant)
    if not isinstance(raw, list) or not raw:
        raise ValueError("Scenario file must contain a non-empty JSON array.")

    seen: set[str] = set()
    for index, scenario in enumerate(raw, start=1):
        if not isinstance(scenario, dict):
            raise ValueError(f"Scenario #{index} must be a JSON object.")
        if "enabled" in scenario:
            raise ValueError("enabled is allowed only on a base scenario, not on variants.")
        scenario_id = scenario.get("id")
        initial_query = scenario.get("initial_query")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ValueError(f"Scenario #{index} needs a non-empty string 'id'.")
        if scenario_id in seen:
            raise ValueError(f"Duplicate scenario id: {scenario_id}")
        if not isinstance(initial_query, str) or not initial_query.strip():
            raise ValueError(f"Scenario '{scenario_id}' needs a non-empty string 'initial_query'.")
        if "missing_count" in scenario and (
            not isinstance(scenario["missing_count"], int)
            or isinstance(scenario["missing_count"], bool)
            or scenario["missing_count"] < 0
        ):
            raise ValueError(f"Scenario '{scenario_id}' has invalid 'missing_count' (expected integer >= 0).")
        expected_initial_missing = scenario.get("expected_initial_missing")
        # An empty list is allowed only for explicit k=0 controls.
        allow_empty = scenario.get("missing_count") == 0
        if (
            not isinstance(expected_initial_missing, list)
            or (not expected_initial_missing and not allow_empty)
            or not all(isinstance(item, str) and item in DIMENSIONS for item in expected_initial_missing)
            or len(set(expected_initial_missing)) != len(expected_initial_missing)
        ):
            raise ValueError(
                f"Scenario '{scenario_id}' needs a unique 'expected_initial_missing' dimension list "
                "(non-empty unless missing_count is 0)."
            )
        if "missing_count" in scenario and scenario["missing_count"] != len(expected_initial_missing):
            raise ValueError(f"Scenario '{scenario_id}' missing_count does not match expected_initial_missing.")
        clarifications = scenario.get("clarifications")
        if not isinstance(clarifications, dict) or not clarifications:
            raise ValueError(f"Scenario '{scenario_id}' needs non-empty 'clarifications' keyed by dimension.")
        unknown_dimensions = set(clarifications) - DIMENSIONS
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
        if not isinstance(expected_mapping, dict) or not expected_mapping or set(expected_mapping) - DIMENSIONS:
            raise ValueError(f"Scenario '{scenario_id}' has invalid 'expected_mapping' dimension keys.")
        if set(expected_initial_missing) - set(expected_mapping):
            raise ValueError(f"Scenario '{scenario_id}' expected_mapping must include every initially missing dimension.")
        allowed_statuses = {"SPECIFIED", "NOT_REQUESTED", "UNCONFIRMED_ABSENT", "AMBIGUOUS", "MISSING_CRITICAL"}
        if any(not isinstance(status, str) or status not in allowed_statuses for status in expected_mapping.values()):
            raise ValueError(f"Scenario '{scenario_id}' has invalid expected mapping status.")
        for field in ("reviewed_query", "one_shot_query", "oracle_query", "base_case_id"):
            if field in scenario and (not isinstance(scenario[field], str) or not scenario[field].strip()):
                raise ValueError(f"Scenario '{scenario_id}' '{field}' must be a non-empty string when provided.")
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
    return [s for s in raw if s["id"] not in disabled_ids]


def scenario_digest(scenario: dict[str, Any]) -> str:
    """Hash one normalized scenario definition independently of file ordering/formatting."""
    canonical = json.dumps(scenario, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def query_digest(query: str, options: dict[str, Any]) -> str:
    """Hash a directly submitted query together with the analysis options."""
    canonical = json.dumps(
        {"query": query, "options": options}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def analysis_options(args: argparse.Namespace, scenario: dict[str, Any]) -> dict[str, Any]:
    """Identical run_analysis options for every condition (scenario overrides apply)."""
    return {
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


def build_jobs(
    scenarios: list[dict[str, Any]], args: argparse.Namespace, model: str
) -> list[dict[str, Any]]:
    """Plan jobs in condition, scenario-file and repetition order."""
    conditions = list(dict.fromkeys(args.condition or ["refined"]))
    oracle_repeat = args.oracle_repeat if args.oracle_repeat is not None else args.repeat
    jobs: list[dict[str, Any]] = []
    for condition in conditions:
        if condition == "refined":
            for scenario in scenarios:
                for repeat_index in range(1, max(args.repeat, scenario.get("repeats", 1)) + 1):
                    jobs.append({
                        "condition": "refined",
                        "model": model,
                        "unit_id": scenario["id"],
                        "scenario_id": scenario["id"],
                        "base_case_id": scenario.get("base_case_id"),
                        "missing_count": scenario_missing_count(scenario),
                        "repeat": repeat_index,
                        "scenario": scenario,
                        "query": None,
                        "options": analysis_options(args, scenario),
                        "input_sha256": scenario_digest(scenario),
                    })
        elif condition == "one_shot":
            for scenario in scenarios:
                if scenario_missing_count(scenario) < 1:
                    continue
                query = scenario.get("one_shot_query") or scenario["initial_query"]
                options = analysis_options(args, scenario)
                for repeat_index in range(1, max(args.repeat, scenario.get("repeats", 1)) + 1):
                    jobs.append({
                        "condition": "one_shot",
                        "model": model,
                        "unit_id": scenario["id"],
                        "scenario_id": scenario["id"],
                        "base_case_id": scenario.get("base_case_id"),
                        "missing_count": scenario_missing_count(scenario),
                        "repeat": repeat_index,
                        "scenario": scenario,
                        "query": query,
                        "options": options,
                        "input_sha256": query_digest(query, options),
                    })
        elif condition == "oracle":
            units: dict[str, dict[str, Any]] = {}
            for scenario in scenarios:
                if not scenario.get("oracle_query"):
                    raise ValueError(
                        f"Condition 'oracle' needs 'oracle_query' in every scenario; missing in '{scenario['id']}'."
                    )
                base = scenario.get("base_case_id") or scenario["id"]
                options = analysis_options(args, scenario)
                unit = units.setdefault(base, {
                    "query": scenario["oracle_query"], "options": options, "scenario": scenario,
                })
                if unit["query"] != scenario["oracle_query"] or unit["options"] != options:
                    raise ValueError(f"Inconsistent oracle_query/options within base_case_id '{base}'.")
            for base, unit in units.items():
                for repeat_index in range(1, oracle_repeat + 1):
                    jobs.append({
                        "condition": "oracle",
                        "model": model,
                        "unit_id": base,
                        "scenario_id": None,
                        "base_case_id": base,
                        "missing_count": None,
                        "repeat": repeat_index,
                        "scenario": unit["scenario"],
                        "query": unit["query"],
                        "options": unit["options"],
                        "input_sha256": query_digest(unit["query"], unit["options"]),
                    })
        else:  # argparse restricts choices; keep a defensive error.
            raise ValueError(f"Unknown condition: {condition}")
    return jobs


def job_key(job: dict[str, Any]) -> tuple[str, str, str, int, str]:
    return (job["condition"], job["model"], job["unit_id"], job["repeat"], job["input_sha256"])


# ---------------------------------------------------------------------------
# Metrics and compaction helpers (pure functions)
# ---------------------------------------------------------------------------

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


def detection_metrics(expected: list[str] | set[str], predicted: list[str] | set[str]) -> dict[str, Any]:
    """Initial missing-dimension detection P/R/F1 with explicit empty-set conventions.

    both empty -> 1.0/1.0/1.0; predicted empty, expected not -> P=None, R=0, F1=0;
    expected empty, predicted not -> P=0, R=None, F1=0 (unnecessary detection).
    """
    expected_set, predicted_set = set(expected), set(predicted)
    if not expected_set and not predicted_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not predicted_set:
        return {"precision": None, "recall": 0.0, "f1": 0.0}
    if not expected_set:
        return {"precision": 0.0, "recall": None, "f1": 0.0}
    overlap = expected_set & predicted_set
    precision = len(overlap) / len(predicted_set)
    recall = len(overlap) / len(expected_set)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def extract_top(buildings: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """Top matching buildings in served rank order (non-matching filler excluded)."""
    top = []
    for item in buildings or []:
        if not isinstance(item, dict) or not item.get("is_match"):
            continue
        top.append({
            "id": str(item.get("id")),
            "score": item.get("score"),
            "distance_km": item.get("distance_km"),
        })
        if len(top) >= limit:
            break
    return top


def _as_obj(value: Any) -> Any:
    """Parse a recorded agent output; accept Markdown-fenced JSON like the pipeline does."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            try:
                from app.utils.json_parser import safe_extract_json

                parsed = safe_extract_json(value)
            except Exception:  # Parsing a trace must never fail a run.
                parsed = None
            return parsed if parsed is not None else value
    return value


def agent_extractions(api_response: dict[str, Any]) -> dict[str, Any]:
    """First extraction-mode output of each agent (pre-relaxation interpretation).

    Reads ``agent_trace`` entries with ``agent_mode == 'extraction'``; falls back
    to the matching ``gemini_responses[...]['response']`` when the trace lacks an agent.
    """
    found: dict[str, Any] = {}
    for step in api_response.get("agent_trace") or []:
        if not isinstance(step, dict) or step.get("agent_mode") != "extraction":
            continue
        name = EXTRACTION_AGENTS.get(step.get("agent_name"))
        if name and name not in found:
            found[name] = _as_obj(step.get("output"))
    responses = api_response.get("gemini_responses") or {}
    for name, key in GEMINI_RESPONSE_KEYS.items():
        if name in found:
            continue
        entry = responses.get(key)
        if isinstance(entry, dict) and "response" in entry:
            found[name] = _as_obj(entry["response"])
    return found


def compact_artifact(record: dict[str, Any]) -> dict[str, Any]:
    """Schema 3 storage: complete matching-ID order, top-10 scores, extraction evidence.

    Keep only extraction outputs from the API. Ranking traces, context, HTML and
    full property records duplicate the dataset and are deliberately not stored.
    The source record is not mutated; legacy records can still build compact rows.
    """
    api = record.get("api_response") or {}
    extractions = agent_extractions(api)
    row = compact_row(record)
    names = {value: key for key, value in EXTRACTION_AGENTS.items()}
    compact_api = {
        "agent_trace": [{"agent_name": names[name], "agent_mode": "extraction", "output": output}
                        for name, output in extractions.items() if name in names],
        "relaxation_applied": row["relaxation_applied"],
        "relaxation_count": row["relaxation_count"],
        "fallback_activated": row["fallback_activated"],
        "agent_errors": row["agent_errors"],
    }
    return {
        **{key: value for key, value in record.items() if key != "api_response"},
        "artifact_schema_version": 3,
        "ranking_ids": list(record.get("ranking_ids", api.get("ranking_ids")) or []),
        "top": row["top"],
        "api_response": compact_api,
    }


def compact_row(record: dict[str, Any]) -> dict[str, Any]:
    """Self-contained runs.jsonl row built from a full run record (see module docstring)."""
    api = record.get("api_response") or {}
    responses = api.get("gemini_responses") or {}
    extractions = agent_extractions(api) if api else {}
    regulatory = extractions.get("regulatory") if isinstance(extractions.get("regulatory"), dict) else {}
    sql_output = extractions.get("sql") if isinstance(extractions.get("sql"), dict) else {}
    conversation = record.get("conversation") or {}
    condition = record.get("condition", "refined")
    fallback = api.get("fallback_activated")
    if fallback is None and isinstance(responses, dict) and "fallback_activated" in responses:
        fallback = responses.get("fallback_activated")
    row: dict[str, Any] = {
        "schema_version": ROW_SCHEMA_VERSION,
        "run_id": record.get("run_id"),
        "condition": condition,
        "model": record.get("model"),
        "unit_id": record.get("unit_id") or record.get("scenario_id"),
        "scenario_id": record.get("scenario_id"),
        "base_case_id": record.get("base_case_id"),
        "missing_count": record.get("missing_count"),
        "repeat": record.get("repeat"),
        "attempt": record.get("attempt"),
        "input_sha256": record.get("input_sha256") or record.get("scenario_sha256"),
        "scenario_sha256": record.get("scenario_sha256"),
        "status": record.get("status"),
        "started_at": record.get("started_at"),
        "duration_seconds": record.get("duration_seconds"),
        "clarification_seconds": record.get("clarification_seconds"),
        "analysis_seconds": record.get("analysis_seconds"),
        "submitted_query": record.get("submitted_query"),
        "final_sql": record.get("final_sql"),
        "sql_agent_sql": sql_output.get("sql"),
        "results_count": record.get("results_count"),
        "top": record.get("top", extract_top(api.get("buildings") or [])),
        "matched_use_cases": regulatory.get("matched_use_cases") if regulatory else None,
        "requirements": regulatory.get("requirements") if regulatory else None,
        "extractions": {
            name: extractions.get(name)
            for name in ("building", "energy", "proximity", "location", "ranking")
        },
        "relaxation_applied": api.get("relaxation_applied"),
        "relaxation_count": api.get("relaxation_count"),
        "fallback_activated": fallback,
        "agent_errors": api.get("agent_errors"),
        "quality": record.get("quality"),
        # Refined-only dialogue fields (None for one_shot / oracle).
        "clarification_status": None,
        "turns": None,
        "turn_targets": None,
        "initial_missing": None,
        "expected_initial_missing": None,
        "detection": None,
        "no_clarification": None,
        "mapping_accuracy": None,
        "refined_query": None,
        "artifact_file": record.get("artifact_file"),
    }
    if condition == "refined" and conversation:
        turns = conversation.get("turns") or []
        row.update({
            "clarification_status": conversation.get("status"),
            "turns": len(turns),
            "turn_targets": [turn.get("target_dimensions", []) for turn in turns],
            "initial_missing": conversation.get("initial_missing"),
            "expected_initial_missing": conversation.get("expected_initial_missing"),
            "detection": conversation.get("missing_detection"),
            "no_clarification": conversation.get("no_clarification", len(turns) == 0 if conversation.get("status") == "READY" else None),
            "mapping_accuracy": conversation.get("mapping_accuracy"),
            "refined_query": conversation.get("refined_query"),
        })
    if record.get("error"):
        row["error"] = record["error"]
    return row


# ---------------------------------------------------------------------------
# SAGE dialogue simulation
# ---------------------------------------------------------------------------

def simulate_conversation(scenario: dict[str, Any]) -> dict[str, Any]:
    """Drive the same SAGE clarification service used by the frontend, in an isolated DB.

    READY without any clarification turn is a valid outcome (k=0 controls or a
    missed omission): it is reported as ``no_clarification=True`` and the
    reviewed refined query is analysed as usual.
    """
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
            detection = detection_metrics(expected_missing, initial_missing)
            base = {
                "session_id": session_id,
                "initial_dimension_state": initial_dimension_state,
                "initial_missing": initial_missing,
                "expected_initial_missing": sorted(expected_missing),
                "missing_detection": detection,
                "turns": turns,
                "messages": messages,
            }

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
                        **base,
                        "status": "INCOMPLETE",
                        "no_clarification": False,
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
            final = {
                **base,
                "dimension_state": dimension_state,
                "mapping": mapping,
                "expected_mapping": expected,
                "mapping_accuracy": mapping_accuracy,
                "no_clarification": not turns,
            }
            if response.status == "READY":
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
                    **final,
                    "status": "READY",
                    "refined_query": response.refined_query,
                    "reviewed_query": reviewed_query,
                }
            if response.status == "BLOCKED" and response.message and messages[-1]["content"] != response.message:
                messages.append({"role": "assistant", "content": response.message})
            return {
                **final,
                "status": response.status,
                "error": response.message or f"Clarification ended with status {response.status}.",
            }
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------

def git_provenance() -> dict[str, Any]:
    def call(*command: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *command], cwd=ROOT, capture_output=True, text=True, timeout=20, check=True,
            )
            return completed.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    status = call("status", "--porcelain")
    return {"commit": call("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def llm_provenance(settings: Any) -> dict[str, Any]:
    model = settings.LLM_MODEL
    base_url = getattr(settings, "LLM_BASE_URL", None) or getattr(settings, "OPENAI_API_BASE", None)
    try:
        from app.services.llm.providers import normalize_provider, resolve_provider

        provider = normalize_provider(resolve_provider(model, base_url))
    except Exception:  # Provenance must never block a run.
        provider = getattr(settings, "LLM_PROVIDER", None) or None
    effort = None
    if provider == "codex_exec":
        effort = getattr(settings, "CODEX_REASONING_EFFORT", None)
    elif provider == "claude_cli":
        effort = getattr(settings, "CLAUDE_CLI_EFFORT", None)
    return {
        "provider": provider,
        "model": model,
        "reasoning_effort": effort,
        "codex_reasoning_effort_setting": getattr(settings, "CODEX_REASONING_EFFORT", None),
        "claude_cli_effort_setting": getattr(settings, "CLAUDE_CLI_EFFORT", None),
        "temperature": getattr(settings, "AGENT_TEMPERATURE", None),
    }


def sage_provenance(settings: Any) -> dict[str, Any]:
    return {
        "enabled": getattr(settings, "ENABLE_SAGE_CLARIFICATION", None),
        "max_turns": getattr(settings, "SAGE_MAX_TURNS", None),
        "redundancy_lambda": getattr(settings, "SAGE_REDUNDANCY_LAMBDA", None),
        "evpi_stop_alpha": getattr(settings, "SAGE_EVPI_STOP_ALPHA", None),
    }


# ---------------------------------------------------------------------------
# Resume bookkeeping
# ---------------------------------------------------------------------------

def legacy_row_hash(row: dict[str, Any], output_dir: Path, previous_manifest: dict[str, Any] | None) -> str:
    """Scenario hash of a v1 row that predates hash recording."""
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
    if isinstance(definition, dict):
        return scenario_digest(definition)
    return (previous_manifest or {}).get("scenarios_sha256", "legacy")


def row_key(row: dict[str, Any], output_dir: Path, previous_manifest: dict[str, Any] | None) -> tuple[str, str, str, int, str]:
    """(condition, model, unit_id, repeat, input_sha256) for current and legacy rows."""
    input_hash = row.get("input_sha256") or row.get("scenario_sha256")
    if input_hash is None:
        input_hash = legacy_row_hash(row, output_dir, previous_manifest)
    return (
        row.get("condition", "refined"),
        row["model"],
        row.get("unit_id") or row["scenario_id"],
        row["repeat"],
        input_hash,
    )


def read_rows(runs_path: Path) -> list[dict[str, Any]]:
    rows = []
    if runs_path.exists():
        with runs_path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def resume_state(
    rows: list[dict[str, Any]], output_dir: Path, previous_manifest: dict[str, Any] | None
) -> tuple[set, dict, dict]:
    """Completed full keys, latest status per hash-less key, and attempt counts per full key."""
    latest_full: dict[tuple, dict[str, Any]] = {}
    latest_status: dict[tuple, str] = {}
    attempts: dict[tuple, int] = {}
    for row in rows:
        try:
            key = row_key(row, output_dir, previous_manifest)
        except (KeyError, TypeError):
            continue
        latest_full[key] = row
        latest_status[key[:4]] = row.get("status", "")
        attempts[key] = attempts.get(key, 0) + 1
    completed = set()
    for key, row in latest_full.items():
        if row.get("status") != "completed":
            continue
        artifact_file = row.get("artifact_file")
        if artifact_file and not (output_dir / artifact_file).is_file():
            continue
        completed.add(key)
    return completed, latest_status, attempts


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _mean(values: list[float], digits: int) -> Any:
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), digits) if values else ""


def write_summary(
    rows: list[dict[str, Any]], output_dir: Path, previous_manifest: dict[str, Any] | None, summary_path: Path
) -> int:
    latest: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        try:
            key = row_key(row, output_dir, previous_manifest)
        except (KeyError, TypeError):
            continue
        if row.get("schema_version") != ROW_SCHEMA_VERSION:
            # Legacy index rows: rebuild the compact view from the artifact (or the row itself).
            record = row
            artifact_file = row.get("artifact_file")
            if artifact_file and (output_dir / artifact_file).is_file():
                try:
                    record = json.loads((output_dir / artifact_file).read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    record = row
            row = {**compact_row({**record, "status": row.get("status", record.get("status"))}),
                   "input_sha256": key[4], "unit_id": key[2], "condition": key[0]}
        latest[key] = row
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for key, row in latest.items():
        condition, model, unit_id, _repeat, input_hash = key
        groups.setdefault((condition, model, unit_id, input_hash), []).append(row)
    summary_rows = []
    for (condition, model, unit_id, input_hash), group in sorted(groups.items()):
        successes = [row for row in group if row.get("status") == "completed"]
        first = group[0]
        summary_rows.append({
            "condition": condition,
            "model": model,
            "unit_id": unit_id,
            "scenario_id": first.get("scenario_id") or "",
            "base_case_id": first.get("base_case_id") or "",
            "missing_count": "" if first.get("missing_count") is None else first.get("missing_count"),
            "input_sha256": input_hash,
            "scenario_sha256": first.get("scenario_sha256") or "",
            "runs": len(group),
            "successes": len(successes),
            "errors": len(group) - len(successes),
            "no_clarification_runs": sum(1 for row in successes if row.get("no_clarification")),
            "mean_duration_seconds": _mean([row.get("duration_seconds") for row in successes], 3),
            "mean_clarification_seconds": _mean([row.get("clarification_seconds") for row in successes], 3),
            "mean_analysis_seconds": _mean([row.get("analysis_seconds") for row in successes], 3),
            "mean_results_count": _mean([row.get("results_count") or 0 for row in successes], 2),
            "mean_expected_recall": _mean([(row.get("quality") or {}).get("recall") for row in successes], 4),
            "mean_clarification_turns": _mean([row.get("turns") for row in successes], 2),
            "mean_mapping_accuracy": _mean([row.get("mapping_accuracy") for row in successes], 4),
            "mean_initial_missing_f1": _mean([(row.get("detection") or {}).get("f1") for row in successes], 4),
        })
    fields = [
        "condition", "model", "unit_id", "scenario_id", "base_case_id", "missing_count", "input_sha256",
        "scenario_sha256", "runs", "successes", "errors", "no_clarification_runs", "mean_duration_seconds",
        "mean_clarification_seconds", "mean_analysis_seconds", "mean_results_count", "mean_expected_recall",
        "mean_clarification_turns", "mean_mapping_accuracy", "mean_initial_missing_f1",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)
    return len(latest)


# ---------------------------------------------------------------------------
# Job selection shared by dry-run and execution
# ---------------------------------------------------------------------------

def select_jobs(
    jobs: list[dict[str, Any]], args: argparse.Namespace, completed: set, latest_status: dict
) -> list[tuple[dict[str, Any], str | None]]:
    """Pair each planned job with a skip reason (None means it will run)."""
    selected = []
    rerun = set(args.rerun_scenario)
    for job in jobs:
        key = job_key(job)
        reason = None
        if rerun:
            if job["unit_id"] not in rerun and job["scenario_id"] not in rerun and job["base_case_id"] not in rerun:
                reason = "cached (outside selected scenarios)"
        elif args.retry_failed:
            if latest_status.get(key[:4]) != "error":
                reason = "cached (not failed)"
        elif key in completed:
            reason = "cached"
        selected.append((job, reason))
    return selected


def dry_run(args: argparse.Namespace) -> int:
    scenarios = load_scenarios(args.scenarios.resolve())
    validate_rerun_ids(args, scenarios)
    try:
        from app.core.config import settings  # configuration only, no LLM call

        model = settings.LLM_MODEL
    except Exception:
        model = "unknown-model"
    jobs = build_jobs(scenarios, args, model)
    completed: set = set()
    latest_status: dict = {}
    output_dir = args.output.resolve()
    if args.resume and (output_dir / "runs.jsonl").exists():
        previous_manifest = None
        if (output_dir / "manifest.json").exists():
            previous_manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        completed, latest_status, _ = resume_state(read_rows(output_dir / "runs.jsonl"), output_dir, previous_manifest)
    plan = select_jobs(jobs, args, completed, latest_status)
    counts: dict[str, list[int]] = {}
    for index, (job, reason) in enumerate(plan, start=1):
        counts.setdefault(job["condition"], [0, 0])[0 if reason is None else 1] += 1
        query = job["query"] if job["query"] is not None else job["scenario"]["initial_query"]
        state = "RUN" if reason is None else reason.upper()
        print(
            f"[{index}/{len(plan)}] {state:<6} {job['condition']:<8} {job['unit_id']:<32} "
            f"k={'' if job['missing_count'] is None else job['missing_count']:<2} r={job['repeat']} "
            f"sha={job['input_sha256'][:10]} | {query[:70]}"
        )
    print(f"\nDry run: model={model} conditions={list(dict.fromkeys(args.condition or ['refined']))}")
    print(f"  enabled bases={len({s.get('base_case_id') or s['id'] for s in scenarios})} variants={len(scenarios)}")
    for condition, (to_run, skipped) in counts.items():
        print(f"  {condition:<8} planned={to_run + skipped:>4} to_run={to_run:>4} skipped={skipped:>4}")
    print(f"  total    planned={len(plan):>4} to_run={sum(1 for _, r in plan if r is None):>4}")
    return 0


def validate_rerun_ids(args: argparse.Namespace, scenarios: list[dict[str, Any]]) -> None:
    known = {scenario["id"] for scenario in scenarios} | {
        scenario.get("base_case_id") for scenario in scenarios if scenario.get("base_case_id")
    }
    unknown = set(args.rerun_scenario) - known
    if unknown:
        raise ValueError("Cannot rerun unknown scenario(s): " + ", ".join(sorted(unknown)))


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

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
    validate_rerun_ids(args, scenarios)
    conditions = list(dict.fromkeys(args.condition or ["refined"]))
    oracle_repeat = args.oracle_repeat if args.oracle_repeat is not None else args.repeat
    scenarios_sha256 = hashlib.sha256(args.scenarios.read_bytes()).hexdigest()
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

    previous_manifest: dict[str, Any] | None = None
    if args.resume and manifest_path.exists():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.retry_failed and (not runs_path.exists() or not manifest_path.exists()):
        raise ValueError("Cannot retry failed runs: the output directory needs an existing manifest.json and runs.jsonl.")
    completed: set = set()
    latest_status: dict = {}
    attempt_counts: dict = {}
    if args.resume and runs_path.exists():
        completed, latest_status, attempt_counts = resume_state(read_rows(runs_path), output_dir, previous_manifest)

    git = git_provenance()
    manifest = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scenario_file": str(args.scenarios.resolve()),
        "models": models,
        "conditions": conditions,
        "clarification_mode": "SageClarifier",
        "review_policy": "auto_accept_refined_query_unless_scenario_overrides_it",
        "dataset_key_default": args.dataset,
        "dataset_file": str(Path(dataset_path).resolve()),
        "dataset_sha256": await asyncio.to_thread(file_sha256, Path(dataset_path)),
        "repeat_default": args.repeat,
        "oracle_repeat": oracle_repeat,
        "scenarios_sha256": scenarios_sha256,
        "scenario_hash_history": [scenarios_sha256],
        "enabled_scenario_ids": sorted({s.get("base_case_id") or s["id"] for s in scenarios}),
        "enabled_variant_ids": [s["id"] for s in scenarios],
        "enabled_scenario_count": len({s.get("base_case_id") or s["id"] for s in scenarios}),
        "sage": sage_provenance(settings),
        "llm": llm_provenance(settings),
        "git": git,
        "git_history": [git],
        "concurrency": args.concurrency,
        "concurrency_history": [args.concurrency],
        "resume_actions": [],
        "python": platform.python_version(),
        "run_artifacts_directory": "runs",
        "run_artifact_schema_version": 3,
        "runs_jsonl_schema_version": ROW_SCHEMA_VERSION,
        "options": {
            "map_limit": args.map_limit,
            "llm_limit": args.llm_limit,
            "use_relaxation": args.use_relaxation,
        },
    }
    if args.resume and manifest_path.exists():
        for field in ("models", "dataset_key_default", "repeat_default", "oracle_repeat",
                      "dataset_sha256", "sage", "llm"):
            if field in previous_manifest and previous_manifest.get(field) != manifest.get(field):
                raise ValueError(f"Cannot resume: benchmark setting '{field}' differs from the existing manifest.")
        if previous_manifest.get("conditions", ["refined"]) != conditions:
            raise ValueError("Cannot resume: benchmark setting 'conditions' differs from the existing manifest.")
        previous_options = dict(previous_manifest.get("options", {}))
        # Language is fixed internally; concurrency is recorded but never blocks a resume.
        previous_options.pop("output_language", None)
        previous_options.pop("concurrency", None)
        if any(previous_options[key] != manifest["options"].get(key) for key in previous_options):
            raise ValueError("Cannot resume: benchmark setting 'options' differs from the existing manifest.")
        scenario_hash_history = previous_manifest.get(
            "scenario_hash_history", [previous_manifest.get("scenarios_sha256")]
        )
        manifest["scenario_hash_history"] = list(dict.fromkeys(
            [value for value in scenario_hash_history if value] + [scenarios_sha256]
        ))
        manifest["git_history"] = list(previous_manifest.get("git_history", [])) + [git]
        legacy_concurrency = (previous_manifest.get("options") or {}).get("concurrency")
        manifest["concurrency_history"] = list(previous_manifest.get(
            "concurrency_history", [legacy_concurrency] if legacy_concurrency else []
        )) + [args.concurrency]
        manifest["started_at_first"] = previous_manifest.get("started_at_first", previous_manifest.get("started_at"))
        manifest["resume_actions"] = list(previous_manifest.get("resume_actions", []))
        if args.rerun_scenario:
            action = {"action": "rerun_scenarios", "scenario_ids": sorted(set(args.rerun_scenario))}
        elif args.retry_failed:
            action = {"action": "retry_failed"}
        else:
            action = {"action": "resume_pending"}
        manifest["resume_actions"].append({"at": manifest["started_at"], **action})
    elif args.resume and runs_path.exists():
        raise ValueError("Cannot safely resume: runs.jsonl exists but manifest.json is missing.")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    new_runs: list[dict[str, Any]] = []
    output_lock = asyncio.Lock()
    concurrency_limit = asyncio.Semaphore(args.concurrency)

    # Load the shared dataset and graph before scheduling workers. This avoids
    # concurrent cache initialization and keeps model selection fixed per batch.
    await asyncio.to_thread(analysis_service._get_or_load_dataset, args.dataset)

    async def execute_one(index: int, total: int, job: dict[str, Any], output: Any) -> dict[str, Any]:
        run_id = f"bench_{uuid.uuid4().hex[:12]}"
        started = time.perf_counter()
        scenario = job["scenario"]
        condition = job["condition"]
        options = job["options"]
        label = f"{condition} / {job['model']} / {job['unit_id']} / repeat {job['repeat']}"
        record: dict[str, Any] = {
            "run_id": run_id,
            "condition": condition,
            "unit_id": job["unit_id"],
            "scenario_id": job["scenario_id"],
            "base_case_id": job["base_case_id"],
            "missing_count": job["missing_count"],
            "scenario_name": scenario.get("name") if job["scenario_id"] else None,
            "tags": scenario.get("tags", []) if job["scenario_id"] else [],
            "model": job["model"],
            "repeat": job["repeat"],
            "attempt": attempt_counts.get(job_key(job), 0) + 1,
            "input_sha256": job["input_sha256"],
            "scenario_sha256": scenario_digest(scenario) if job["scenario_id"] else None,
            "initial_query": scenario["initial_query"] if condition == "refined" else job["query"],
            "options": {key: value for key, value in options.items() if key != "output_language"},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "clarification_seconds": None,
            "analysis_seconds": None,
        }
        print(f"[{index}/{total}] start {label}", flush=True)
        try:
            if condition == "refined":
                clarification_started = time.perf_counter()
                conversation = await asyncio.to_thread(simulate_conversation, scenario)
                record["clarification_seconds"] = round(time.perf_counter() - clarification_started, 3)
                record["conversation"] = conversation
                if conversation["status"] != "READY":
                    raise ValueError(conversation.get("error", "Clarification did not reach review."))
                query = conversation["reviewed_query"]
                if not query:
                    raise ValueError("Clarification reached READY without a refined query.")
            else:
                query = job["query"]

            record["submitted_query"] = query
            analysis_started = time.perf_counter()
            result = await analysis_service.run_analysis(run_id=run_id, query=query, **options)
            record["analysis_seconds"] = round(time.perf_counter() - analysis_started, 3)
            api_response = make_json_safe(result)
            buildings = api_response.get("buildings", [])
            top = extract_top(buildings)
            record.update({
                "status": "completed",
                "api_response": api_response,
                "results_count": api_response.get("results_count", len(buildings)),
                "top_ids": [item["id"] for item in top],
                "quality": result_metrics(
                    [item for item in buildings if item.get("is_match")], scenario.get("expected_ids", [])
                ),
                "final_sql": (api_response.get("filters_applied") or {}).get("final_sql"),
            })
        except Exception as exc:  # Preserve failed runs in the artifact and continue the batch.
            record.update({"status": "error", "error": str(exc)})

        record["duration_seconds"] = round(time.perf_counter() - started, 3)
        record["scenario_definition"] = scenario
        record["artifact_file"] = f"runs/{run_id}.json"
        record = compact_artifact(record)
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

            index_record = make_json_safe(compact_row(record))
            output.write(json.dumps(index_record, ensure_ascii=False) + "\n")
            output.flush()
            new_runs.append(record)
            state = "OK" if record["status"] == "completed" else "ERR"
            print(f"[{index}/{total}] {state} {label} ({record['duration_seconds']} s)", flush=True)
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
            plan = select_jobs(build_jobs(scenarios, args, model), args, completed, latest_status)
            total = len(plan)
            pending = []
            for index, (job, reason) in enumerate(plan, start=1):
                if reason is not None:
                    print(f"[{index}/{total}] {reason} {job['condition']} / {model} / {job['unit_id']} / repeat {job['repeat']}")
                    continue
                pending.append((index, total, job, output))
            await asyncio.gather(*(bounded_execute(*job) for job in pending))

    result_runs = write_summary(read_rows(runs_path), output_dir, previous_manifest, summary_path)
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["scenario_count"] = len(scenarios)
    manifest["result_runs"] = result_runs
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Benchmark artifacts: {output_dir}")
    return 1 if any(row.get("status") == "error" for row in new_runs) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MURENA benchmark scenarios (refined / one-shot / oracle) directly against the analysis service.")
    parser.add_argument("--scenarios", type=Path, required=True, help="YAML or JSON file containing benchmark scenarios.")
    parser.add_argument("--output", type=Path, default=ROOT / "backend/experiments/results/cli-benchmark", help="Directory for manifest, JSONL runs, and CSV summary.")
    parser.add_argument("--dataset", default="full", choices=["full"], help="Configured dataset key (currently only 'full' is available).")
    parser.add_argument("--condition", action="append", choices=CONDITIONS, default=None,
                        help="Experimental condition; repeatable (default: refined). Jobs follow the requested condition order and scenario file order.")
    parser.add_argument("--repeat", type=int, default=1, help="Minimum repeat count per scenario for refined/one_shot (scenario 'repeats' can request more).")
    parser.add_argument("--oracle-repeat", type=int, default=None, help="Repeats per oracle unit (one per base_case_id); default: --repeat.")
    parser.add_argument("--concurrency", type=int, default=2, help="Maximum number of runs in flight (default: 2). Use 1 for sequential execution.")
    parser.add_argument("--map-limit", type=int, default=1000)
    parser.add_argument("--llm-limit", type=int, default=10)
    parser.add_argument("--use-relaxation", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true", help="List planned jobs (and resume state) without loading data or calling any LLM.")
    parser.add_argument("--resume", action="store_true", help="Append to existing output, skip keys whose latest attempt completed with the same input hash, and run pending or failed keys.")
    parser.add_argument("--retry-failed", action="store_true", help="With --resume, rerun only (condition, model, unit, repeat) tuples whose latest attempt failed; changed inputs are kept separate by hash.")
    parser.add_argument("--rerun-scenario", action="append", default=[], metavar="ID", help="With --resume, run every planned job whose scenario id or unit id (base_case_id for oracle) matches, even if completed. May be repeated.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.repeat < 1 or args.map_limit < 1 or args.llm_limit < 1 or args.concurrency < 1:
        parser.error("--repeat, --map-limit, --llm-limit and --concurrency must be positive integers.")
    if args.oracle_repeat is not None and args.oracle_repeat < 1:
        parser.error("--oracle-repeat must be a positive integer.")
    if args.retry_failed and not args.resume:
        parser.error("--retry-failed requires --resume.")
    if args.rerun_scenario and not args.resume:
        parser.error("--rerun-scenario requires --resume.")
    if args.retry_failed and args.rerun_scenario:
        parser.error("--retry-failed and --rerun-scenario cannot be used together.")
    try:
        exit_code = dry_run(args) if args.dry_run else asyncio.run(run(args))
    except ValueError as exc:
        parser.error(str(exc))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
