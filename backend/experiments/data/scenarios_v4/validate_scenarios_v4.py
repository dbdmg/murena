#!/usr/bin/env python3
"""Static validator for the v4 scenario suite.

Validates all 8,192 scenarios covering the full combinatorial catalog
(256 omission masks) crossed with exhaustive ternary balances (specified,
vague, opt-out) across k=0..5, without model calls or network access.

Usage:
    uv run python backend/experiments/data/scenarios_v4/validate_scenarios_v4.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

from backend.experiments.benchmark_cli import DIMENSIONS, load_scenarios  # noqa: E402


def validate_suite() -> None:
    yaml_path = HERE / "imperfect_user_v4.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Missing {yaml_path}")

    # Use the official benchmark loader to ensure parser compatibility
    scenarios = load_scenarios(yaml_path)
    if len(scenarios) != 8192:
        raise ValueError(f"Expected 8192 scenarios, found {len(scenarios)}")

    profiles = Counter()
    by_k = Counter()
    masks = set()

    for s in scenarios:
        info = s.get("imperfect_user")
        if not isinstance(info, dict) or "balance" not in info or "profile" not in info:
            raise ValueError(f"Scenario {s['id']} missing valid 'imperfect_user' metadata")

        masks.add(info.get("source_variant_id"))
        k = s.get("missing_count", 0)
        by_k[k] += 1
        profiles[info["profile"]] += 1

        v_dims = info.get("vague_dimensions", [])
        o_dims = info.get("optout_dimensions", [])
        s_dims = info.get("specified_dimensions", [])

        if len(v_dims) + len(o_dims) + len(s_dims) != k:
            raise ValueError(f"Scenario {s['id']} dimensions sum != k")
        if not set(v_dims + o_dims + s_dims) <= DIMENSIONS:
            raise ValueError(f"Scenario {s['id']} has unknown dimensions")

        # Vague clarification format (2-element list, non-empty, expected SPECIFIED)
        for d in v_dims:
            ans = s["clarifications"][d]
            if not isinstance(ans, list) or len(ans) != 2:
                raise ValueError(f"Vague dim {d} in {s['id']} must be a 2-element list")
            if not ans[0].strip() or not ans[1].strip():
                raise ValueError(f"Vague dim {d} in {s['id']} contains empty string")
            if s["expected_mapping"][d] != "SPECIFIED":
                raise ValueError(f"Vague dim {d} in {s['id']} expected mapping must be SPECIFIED")

        # Opt-out clarification format (string, non-empty, expected NOT_REQUESTED)
        for d in o_dims:
            ans = s["clarifications"][d]
            if not isinstance(ans, str) or not ans.strip():
                raise ValueError(f"Optout dim {d} in {s['id']} must be a non-empty string")
            if s["expected_mapping"][d] != "NOT_REQUESTED":
                raise ValueError(f"Optout dim {d} in {s['id']} expected mapping must be NOT_REQUESTED")

        # Specified clarification format (string, non-empty, expected SPECIFIED)
        for d in s_dims:
            ans = s["clarifications"][d]
            if not isinstance(ans, str) or not ans.strip():
                raise ValueError(f"Specified dim {d} in {s['id']} must be a non-empty string")
            if s["expected_mapping"][d] != "SPECIFIED":
                raise ValueError(f"Specified dim {d} in {s['id']} expected mapping must be SPECIFIED")

    expected_by_k = {0: 8, 1: 120, 2: 720, 3: 2160, 4: 3240, 5: 1944}
    if dict(by_k) != expected_by_k:
        raise ValueError(f"Distribution mismatch: {dict(by_k)} vs {expected_by_k}")
    if len(masks) != 256:
        raise ValueError(f"Expected 256 distinct source masks, found {len(masks)}")

    print(f"Validation successful: all 8,192 scenarios verified in {yaml_path.name}")
    print("Scenarios by k level:", dict(sorted(by_k.items())))
    print("Scenarios by profile:", dict(profiles))
    print("Distinct source masks:", len(masks))


if __name__ == "__main__":
    validate_suite()
