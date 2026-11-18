"""Export completed refined benchmark rows for the local scenario demo."""

import json
import math
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
        api_artifact = artifact.get("api_response") or {}
        evaluation_results = api_artifact.get("evaluation_results") or []
        evaluation_scores = {
            str(item.get("id")): (
                item.get("final_ranking_score")
                if item.get("final_ranking_score") is not None
                else item.get("score")
            )
            for item in evaluation_results
            if isinstance(item, dict) and item.get("id") is not None
        }
        top = row.get("top") or artifact.get("top") or []
        scored_top = []
        for item in top:
            raw_score = item.get("score")
            if raw_score is None:
                raw_score = evaluation_scores.get(str(item.get("id")))
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = math.nan
            if not math.isfinite(score):
                raise ValueError(
                    f"Benchmark run {run_id} has a top result without a finite score: {item.get('id')}"
                )
            scored_top.append({**item, "score": score})
        definition = artifact.get("scenario_definition") or {}
        conversation = artifact.get("conversation") or {}
        imperfect_user = definition.get("imperfect_user") or {}
        name = definition.get("name") or run_id
        use_case = name.split("intended use:", 1)[1].split("; balance:", 1)[0].strip() if "intended use:" in name else row.get("base_case_id") or "Other"
        scenario = {
            "case_id": run_id,
            "base_case_id": row.get("base_case_id"),
            "name": name,
            "use_case": use_case,
            "profile": imperfect_user.get("profile"),
            "balance": imperfect_user.get("balance"),
            "specified_dimensions": imperfect_user.get("specified_dimensions") or [],
            "vague_dimensions": imperfect_user.get("vague_dimensions") or [],
            "optout_dimensions": imperfect_user.get("optout_dimensions") or [],
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
            "top": scored_top,
            "final_sql": row.get("final_sql") or artifact.get("final_sql"),
            "agent_trace": api_artifact.get("agent_trace") or [],
            "evaluation_results": evaluation_results,
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(selected, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Exported {len(selected)} completed refined scenarios from {results} to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
