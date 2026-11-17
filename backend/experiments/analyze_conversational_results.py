#!/usr/bin/env python3
"""Aggregate metrics from a conversational benchmark output directory.

Reads ``runs.jsonl`` and the per-run artifacts written by ``benchmark_cli.py``
plus the matching ``scenario_triplets.json`` (for expected use cases and the
stratification key), and prints:

* initial missing-dimension detection (micro P/R/F1, exact-match rate),
  including runs that ended without a clarification turn;
* clarification turns, final mapping accuracy, duration and result counts;
* RegulatoryAgent ``matched_use_cases`` against the expected labels for the
  conversational configuration, and the number of binding requirements;
* stability across repeats (identical final SQL, Jaccard of top-5/top-10 IDs);
* the same figures stratified by ``missing_count`` (v2) or ``category`` (v1).

Only the latest recorded attempt of each (scenario, repeat) is used. No model
calls are made.

Example:
    python backend/experiments/analyze_conversational_results.py \
        --results backend/experiments/results/missingness_v2 \
        --triplets backend/experiments/data/scenarios_v2/scenario_triplets.json
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from itertools import combinations
from pathlib import Path


def _load_runs(results: Path) -> list[dict]:
    """Latest recorded attempt per (scenario, repeat), in runs.jsonl order.

    Resumed or rerun scenarios append newer attempts, so the last line for a
    (scenario, repeat) pair reflects the most recent scenario definition.
    """
    latest: dict[tuple, dict] = {}
    for line in (results / "runs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        latest[(row["scenario_id"], row["repeat"])] = row
    return list(latest.values())


def _matched_use_cases(artifact: dict) -> list[str] | None:
    trace = ((artifact.get("api_response") or {}).get("agent_trace")) or []
    found = None
    for step in trace:
        output = step.get("output") if isinstance(step, dict) else None
        if isinstance(output, dict) and "matched_use_cases" in output:
            found = (output.get("matched_use_cases") or [], output.get("requirements") or [])
    return found


def _jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa | sb else 1.0


def _prf(records: list[dict]) -> tuple[float, float, float]:
    tp = sum(len(set(r["detected"]) & set(r["expected"])) for r in records)
    fp = sum(len(set(r["detected"]) - set(r["expected"])) for r in records)
    fn = sum(len(set(r["expected"]) - set(r["detected"])) for r in records)
    p = tp / (tp + fp) if tp + fp else 1.0
    rc = tp / (tp + fn) if tp + fn else 1.0
    return p, rc, (2 * p * rc / (p + rc) if p + rc else 0.0)


def _fmt(values: list[float], digits: int = 1) -> str:
    return f"{st.median(values):.{digits}f}" if values else "-"


def summarize(records: list[dict], label: str) -> str:
    done = [r for r in records if r["status"] == "completed"]
    p, rc, f1 = _prf(records)
    exact = sum(set(r["detected"]) == set(r["expected"]) for r in records)
    uc = [r for r in done if r["use_cases"] is not None]
    uc_ok = sum(set(r["use_cases"]) == set(r["expected_use_cases"]) for r in uc)
    turns = [r["turns"] for r in done]
    return (
        f"{label:<24} runs={len(records):>3} ok={len(done):>3} "
        f"P={p:.2f} R={rc:.2f} F1={f1:.2f} exact={exact}/{len(records)} "
        f"turns={st.mean(turns) if turns else 0:.2f} "
        f"map_acc={st.mean(r['mapping_accuracy'] for r in done) if done else 0:.2f} "
        f"use_case={uc_ok}/{len(uc)} "
        f"dur_med={_fmt([r['duration'] for r in done])}s "
        f"results_med={_fmt([r['results'] for r in done], 0)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--triplets", type=Path, required=True)
    parser.add_argument("--config-key", default=None,
                        help="Key of expected_matched_use_cases_by_configuration "
                             "(default: 'conversational' or 'refined').")
    args = parser.parse_args()

    triplets = {t["case_id"]: t for t in json.loads(args.triplets.read_text(encoding="utf-8"))}
    rows = _load_runs(args.results)

    records = []
    for row in rows:
        artifact = json.loads((args.results / row["artifact_file"]).read_text(encoding="utf-8"))
        conv = artifact.get("conversation") or {}
        triplet = triplets.get(row["scenario_id"], {})
        by_conf = triplet.get("expected_matched_use_cases_by_configuration") or {}
        key = args.config_key or ("conversational" if "conversational" in by_conf else "refined")
        matched = _matched_use_cases(artifact)
        records.append({
            "scenario": row["scenario_id"],
            "stratum": str(triplet.get("missing_count", triplet.get("category", "?"))),
            "status": row["status"],
            "detected": conv.get("initial_missing") or [],
            "expected": conv.get("expected_initial_missing") or [],
            "turns": len(conv.get("turns") or []),
            "mapping_accuracy": conv.get("mapping_accuracy") or 0.0,
            "duration": artifact.get("duration_seconds") or 0.0,
            "results": artifact.get("results_count") or 0,
            "use_cases": matched[0] if matched else None,
            "requirements": matched[1] if matched else [],
            "expected_use_cases": by_conf.get(key, triplet.get("expected_matched_use_cases", [])),
            "sql": artifact.get("final_sql"),
            "top": artifact.get("top_ids") or [],
            "error": artifact.get("error"),
        })

    print(summarize(records, "ALL"))
    strata = defaultdict(list)
    for r in records:
        strata[r["stratum"]].append(r)
    for key in sorted(strata, key=lambda k: (len(k), k)):
        print(summarize(strata[key], f"  {key}"))

    done = [r for r in records if r["status"] == "completed"]
    print(f"\nbinding regulatory requirements: {sum(bool(r['requirements']) for r in done)}/{len(done)} runs")

    by_scenario = defaultdict(list)
    for r in done:
        by_scenario[r["scenario"]].append(r)
    multi = {k: v for k, v in by_scenario.items() if len(v) > 1}
    if multi:
        same_sql = sum(len({r["sql"] for r in v}) == 1 for v in multi.values())
        j5 = st.mean(st.mean(_jaccard(a["top"][:5], b["top"][:5]) for a, b in combinations(v, 2)) for v in multi.values())
        j10 = st.mean(st.mean(_jaccard(a["top"], b["top"]) for a, b in combinations(v, 2)) for v in multi.values())
        print(f"stability: identical SQL {same_sql}/{len(multi)} scenarios; "
              f"mean top-5 Jaccard {j5:.2f}; top-10 {j10:.2f}")

    print("\nruns not exactly matching expected detection:")
    for r in sorted(records, key=lambda r: r["scenario"]):
        if set(r["detected"]) != set(r["expected"]):
            print(f"  {r['scenario']:<12} detected={sorted(r['detected'])} expected={sorted(r['expected'])} "
                  f"status={r['status']}")
    print("\nruns with unexpected matched_use_cases:")
    for r in sorted(done, key=lambda r: r["scenario"]):
        if r["use_cases"] is not None and set(r["use_cases"]) != set(r["expected_use_cases"]):
            print(f"  {r['scenario']:<12} got={r['use_cases']} expected={r['expected_use_cases']}")


if __name__ == "__main__":
    main()
