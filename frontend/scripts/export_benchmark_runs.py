"""Export completed refined benchmark rows for the local scenario demo."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "backend/experiments/results/all_scenarios_codex"
OUTPUT = ROOT / "frontend/public/data/benchmark_runs.json"


def main() -> None:
    rows = [json.loads(line) for line in (RESULTS / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    selected: dict[str, dict] = {}
    for row in rows:
        if row.get("condition") != "refined" or row.get("status") != "completed":
            continue
        artifact_file = row.get("artifact_file")
        if not artifact_file:
            continue
        artifact_path = RESULTS / artifact_file
        if not artifact_path.is_file():
            continue
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        run_id = row.get("scenario_id") or row.get("unit_id")
        previous = selected.get(run_id)
        if previous and (previous.get("started_at", ""), previous.get("repeat", 0)) >= (row.get("started_at", ""), row.get("repeat", 0)):
            continue
        selected[run_id] = {
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
    print(f"Exported {len(selected)} completed refined scenarios to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
