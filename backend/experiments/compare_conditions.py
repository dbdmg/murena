#!/usr/bin/env python3
"""Compare refined / one-shot / oracle runs written by ``benchmark_cli.py``.

Reads only ``runs.jsonl`` (schema_version 2 rows); no artifacts, no LLM calls.

Run selection
    Latest attempt per (condition, model, unit_id, repeat). For each
    (condition, model, unit_id) only rows carrying the most recent input hash
    (last one in file order) are kept, so edited scenarios never mix with
    older definitions. Metrics use completed runs; completion rates use all.

Ranking agreement with the oracle (O = oracle runs of the same base intent)
    * Jaccard@5 on the ids of ``top[:5]``.
    * RBO@10, extrapolated, p=0.8 (Webber, Moffat & Zobel 2010, eq. 32 for
      equal lengths; for unequal lengths the extrapolation of their eq. 30/32
      for uneven lists: X_d for d > s uses the full short list, and the
      residual term is ((X_l - X_s)/l + X_s/s) * p^l).
    * Empty lists: both empty -> pair excluded and counted (``both_empty``);
      exactly one empty -> 0.
    * Tie awareness: "served" uses the served order; "tie_expected" is the
      mean over N (default 1000) seeded random permutations within equal-score
      groups (scores rounded to 6 decimals; None scores are never permuted).
      Only the stored top-10 is observable, so ties straddling rank 10 cannot
      be resolved beyond it.
    * Pairing: for each (base b, k) the metric is the mean over all repeat
      pairs (condition run r x oracle run r'). Noise ceiling: mean over
      within-intent oracle pairs (r < r'). Delta(b,k) = M(refined,O) - M(one_shot,O).

Structured filter agreement (proxy for atomic-constraint F1)
    Atoms are extracted from the agents' extraction outputs stored in the row:
      D  : ``D:use=<matched use case>`` (regulatory agent, lower-cased)
      L  : ``L:city=<place>`` (location agent; 'torino' normalised to 'turin')
           and ``L:radius=<km, 1 decimal>``
      Cb : ``Cb:surface_area>=N`` (building agent requirement, >= or >) and
           ``Cb:capacity>=N`` if any requirement targets a capacity-like column
      Ce : ``Ce:worst=<class>``, the worst allowed class under the order
           A4 > A3 > A2 > A1 > B > C > D > E > F > G (IN list -> worst member;
           '=', '<=' or '>=' with one class -> that class)
      Cp : ``Cp:<proximity column>`` (thresholds ignored: they are percentile
           roundings that vary across runs)
      I  : ``I:typology=<typology>`` (building agent typologies, lower-cased)
    Reference O*(b): atoms present in a strict majority of the oracle repeats
    (> n/2; e.g. >=2 of 3, >=3 of 5), overridable with --reference-min-votes.
    Reported: atom F1 (both empty -> 1), per-dimension recall, invented atoms
    (run atoms not in O*), and oracle self-agreement (each oracle run against
    the leave-one-out majority of the other oracle repeats). SQL consistency:
    share of L-radius/Cb/Ce/Cp atoms whose column appears in ``sql_agent_sql``.

Uncertainty
    Cluster bootstrap over base intents (B=10000, seeded, percentile 95% CI)
    for per-k means and Delta; exact sign-flip test (2^n assignments,
    two-sided) on intent-level Delta (mean over k of Delta(b,k)), plus per-k.

Example:
    uv run python backend/experiments/compare_conditions.py \
        --results backend/experiments/results/missingness_v3 \
        --output-prefix backend/experiments/results/missingness_v3/comparison
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import random
import re
import statistics as st
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

ENERGY_ORDER = ["A4", "A3", "A2", "A1", "B", "C", "D", "E", "F", "G"]  # best -> worst
FILTER_DIMS = ("I", "D", "L", "Cb", "Ce", "Cp")
CITY_ALIASES = {"torino": "turin"}
CAPACITY_COLUMN = re.compile(r"capacit|places|posti|beds|children|guests|residents", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Ranking metrics
# ---------------------------------------------------------------------------

def jaccard(a: Sequence[Any], b: Sequence[Any]) -> float | None:
    """Set Jaccard; None when both are empty (excluded upstream), 0 if one is empty."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return None
    return len(sa & sb) / len(sa | sb)


def rbo_ext(a: Sequence[Any], b: Sequence[Any], p: float = 0.8) -> float | None:
    """Extrapolated rank-biased overlap (Webber et al. 2010, eq. 32 / uneven-list form).

    None when both lists are empty; 0 when exactly one is empty.
    """
    if not a and not b:
        return None
    if not a or not b:
        return 0.0
    short, long_ = (list(a), list(b)) if len(a) <= len(b) else (list(b), list(a))
    s, l = len(short), len(long_)
    x = _overlap_counts(short, long_)  # x[d] = |short[:min(d,s)] ∩ long[:d]|
    x_s, x_l = x[s], x[l]
    total = sum(x[d] / d * p ** d for d in range(1, l + 1))
    total += sum(x_s * (d - s) / (s * d) * p ** d for d in range(s + 1, l + 1))
    return (1 - p) / p * total + ((x_l - x_s) / l + x_s / s) * p ** l


def _overlap_counts(short: Sequence[Any], long_: Sequence[Any]) -> list[int]:
    """X_d = |short[:min(d,s)] ∩ long[:d]| for d = 0..len(long_) (lists are short, <= 10)."""
    s = len(short)
    return [len(set(short[:min(d, s)]) & set(long_[:d])) for d in range(0, len(long_) + 1)]


def tie_groups(scores: Sequence[Any], digits: int = 6) -> list[list[int]]:
    """Consecutive index groups with equal (rounded) score; None scores stay singletons."""
    groups: list[list[int]] = []
    previous = object()
    for index, score in enumerate(scores):
        key = round(float(score), digits) if isinstance(score, (int, float)) else None
        if key is not None and groups and key == previous:
            groups[-1].append(index)
        else:
            groups.append([index])
        previous = key if key is not None else object()
    return groups


def tie_permutations(ids: Sequence[Any], scores: Sequence[Any], n: int, seed: str) -> list[list[Any]]:
    """n seeded random orderings permuting only within equal-score groups."""
    groups = tie_groups(scores)
    if all(len(group) == 1 for group in groups):
        return [list(ids)] * n
    rng = random.Random(seed)
    result = []
    for _ in range(n):
        order: list[Any] = []
        for group in groups:
            members = [ids[i] for i in group]
            if len(members) > 1:
                rng.shuffle(members)
            order.extend(members)
        result.append(order)
    return result


# ---------------------------------------------------------------------------
# Filter atoms
# ---------------------------------------------------------------------------

def _num(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def worst_energy_class(values: Iterable[Any]) -> str | None:
    ranks = [ENERGY_ORDER.index(str(v).upper()) for v in values if str(v).upper() in ENERGY_ORDER]
    return ENERGY_ORDER[max(ranks)] if ranks else None


def filter_atoms(row: dict[str, Any]) -> set[str]:
    """Normalised structured-filter atoms of one run (see module docstring)."""
    atoms: set[str] = set()
    extractions = row.get("extractions") or {}
    for use_case in row.get("matched_use_cases") or []:
        atoms.add(f"D:use={_norm(use_case)}")
    location = extractions.get("location") or {}
    for place in (location.get("places") or []) if isinstance(location, dict) else []:
        if not isinstance(place, dict):
            continue
        name = _norm(place.get("city") or place.get("name") or "")
        if name:
            atoms.add(f"L:city={CITY_ALIASES.get(name, name)}")
        if place.get("radius_km") is not None:
            try:
                atoms.add(f"L:radius={float(place['radius_km']):.1f}")
            except (TypeError, ValueError):
                pass
    building = extractions.get("building") or {}
    requirements = list(building.get("requirements") or []) if isinstance(building, dict) else []
    requirements += [r for r in (row.get("requirements") or []) if isinstance(r, dict)]
    for req in requirements:
        if not isinstance(req, dict):
            continue
        column = str(req.get("target_column") or "")
        operator = str(req.get("operator") or "")
        if column == "surface_area" and operator in (">=", ">"):
            atoms.add(f"Cb:surface_area>={_num(req.get('value'))}")
        elif CAPACITY_COLUMN.search(column) and operator in (">=", ">", "="):
            atoms.add(f"Cb:capacity>={_num(req.get('value'))}")
    for typology in (building.get("typologies") or []) if isinstance(building, dict) else []:
        atoms.add(f"I:typology={_norm(typology)}")
    energy = extractions.get("energy") or {}
    for req in (energy.get("requirements") or []) if isinstance(energy, dict) else []:
        if not isinstance(req, dict) or req.get("target_column") != "energy_class":
            continue
        value = req.get("value")
        worst = worst_energy_class(value if isinstance(value, list) else [value])
        if worst and str(req.get("operator")) in ("IN", "in", "=", "<=", ">="):
            atoms.add(f"Ce:worst={worst}")
    proximity = extractions.get("proximity") or {}
    for req in (proximity.get("requirements") or []) if isinstance(proximity, dict) else []:
        if isinstance(req, dict) and req.get("target_column"):
            atoms.add(f"Cp:{_norm(req['target_column'])}")
    return atoms


def sql_consistency(row: dict[str, Any], atoms: set[str]) -> tuple[int, int]:
    """(consistent, checked) for atoms that should be visible in sql_agent_sql."""
    sql = (row.get("sql_agent_sql") or "").lower()
    if not sql:
        return 0, 0
    checked = consistent = 0
    for atom in atoms:
        dim, _, body = atom.partition(":")
        if dim == "Cb" and body.startswith("surface_area"):
            column = "surface_area"
        elif dim == "Ce":
            column = "energy_class"
        elif dim == "Cp":
            column = body
        elif dim == "L" and body.startswith("radius"):
            column = "haversine_km"
        else:
            continue
        checked += 1
        consistent += column in sql
    return consistent, checked


def atom_dim(atom: str) -> str:
    return atom.split(":", 1)[0]


def atom_prf(predicted: set[str], reference: set[str]) -> dict[str, Any]:
    if not predicted and not reference:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    tp = len(predicted & reference)
    precision = tp / len(predicted) if predicted else None
    recall = tp / len(reference) if reference else None
    if not predicted or not reference:
        return {"precision": precision, "recall": recall, "f1": 0.0}
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def majority_atoms(atom_sets: Sequence[set[str]], min_votes: int | None = None) -> set[str]:
    if not atom_sets:
        return set()
    threshold = min_votes if min_votes is not None else len(atom_sets) // 2 + 1
    counts: dict[str, int] = defaultdict(int)
    for atoms in atom_sets:
        for atom in atoms:
            counts[atom] += 1
    return {atom for atom, count in counts.items() if count >= threshold}


# ---------------------------------------------------------------------------
# Uncertainty
# ---------------------------------------------------------------------------

def cluster_bootstrap(
    values_by_cluster: dict[str, float | None], b: int = 10000, seed: int = 13, alpha: float = 0.05
) -> dict[str, Any]:
    """Percentile CI of the mean over clusters (base intents), resampling clusters."""
    values = np.array([v for v in values_by_cluster.values() if v is not None and not math.isnan(v)], dtype=float)
    if values.size == 0:
        return {"mean": None, "ci_low": None, "ci_high": None, "n": 0}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, values.size, size=(b, values.size))
    means = values[idx].mean(axis=1)
    return {
        "mean": float(values.mean()),
        "ci_low": float(np.quantile(means, alpha / 2)),
        "ci_high": float(np.quantile(means, 1 - alpha / 2)),
        "n": int(values.size),
    }


def sign_flip_test(values: Sequence[float | None]) -> dict[str, Any]:
    """Exact two-sided sign-flip (paired permutation) test of mean == 0."""
    data = [float(v) for v in values if v is not None and not math.isnan(v)]
    if not data:
        return {"p_value": None, "n": 0, "mean": None}
    observed = abs(sum(data) / len(data))
    extreme = total = 0
    for signs in itertools.product((1, -1), repeat=len(data)):
        total += 1
        stat = abs(sum(s * v for s, v in zip(signs, data)) / len(data))
        if stat >= observed - 1e-12:
            extreme += 1
    return {"p_value": extreme / total, "n": len(data), "mean": sum(data) / len(data)}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_rows(results: Path, model: str | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = []
    skipped = {"legacy_rows": 0, "other_model": 0, "stale_hash": 0}
    for line in (results / "runs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("schema_version") != 2:
            skipped["legacy_rows"] += 1
            continue
        rows.append(row)
    models = sorted({row.get("model") for row in rows})
    if model is None and len(models) > 1:
        raise SystemExit(f"Multiple models in runs.jsonl ({models}); choose one with --model.")
    if model is not None:
        skipped["other_model"] = sum(1 for row in rows if row.get("model") != model)
        rows = [row for row in rows if row.get("model") == model]
    last_hash: dict[tuple, str] = {}
    for row in rows:
        last_hash[(row["condition"], row["model"], row["unit_id"])] = row.get("input_sha256")
    latest: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        if row.get("input_sha256") != last_hash[(row["condition"], row["model"], row["unit_id"])]:
            skipped["stale_hash"] += 1
            continue
        latest[(row["condition"], row["model"], row["unit_id"], row["repeat"])] = row
    return list(latest.values()), skipped


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _ids(row: dict[str, Any], depth: int) -> list[str]:
    return [str(item["id"]) for item in (row.get("top") or [])[:depth]]


def _mean(values: Iterable[float | None]) -> float | None:
    data = [v for v in values if v is not None]
    return sum(data) / len(data) if data else None


class RankingComparer:
    """Pairwise ranking metrics with cached tie permutations per run."""

    def __init__(self, permutations: int, seed: int, p: float):
        self.permutations = permutations
        self.seed = seed
        self.p = p
        self._cache: dict[str, list[list[str]]] = {}
        self.metrics: dict[str, Callable[[list[str], list[str]], float | None]] = {
            "jaccard5": lambda a, b: jaccard(a[:5], b[:5]),
            "rbo10": lambda a, b: rbo_ext(a[:10], b[:10], self.p),
        }

    def _perms(self, row: dict[str, Any]) -> list[list[str]] | None:
        """Cached tie permutations, or None when the stored top list has no ties."""
        key = row["run_id"]
        if key not in self._cache:
            top = (row.get("top") or [])[:10]
            scores = [item.get("score") for item in top]
            has_ties = any(len(group) > 1 for group in tie_groups(scores))
            self._cache[key] = tie_permutations(
                [str(item["id"]) for item in top], scores, self.permutations, f"{self.seed}:{key}",
            ) if has_ties else None
        return self._cache[key]

    def pair(self, a: dict[str, Any], b: dict[str, Any]) -> dict[str, float | None] | None:
        """Served and tie-expected metrics for one pair; None if both lists are empty."""
        ids_a, ids_b = _ids(a, 10), _ids(b, 10)
        if not ids_a and not ids_b:
            return None
        out: dict[str, float | None] = {}
        perms_a, perms_b = self._perms(a), self._perms(b)
        for name, fn in self.metrics.items():
            out[f"{name}_served"] = fn(ids_a, ids_b)
            if perms_a is None and perms_b is None:
                out[f"{name}_tie_expected"] = out[f"{name}_served"]
            else:
                seq_a = perms_a or [ids_a] * self.permutations
                seq_b = perms_b or [ids_b] * self.permutations
                out[f"{name}_tie_expected"] = sum(
                    fn(pa, pb) for pa, pb in zip(seq_a, seq_b)
                ) / self.permutations
        return out


METRIC_KEYS = ("jaccard5_served", "jaccard5_tie_expected", "rbo10_served", "rbo10_tie_expected")


def mean_pairs(comparer: RankingComparer, left: list[dict], right: list[dict], same: bool = False) -> tuple[dict[str, float | None], int, int]:
    pairs = itertools.combinations(left, 2) if same else itertools.product(left, right)
    values: dict[str, list[float]] = defaultdict(list)
    both_empty = used = 0
    for a, b in pairs:
        result = comparer.pair(a, b)
        if result is None:
            both_empty += 1
            continue
        used += 1
        for key, value in result.items():
            values[key].append(value)
    return {key: _mean(values.get(key, [])) for key in METRIC_KEYS}, used, both_empty


def analyse(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    by_cond: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_cond[row["condition"]].append(row)
    done = {cond: [r for r in rs if r.get("status") == "completed"] for cond, rs in by_cond.items()}
    oracle_by_base: dict[str, list[dict]] = defaultdict(list)
    for row in done.get("oracle", []):
        oracle_by_base[row["base_case_id"]].append(row)
    cells: dict[tuple[str, str, int], list[dict]] = defaultdict(list)  # (cond, base, k)
    for cond in ("refined", "one_shot"):
        for row in done.get(cond, []):
            if row.get("base_case_id") is None or row.get("missing_count") is None:
                continue
            cells[(cond, row["base_case_id"], int(row["missing_count"]))].append(row)
    bases = sorted(oracle_by_base)
    ks = sorted({k for (_, _, k) in cells})
    comparer = RankingComparer(args.permutations, args.seed, args.rbo_p)

    # Ranking agreement per (condition, base, k)
    ranking: dict[str, dict[str, dict[int, dict[str, Any]]]] = defaultdict(lambda: defaultdict(dict))
    excluded_both_empty: dict[str, int] = defaultdict(int)
    for (cond, base, k), runs in sorted(cells.items()):
        oracle_runs = oracle_by_base.get(base, [])
        if not oracle_runs:
            continue
        values, used, both_empty = mean_pairs(comparer, runs, oracle_runs)
        excluded_both_empty[cond] += both_empty
        ranking[cond][base][k] = {**values, "pairs": used, "both_empty_pairs": both_empty}
    ceiling_by_base = {}
    for base, runs in oracle_by_base.items():
        values, used, both_empty = mean_pairs(comparer, runs, runs, same=True)
        excluded_both_empty["oracle_vs_oracle"] += both_empty
        ceiling_by_base[base] = {**values, "pairs": used, "both_empty_pairs": both_empty}

    # Filter atoms
    atoms_by_run = {row["run_id"]: filter_atoms(row) for row in rows if row.get("status") == "completed"}
    reference = {
        base: majority_atoms([atoms_by_run[r["run_id"]] for r in runs], args.reference_min_votes)
        for base, runs in oracle_by_base.items()
    }
    oracle_self = {}
    for base, runs in oracle_by_base.items():
        scores = []
        for i, run in enumerate(runs):
            others = [atoms_by_run[r["run_id"]] for j, r in enumerate(runs) if j != i]
            if others:
                scores.append(atom_prf(atoms_by_run[run["run_id"]], majority_atoms(others, args.reference_min_votes))["f1"])
        oracle_self[base] = _mean(scores)
    filters: dict[str, dict[str, dict[int, dict[str, Any]]]] = defaultdict(lambda: defaultdict(dict))
    for (cond, base, k), runs in sorted(cells.items()):
        if base not in reference:
            continue
        ref = reference[base]
        f1s, invented, dim_recall = [], [], defaultdict(list)
        for run in runs:
            atoms = atoms_by_run[run["run_id"]]
            f1s.append(atom_prf(atoms, ref)["f1"])
            invented.append(len(atoms - ref))
            for dim in FILTER_DIMS:
                ref_dim = {a for a in ref if atom_dim(a) == dim}
                if ref_dim:
                    dim_recall[dim].append(len(ref_dim & atoms) / len(ref_dim))
        filters[cond][base][k] = {
            "f1": _mean(f1s),
            "invented_atoms": _mean(invented),
            "dim_recall": {dim: _mean(v) for dim, v in dim_recall.items()},
        }
    sql_checks = defaultdict(lambda: [0, 0])
    for row in rows:
        if row.get("status") != "completed":
            continue
        consistent, checked = sql_consistency(row, atoms_by_run[row["run_id"]])
        sql_checks[row["condition"]][0] += consistent
        sql_checks[row["condition"]][1] += checked

    # Aggregation with uncertainty
    def per_k_stats(table: dict[str, dict[int, dict[str, Any]]], key: Callable[[dict], float | None]) -> dict[int, dict]:
        out = {}
        for k in ks:
            by_base = {base: key(table[base][k]) for base in table if k in table[base]}
            out[k] = cluster_bootstrap(by_base, args.bootstrap, args.seed)
        return out

    def delta_stats(metric_of: Callable[[str, str, int], float | None]) -> dict[str, Any]:
        per_k, intent_level = {}, {}
        paired_values = {cond: {} for cond in ("refined", "one_shot")}
        for k in ks:
            if k == 0:
                continue
            deltas = {}
            paired = {cond: {} for cond in paired_values}
            for base in bases:
                a, b = metric_of("refined", base, k), metric_of("one_shot", base, k)
                if a is not None and b is not None:
                    deltas[base] = a - b
                    paired["refined"][base] = a
                    paired["one_shot"][base] = b
            per_k[k] = {**cluster_bootstrap(deltas, args.bootstrap, args.seed),
                        "sign_flip": sign_flip_test(list(deltas.values())), "by_base": deltas,
                        "paired_by_condition": {cond: cluster_bootstrap(values, args.bootstrap, args.seed)
                                                for cond, values in paired.items()}}
            for cond in paired_values:
                paired_values[cond][k] = paired[cond]
        for base in bases:
            ds = [per_k[k]["by_base"].get(base) for k in per_k]
            intent_level[base] = _mean(ds)
        overall = {**cluster_bootstrap(intent_level, args.bootstrap, args.seed),
                   "sign_flip": sign_flip_test(list(intent_level.values())), "by_base": intent_level}
        overall["paired_by_condition"] = {
            cond: cluster_bootstrap(
                {base: _mean(values.get(base) for values in by_k.values()) for base in bases},
                args.bootstrap, args.seed,
            ) for cond, by_k in paired_values.items()
        }
        return {"per_k": per_k, "intent_level": overall}

    ranking_summary: dict[str, Any] = {}
    for metric in METRIC_KEYS:
        ranking_summary[metric] = {
            "by_condition": {
                cond: per_k_stats(ranking[cond], lambda cell, m=metric: cell.get(m)) for cond in ("refined", "one_shot")
            },
            "delta_refined_minus_one_shot": delta_stats(
                lambda cond, base, k, m=metric: ranking[cond].get(base, {}).get(k, {}).get(m)
            ),
            "oracle_noise_ceiling": cluster_bootstrap(
                {base: cell.get(metric) for base, cell in ceiling_by_base.items()}, args.bootstrap, args.seed
            ),
        }
    filter_summary = {
        "reference_rule": (f">= {args.reference_min_votes} votes" if args.reference_min_votes
                           else "strict majority of oracle repeats"),
        "reference_atoms": {base: sorted(atoms) for base, atoms in reference.items()},
        "f1": {
            "by_condition": {cond: per_k_stats(filters[cond], lambda cell: cell["f1"]) for cond in ("refined", "one_shot")},
            "delta_refined_minus_one_shot": delta_stats(
                lambda cond, base, k: filters[cond].get(base, {}).get(k, {}).get("f1")
            ),
        },
        "invented_atoms": {
            cond: {k: _mean(filters[cond][b][k]["invented_atoms"] for b in filters[cond] if k in filters[cond][b]) for k in ks}
            for cond in ("refined", "one_shot")
        },
        "dim_recall": {
            cond: {
                k: {dim: _mean(filters[cond][b][k]["dim_recall"].get(dim) for b in filters[cond] if k in filters[cond][b])
                    for dim in FILTER_DIMS}
                for k in ks
            }
            for cond in ("refined", "one_shot")
        },
        "oracle_self_agreement_f1": cluster_bootstrap(oracle_self, args.bootstrap, args.seed),
        "sql_consistency": {
            cond: {"consistent": c, "checked": n, "rate": (c / n if n else None)} for cond, (c, n) in sql_checks.items()
        },
    }

    # Operational metrics per (condition, k)
    operational: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for cond, cond_rows in by_cond.items():
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in cond_rows:
            groups["all" if row.get("missing_count") is None else str(row["missing_count"])].append(row)
        for k, group in sorted(groups.items()):
            ok = [r for r in group if r.get("status") == "completed"]
            dialog = [r for r in ok if r.get("turns") is not None]
            clar = [r.get("clarification_seconds") for r in ok if r.get("clarification_seconds") is not None]
            anal = [r.get("analysis_seconds") for r in ok if r.get("analysis_seconds") is not None]
            operational[cond][k] = {
                "runs": len(group),
                "completed": len(ok),
                "completion_rate": len(ok) / len(group) if group else None,
                "no_clarification": sum(1 for r in ok if r.get("no_clarification")),
                "with_clarification_turns": sum(1 for r in dialog if r.get("turns")),
                "mean_turns": _mean(r.get("turns") for r in dialog),
                "detection_f1": _mean((r.get("detection") or {}).get("f1") for r in ok),
                "clarification_seconds_mean": _mean(clar),
                "clarification_seconds_median": st.median(clar) if clar else None,
                "analysis_seconds_mean": _mean(anal),
                "analysis_seconds_median": st.median(anal) if anal else None,
                "empty_results": sum(1 for r in ok if not r.get("top")),
                "relaxation_applied": sum(1 for r in ok if r.get("relaxation_applied")),
                "fallback_activated": sum(1 for r in ok if r.get("fallback_activated")),
                "agent_errors_runs": sum(1 for r in ok if r.get("agent_errors")),
            }
    k0 = operational.get("refined", {}).get("0")
    unnecessary_turn_rate = (k0["with_clarification_turns"] / k0["completed"]) if k0 and k0["completed"] else None

    return {
        "settings": {
            "permutations": args.permutations, "bootstrap": args.bootstrap, "seed": args.seed,
            "rbo_p": args.rbo_p, "reference_min_votes": args.reference_min_votes,
        },
        "bases": bases,
        "ks": ks,
        "excluded_both_empty_pairs": dict(excluded_both_empty),
        "ranking": ranking_summary,
        "ranking_cells": {cond: {b: {str(k): v for k, v in cells_.items()} for b, cells_ in table.items()} for cond, table in ranking.items()},
        "oracle_noise_ceiling_by_base": ceiling_by_base,
        "filters": filter_summary,
        "operational": operational,
        "k0_unnecessary_turn_rate": unnecessary_turn_rate,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _f(value: Any, digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def per_k_table(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    metrics = {**{m: result["ranking"][m] for m in METRIC_KEYS}, "filter_f1": result["filters"]["f1"]}
    for metric, block in metrics.items():
        for k in result["ks"]:
            refined = block["by_condition"]["refined"].get(k, {})
            one_shot = block["by_condition"]["one_shot"].get(k, {})
            delta = block["delta_refined_minus_one_shot"]["per_k"].get(k, {})
            rows.append({
                "metric": metric, "k": k, "row_type": "per_k",
                "comparison_status": "not_applicable_k0" if k == 0 else ("available" if delta.get("n") else "no_paired_data"),
                "n_bases_refined": refined.get("n", 0),
                "n_bases_one_shot": one_shot.get("n", 0),
                "n_bases_paired": delta.get("n", 0),
                "refined_paired": delta.get("paired_by_condition", {}).get("refined", {}).get("mean"),
                "one_shot_paired": delta.get("paired_by_condition", {}).get("one_shot", {}).get("mean"),
                "refined": refined.get("mean"), "refined_ci_low": refined.get("ci_low"), "refined_ci_high": refined.get("ci_high"),
                "one_shot": one_shot.get("mean"), "one_shot_ci_low": one_shot.get("ci_low"), "one_shot_ci_high": one_shot.get("ci_high"),
                "delta": delta.get("mean"), "delta_ci_low": delta.get("ci_low"), "delta_ci_high": delta.get("ci_high"),
                "delta_sign_flip_p": (delta.get("sign_flip") or {}).get("p_value"),
            })
        overall = block["delta_refined_minus_one_shot"]["intent_level"]
        paired = overall["paired_by_condition"]
        rows.append({
            "metric": metric, "k": "1-5 (intent mean)", "row_type": "intent_mean_paired",
            "comparison_status": "available" if overall.get("n") else "no_paired_data",
            "n_bases_refined": paired["refined"]["n"],
            "n_bases_one_shot": paired["one_shot"]["n"],
            "n_bases_paired": overall["n"],
            "refined_paired": paired["refined"]["mean"],
            "one_shot_paired": paired["one_shot"]["mean"],
            **{f"{cond}{suffix}": paired[cond][key]
               for cond in ("refined", "one_shot")
               for suffix, key in (("", "mean"), ("_ci_low", "ci_low"), ("_ci_high", "ci_high"))},
            "delta": overall.get("mean"), "delta_ci_low": overall.get("ci_low"), "delta_ci_high": overall.get("ci_high"),
            "delta_sign_flip_p": overall["sign_flip"]["p_value"],
        })
    return rows


def print_report(result: dict[str, Any], skipped: dict[str, int]) -> None:
    print(f"bases={len(result['bases'])} ks={result['ks']} skipped={skipped} "
          f"both-empty pairs excluded={result['excluded_both_empty_pairs']}")
    print("\nPer-k agreement with oracle (mean over intents [95% cluster-bootstrap CI]); delta = refined - one_shot")
    print(f"{'metric':<22}{'k':>18} {'refined':>24} {'one_shot':>24} {'delta':>24} {'p':>6}")
    for row in per_k_table(result):
        def cell(prefix: str) -> str:
            if row.get(prefix) is None:
                return "-"
            return f"{row[prefix]:.3f} [{_f(row.get(prefix + '_ci_low'))},{_f(row.get(prefix + '_ci_high'))}]"
        print(f"{row['metric']:<22}{str(row['k']):>18} {cell('refined'):>24} {cell('one_shot'):>24} {cell('delta'):>24} {_f(row.get('delta_sign_flip_p'), 3):>6}")
    print("\nOracle-vs-oracle noise ceiling:")
    for metric in METRIC_KEYS:
        c = result["ranking"][metric]["oracle_noise_ceiling"]
        print(f"  {metric:<22} {_f(c['mean'])} [{_f(c['ci_low'])},{_f(c['ci_high'])}] n={c['n']}")
    f = result["filters"]
    sa = f["oracle_self_agreement_f1"]
    print(f"\nFilter atoms: oracle self-agreement F1 {_f(sa['mean'])} [{_f(sa['ci_low'])},{_f(sa['ci_high'])}]; "
          f"SQL consistency {json.dumps({c: _f(v['rate']) for c, v in f['sql_consistency'].items()})}")
    for cond in ("refined", "one_shot"):
        for k in result["ks"]:
            recalls = f["dim_recall"][cond].get(k, {})
            print(f"  {cond:<8} k={k} invented={_f(f['invented_atoms'][cond].get(k), 2)} recall "
                  + " ".join(f"{d}={_f(recalls.get(d), 2)}" for d in FILTER_DIMS))
    print("\nOperational (condition, k): runs ok rate no_clar turns detF1 clar_s(med) anal_s(med) empty relax fallback")
    for cond, groups in result["operational"].items():
        for k, g in groups.items():
            print(f"  {cond:<8} k={k:<3} {g['runs']:>4} {g['completed']:>4} {_f(g['completion_rate'], 2):>5} "
                  f"{g['no_clarification']:>4} {_f(g['mean_turns'], 2):>5} {_f(g['detection_f1'], 2):>5} "
                  f"{_f(g['clarification_seconds_median'], 1):>7} {_f(g['analysis_seconds_median'], 1):>7} "
                  f"{g['empty_results']:>4} {g['relaxation_applied']:>4} {g['fallback_activated']:>4}")
    print(f"\nk=0 unnecessary-turn rate (refined): {_f(result['k0_unnecessary_turn_rate'])}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare refined / one-shot / oracle runs (no LLM calls).")
    parser.add_argument("--results", type=Path, required=True, help="benchmark_cli output directory (runs.jsonl).")
    parser.add_argument("--model", default=None, help="Model to analyse when runs.jsonl contains several.")
    parser.add_argument("--output-prefix", type=Path, default=None,
                        help="Write <prefix>.json, <prefix>_per_k.csv and <prefix>_operational.csv (default: <results>/comparison).")
    parser.add_argument("--permutations", type=int, default=1000, help="Tie permutations per run (default 1000).")
    parser.add_argument("--bootstrap", type=int, default=10000, help="Cluster bootstrap resamples (default 10000).")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--rbo-p", type=float, default=0.8)
    parser.add_argument("--reference-min-votes", type=int, default=None,
                        help="Votes needed for an atom to enter O* (default: strict majority of oracle repeats).")
    args = parser.parse_args(argv)
    rows, skipped = load_rows(args.results, args.model)
    if not rows:
        raise SystemExit("No schema_version 2 rows found in runs.jsonl.")
    result = analyse(rows, args)
    print_report(result, skipped)
    prefix = args.output_prefix or (args.results / "comparison")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    result["skipped_rows"] = skipped
    Path(f"{prefix}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    table = per_k_table(result)
    with open(f"{prefix}_per_k.csv", "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]) if table else ["metric"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(table)
    with open(f"{prefix}_operational.csv", "w", encoding="utf-8", newline="") as stream:
        fields = ["condition", "k"] + list(next(iter(next(iter(result["operational"].values())).values())).keys())
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for cond, groups in result["operational"].items():
            for k, g in groups.items():
                writer.writerow({"condition": cond, "k": k, **g})
    print(f"\nWrote {prefix}.json, {prefix}_per_k.csv, {prefix}_operational.csv")


if __name__ == "__main__":
    main()
