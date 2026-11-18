"""Analyse the imperfect-user benchmark (opt-out and vague-then-exact answers).

No LLM calls. Reads ``runs.jsonl`` and the per-run artifacts of a
benchmark_cli output directory produced from ``imperfect_user.yaml``, and
reports per profile:

* opt-out: final state of the declined dimension (NOT_REQUESTED expected),
  whether it was asked again, turns == k, absence of filter atoms for the
  declined dimension, and filter F1 on the *other* dimensions against the
  strict-majority oracle reference (declined-dimension atoms removed). No
  ranking agreement with the oracle is reported: the oracle still contains
  the declined constraint.
* vague: share of runs with a follow-up on the vague dimension (turns ==
  k+1), final state SPECIFIED, top-5 Jaccard / RBO with the oracle runs of
  the same output directory, and filter F1.

Means are taken per base intent, then over intents, with a percentile
cluster bootstrap over intents (as in compare_conditions.py).

Usage:
    uv run --project backend python backend/experiments/analyze_imperfect_user.py \
        --results backend/experiments/results/imperfect_user_haiku
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compare_conditions import (  # noqa: E402
    RankingComparer,
    atom_dim,
    atom_prf,
    cluster_bootstrap,
    filter_atoms,
    load_rows,
    majority_atoms,
    mean_pairs,
)


def _artifact(results: Path, row: dict[str, Any]) -> dict[str, Any]:
    path = results / (row.get("artifact_file") or f"runs/{row['run_id']}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(per_intent: dict[str, list[float]], b: int, seed: int) -> dict[str, Any]:
    means = {intent: sum(v) / len(v) for intent, v in per_intent.items() if v}
    return {**cluster_bootstrap(means, b=b, seed=seed), "runs": sum(len(v) for v in per_intent.values())}


def analyse(results: Path, b: int, seed: int, permutations: int, p: float) -> dict[str, Any]:
    rows, skipped = load_rows(results)
    oracle_by_intent: dict[str, list[dict]] = defaultdict(list)
    refined: list[dict] = []
    for row in rows:
        if row["condition"] == "oracle" and row["status"] == "completed":
            oracle_by_intent[row["unit_id"]].append(row)
        elif row["condition"] == "refined":
            refined.append(row)
    reference = {intent: majority_atoms([filter_atoms(r) for r in runs]) for intent, runs in oracle_by_intent.items()}
    comparer = RankingComparer(permutations, seed, p)

    metrics: dict[str, dict[str, dict[str, list[float]]]] = {
        "optout": defaultdict(lambda: defaultdict(list)),
        "vague": defaultdict(lambda: defaultdict(list)),
    }
    status_counts: dict[str, dict[str, int]] = {"optout": defaultdict(int), "vague": defaultdict(int)}
    final_states: dict[str, dict[str, int]] = {"optout": defaultdict(int), "vague": defaultdict(int)}
    outcomes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in refined:
        artifact = _artifact(results, row)
        info = (artifact.get("scenario_definition") or {}).get("imperfect_user") or {}
        profile, dim = info.get("profile"), info.get("dimension")
        if profile not in metrics:
            continue
        status_counts[profile][row["status"]] += 1
        outcome = row["status"] if row["status"] == "completed" else (row.get("clarification_status") or row["status"])
        outcomes[f"{profile}:{dim}"][outcome] += 1
        if row["status"] != "completed":
            continue
        intent = row["base_case_id"]
        m = metrics[profile]
        conversation = artifact.get("conversation") or {}
        state = (conversation.get("mapping") or {}).get(dim)
        final_states[profile][str(state)] += 1
        turns = conversation.get("turns") or []
        k = row["missing_count"]
        asked = sum(1 for t in turns if dim in (t.get("target_dimensions") or []))
        atoms = filter_atoms(row)
        ref = reference.get(intent, set())
        if profile == "optout":
            m["not_requested"][intent].append(float(state == "NOT_REQUESTED"))
            m["asked_once"][intent].append(float(asked == 1))
            m["turns_eq_k"][intent].append(float(row.get("turns") == k))
            m["no_declined_atoms"][intent].append(float(not any(atom_dim(a) == dim for a in atoms)))
            if intent in reference:
                others = {a for a in atoms if atom_dim(a) != dim}
                ref_others = {a for a in ref if atom_dim(a) != dim}
                m["filter_f1_other_dims"][intent].append(atom_prf(others, ref_others)["f1"])
        else:
            m["followup"][intent].append(float(asked >= 2))
            m["turns_eq_k_plus_1"][intent].append(float(row.get("turns") == k + 1))
            m["specified"][intent].append(float(state == "SPECIFIED"))
            if intent in reference:
                m["filter_f1"][intent].append(atom_prf(atoms, ref)["f1"])
            pairs, _, _ = mean_pairs(comparer, [row], oracle_by_intent.get(intent, []))
            for key in ("jaccard5_served", "rbo10_served"):
                if pairs.get(key) is not None:
                    m[key][intent].append(pairs[key])
            m["clarification_seconds"][intent].append(float(row.get("clarification_seconds") or 0))

    out: dict[str, Any] = {
        "results": str(results),
        "skipped": skipped,
        "oracle_runs": {i: len(r) for i, r in oracle_by_intent.items()},
        "status_counts": {p: dict(c) for p, c in status_counts.items()},
        "final_state_of_altered_dimension": {p: dict(c) for p, c in final_states.items()},
        "outcome_by_profile_and_dimension": {k: dict(v) for k, v in sorted(outcomes.items())},
        "bootstrap": b,
    }
    for profile, by_metric in metrics.items():
        out[profile] = {name: _summary(per_intent, b, seed) for name, per_intent in by_metric.items()}
    noise = defaultdict(list)
    for intent, runs in oracle_by_intent.items():
        pairs, used, _ = mean_pairs(comparer, runs, runs, same=True)
        if used and pairs.get("jaccard5_served") is not None:
            noise[intent].append(pairs["jaccard5_served"])
    out["oracle_vs_oracle_jaccard5"] = _summary(noise, b, seed)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--permutations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--rbo-p", type=float, default=0.8)
    args = parser.parse_args(argv)
    result = analyse(args.results, args.bootstrap, args.seed, args.permutations, args.rbo_p)
    (args.results / "imperfect_user_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"status: {result['status_counts']}")
    print(f"final state of altered dimension: {result['final_state_of_altered_dimension']}")
    for key, counts in result["outcome_by_profile_and_dimension"].items():
        print(f"  outcome {key:<10} {counts}")
    for profile in ("optout", "vague"):
        print(f"\n{profile}:")
        for name, s in result[profile].items():
            if s["mean"] is None:
                continue
            print(f"  {name:<22} {s['mean']:.3f} [{s['ci_low']:.3f}, {s['ci_high']:.3f}] intents={s['n']} runs={s['runs']}")
    s = result["oracle_vs_oracle_jaccard5"]
    if s["mean"] is not None:
        print(f"\noracle vs oracle J5      {s['mean']:.3f} [{s['ci_low']:.3f}, {s['ci_high']:.3f}] intents={s['n']}")
    print(f"\nWrote {args.results / 'imperfect_user_summary.json'}")


if __name__ == "__main__":
    main()
