"""Export completed refined benchmark rows for the local scenario demo."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
OUTPUT = ROOT / "frontend/public/data/benchmark_runs.json"


def results_directory() -> Path:
    configured = os.environ.get("VITE_BENCHMARK_RESULTS_DIR")
    if not configured:
        env_file = FRONTEND / ".env.demo"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "VITE_BENCHMARK_RESULTS_DIR":
                    configured = value.strip().strip("\"'")
                    break
    path = Path(configured) if configured else Path("../backend/experiments/results/imperfect_user_v4_multiseed_seed13")
    return path.resolve() if path.is_absolute() else (FRONTEND / path).resolve()


def main() -> None:
    results = results_directory()
    rows = [json.loads(line) for line in (results / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    selected: dict[str, dict] = {}
    for row in rows:
        if row.get("condition") != "refined" or row.get("status") != "completed":
            continue
        artifact_file = row.get("artifact_file")
        if not artifact_file:
            continue
        artifact_path = results / artifact_file
        if not artifact_path.is_file():
            continue
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        run_id = row.get("scenario_id") or row.get("unit_id")
        definition = artifact.get("scenario_definition") or {}
        conversation = artifact.get("conversation") or {}
        scenario = {
            "case_id": run_id,
            "base_case_id": row.get("base_case_id"),
            "name": definition.get("name") or run_id,
            "profile": (definition.get("imperfect_user") or {}).get("profile"),
            "balance": (definition.get("imperfect_user") or {}).get("balance"),
            "initial_query": artifact.get("initial_query") or definition.get("initial_query") or "",
            "missing_dimensions": definition.get("expected_initial_missing") or row.get("expected_initial_missing") or [],
            "turns": [
                {"question": turn.get("question"), "answer": turn.get("answer")}
                for turn in conversation.get("turns", [])
                if isinstance(turn, dict) and turn.get("question") and turn.get("answer")
            ],
            "review_query": artifact.get("submitted_query") or row.get("submitted_query") or "",
        }
        previous = selected.get(run_id)
        if previous and (previous.get("started_at", ""), previous.get("repeat", 0)) >= (row.get("started_at", ""), row.get("repeat", 0)):
            continue
        selected[run_id] = {
            "scenario": scenario,
            "run_id": row.get("run_id"),
            "scenario_id": run_id,
            "condition": row.get("condition"),
            "model": row.get("model"),
            "repeat": row.get("repeat"),
            "query": row.get("submitted_query"),
            "results_count": row.get("results_count"),
            "top": row.get("top") or artifact.get("top") or [],
            "final_sql": row.get("final_sql") or artifact.get("final_sql"),
            "agent_trace": (artifact.get("api_response") or {}).get("agent_trace") or [],
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(selected, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Exported {len(selected)} completed refined scenarios from {results} to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
