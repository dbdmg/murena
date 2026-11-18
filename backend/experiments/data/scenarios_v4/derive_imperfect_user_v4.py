"""Derive exhaustive generalized imperfect-user scenarios (v4).

Deterministic generation, no model calls. The source is the full combinatorial
catalog ``scenarios_v3/conversational_scenarios.yaml``: 8 base intents x all 32
subsets of the five optional dimensions (D, L, Cb, Ce, Cp), i.e. 256 masks.

For every mask with k omitted dimensions, all 3**k ternary assignments are
generated, so that *every* combination of the three user behaviours is covered:

* specified (cooperative): exact requirement on the 1st turn -> SPECIFIED
* vague: domain-tailored vague response, then exact on follow-up -> SPECIFIED
  (two turns for that dimension)
* opt-out: domain-tailored refusal ("no requirement") -> NOT_REQUESTED
  (one turn, no SQL filter for that dimension)

Every balance n_spec + n_vague + n_optout = k is therefore represented, and
every possible subset of omitted dimensions is represented as well.

Total: 8 * sum(C(5, k) * 3**k for k in 0..5) = 8 * 1024 = 8,192 scenarios.

Usage:
    uv run python backend/experiments/data/scenarios_v4/derive_imperfect_user_v4.py
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
CANONICAL_DIMS = ("D", "L", "Cb", "Ce", "Cp")

# Domain-grounded vague responses tailored to the specific use case and dimension.
VAGUE_ANSWERS: dict[str, dict[str, str]] = {
    "UC01_micro_nursery_missing_use": {
        "D": "I am looking to start a small childcare facility for toddlers, something like a nursery or micro-nursery for very young children.",
        "L": "Somewhere in Turin, preferably in a family-friendly residential neighborhood, but I am still evaluating different quiet areas.",
        "Cb": "I need child-scaled spaces with separate areas for play and sleep, but I have not calculated the exact gross square meters yet.",
        "Ce": "A warm and well-insulated building with good climate control since toddlers crawl on the floor, without a specific required rating.",
        "Cp": "A quiet residential street with convenient drop-off parking for parents or close to a neighborhood public garden.",
    },
    "UC02_nursery_missing_use": {
        "D": "I intend to set up a comprehensive early childhood educational center or nursery school with multiple classrooms.",
        "L": "In Turin, ideally with easy drop-off and pickup access for working parents across the city, open to several districts.",
        "Cb": "A large dedicated facility capable of accommodating several infant and toddler sections, though the exact architectural square footage is still being finalized.",
        "Ce": "An energy-efficient property that keeps operating utilities low and indoor air healthy, without a rigid class requirement.",
        "Cp": "Preferably near public parks or green recreational spaces where children can spend outdoor time safely.",
    },
    "UC03_spring_missing_use": {
        "D": "I want to introduce an educational transition group for two-year-olds connected with an early years preschool.",
        "L": "Located in Turin, conveniently positioned relative to existing school clusters, not fixed on one single quarter.",
        "Cb": "A dedicated indoor section adequate for a small bridge cohort of children aged 24 to 36 months, without exact gross area metrics ready.",
        "Ce": "A healthy indoor thermal environment that avoids drafts and high heating costs, without a predetermined certification grade.",
        "Cp": "Well-served by municipal transport connections so families commuting without cars can easily reach it.",
    },
    "UC04_baby_parking_missing_use": {
        "D": "I plan to operate a flexible hourly childcare space or indoor playground for young children while parents run errands.",
        "L": "In Turin, in an active commercial or central district with good foot traffic, though open to suitable adjacent avenues.",
        "Cb": "A welcoming open-plan commercial unit with child-safe facilities, but the exact square meters will depend on the final layout.",
        "Ce": "A comfortable commercial space with modern climate control, without demanding a specific energy tier.",
        "Cp": "Close to public gardens, pedestrian zones, or neighborhood squares where families naturally congregate.",
    },
    "UC05_home_nursery_missing_use": {
        "D": "I want to host a small domestic childcare service or home nursery for just a few infants in a home setting.",
        "L": "In Turin, situated in a quiet residential quarter, not tied to any single neighborhood.",
        "Cb": "A comfortable domestic layout with room for cots and safe play for a small group, without strict square meter thresholds in mind.",
        "Ce": "A cozy apartment with efficient heating and double glazing to keep infants comfortable during winter.",
        "Cp": "Within walking distance of green parks or tree-lined squares for daily pram walks.",
    },
    "UC06_senior_day_missing_use": {
        "D": "I intend to establish a daytime social and recreational support center for elderly community members.",
        "L": "In Turin, in a central or well-connected neighborhood that elderly visitors and their families can reach with ease.",
        "Cb": "A step-free single-level layout with social rooms, a dining area, and accessible restrooms, but no exact total square meters yet.",
        "Ce": "A well-insulated building with balanced year-round heating and cooling to protect elderly guests from heatwaves or cold spells.",
        "Cp": "Convenient to public health clinics, local pharmacies, or medical consulting offices.",
    },
    "UC07_RSA_missing_use": {
        "D": "I am developing a full-time residential healthcare and assisted living residence for senior citizens needing nursing care.",
        "L": "In Turin or the first urban ring, preferably in a calm area buffered from heavy traffic noise.",
        "Cb": "A large multi-room complex barrier-free throughout, with rooms, infirmary, and common dining, though exact gross square meters remain to be surveyed.",
        "Ce": "High thermal insulation and dependable HVAC systems ensuring continuous medical-grade comfort, without a specific label.",
        "Cp": "Immediate proximity to major hospitals, emergency services, or healthcare infrastructure.",
    },
    "UC08_student_grant_missing_use": {
        "D": "I plan to develop affordable housing and dormitory accommodations for university students eligible under regional support schemes.",
        "L": "In Turin, within reasonable commuting distance of major university campuses (such as Politecnico or UniTo).",
        "Cb": "A sizable building with potential for individual study bedrooms and communal kitchens, with exact capacity and area under preliminary feasibility study.",
        "Ce": "A modern energy rating to guarantee low ongoing utility bills and sustainable operation for student tenants.",
        "Cp": "Direct access to high-frequency metro or bus corridors and close to daily student amenities.",
    },
}

# Domain-tailored opt-out statements per use case for all five dimensions.
OPTOUT_ANSWERS: dict[str, dict[str, str]] = {
    "UC01_micro_nursery_missing_use": {
        "D": "I have no specific intended conversion or early childhood use in mind.",
        "L": "I have no requirement on the specific city or location.",
        "Cb": "I have no specific requirement on minimum gross floor area, building layout, or infant capacity.",
        "Ce": "I have no requirement on the energy efficiency class.",
        "Cp": "I have no requirement on proximity to public transit or parks.",
    },
    "UC02_nursery_missing_use": {
        "D": "I have no specific educational or nursery use in mind.",
        "L": "I have no requirement on the specific city or location.",
        "Cb": "I have no requirement on total floor area or child capacity for the nursery building.",
        "Ce": "I have no requirement on the energy performance rating.",
        "Cp": "I have no requirement on proximity to green areas or parks.",
    },
    "UC03_spring_missing_use": {
        "D": "I have no specific spring section or educational program in mind.",
        "L": "I have no requirement on the specific city or location.",
        "Cb": "I have no requirement on gross square meters or toddler capacity for the spring section.",
        "Ce": "I have no requirement on the energy class.",
        "Cp": "I have no requirement on proximity to public transport.",
    },
    "UC04_baby_parking_missing_use": {
        "D": "I have no specific childcare or play space conversion in mind.",
        "L": "I have no requirement on the specific city or location.",
        "Cb": "I have no requirement on commercial floor area or child occupancy limits for the play space.",
        "Ce": "I have no requirement on the energy rating.",
        "Cp": "I have no requirement on proximity to public parks.",
    },
    "UC05_home_nursery_missing_use": {
        "D": "I have no specific childcare or home nursery use in mind.",
        "L": "I have no requirement on the specific city or location.",
        "Cb": "I have no requirement on dwelling floor area or capacity limits for the home nursery.",
        "Ce": "I have no requirement on the residential energy class.",
        "Cp": "I have no requirement on nearby green spaces or parks.",
    },
    "UC06_senior_day_missing_use": {
        "D": "I have no specific senior center or day care conversion in mind.",
        "L": "I have no requirement on the specific city or location.",
        "Cb": "I have no requirement on total building area, guest capacity, or structural dimensions for the day center.",
        "Ce": "I have no requirement on the energy efficiency grade.",
        "Cp": "I have no requirement on proximity to healthcare or medical clinics.",
    },
    "UC07_RSA_missing_use": {
        "D": "I have no specific residential care or nursing facility conversion in mind.",
        "L": "I have no requirement on the specific city or location.",
        "Cb": "I have no requirement on total gross floor area, resident capacity, or structural dimensions for the RSA.",
        "Ce": "I have no requirement on the energy performance class.",
        "Cp": "I have no requirement on proximity to hospitals or healthcare facilities.",
    },
    "UC08_student_grant_missing_use": {
        "D": "I have no specific student residence or academic housing program in mind.",
        "L": "I have no requirement on the specific city or location.",
        "Cb": "I have no requirement on total gross square meters or bed capacity for the student residence.",
        "Ce": "I have no requirement on the energy efficiency rating.",
        "Cp": "I have no requirement on proximity to public transportation or bus lines.",
    },
}


def canonical_order(dimensions: list[str] | set[str]) -> list[str]:
    """Sort dimensions according to canonical domain order: D, L, Cb, Ce, Cp."""
    return [d for d in CANONICAL_DIMS if d in dimensions]


def load_source_variants(path: Path) -> list[dict[str, Any]]:
    """Load scenarios from either the grouped v3 catalog or a flat YAML list."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "scenarios" in raw:
        variants: list[dict[str, Any]] = []
        for group in raw["scenarios"]:
            for variant in group.get("variants", []):
                item = json.loads(json.dumps(variant))
                item["_source_enabled"] = bool(group.get("enabled", True))
                variants.append(item)
        return variants
    if isinstance(raw, list):
        return [json.loads(json.dumps(item)) for item in raw]
    raise ValueError(f"Unsupported source format in {path}")


def derive_ternary_variants(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive all 3**k ternary assignments for each source mask."""
    derived: list[dict[str, Any]] = []

    for scenario in scenarios:
        missing = scenario.get("expected_initial_missing") or []
        source_id = scenario.get("source_case_id", "")
        if source_id not in VAGUE_ANSWERS or source_id not in OPTOUT_ANSWERS:
            raise ValueError(f"Unknown source case id: {source_id}")
        source_enabled = bool(scenario.pop("_source_enabled", True))
        k = len(missing)

        if k == 0:
            variant = json.loads(json.dumps(scenario))
            variant["id"] = f"{scenario['id']}_control"
            variant["tags"] = [*scenario.get("tags", []), "imperfect_user_v4", "control_k0"]
            variant["imperfect_user"] = {
                "profile": "control",
                "balance": "0spec_0vague_0optout",
                "source_variant_id": scenario["id"],
                "source_enabled": source_enabled,
                "specified_count": 0,
                "vague_count": 0,
                "optout_count": 0,
                "specified_dimensions": [],
                "vague_dimensions": [],
                "optout_dimensions": [],
                "expected_turns": 0,
            }
            derived.append(variant)
            continue

        for assignment in itertools.product(("spec", "vague", "optout"), repeat=k):
            spec_dims = canonical_order([d for d, s in zip(missing, assignment) if s == "spec"])
            vague_dims = canonical_order([d for d, s in zip(missing, assignment) if s == "vague"])
            optout_dims = canonical_order([d for d, s in zip(missing, assignment) if s == "optout"])

            spec_c, vague_c, opt_c = len(spec_dims), len(vague_dims), len(optout_dims)

            parts: list[str] = []
            if spec_dims and (vague_dims or optout_dims):
                parts.append("spec_" + "_".join(spec_dims))
            if vague_dims:
                parts.append("vague_" + "_".join(vague_dims))
            if optout_dims:
                parts.append("optout_" + "_".join(optout_dims))

            if not parts:
                vid = f"{scenario['id']}_all_specified"
            elif vague_c == k:
                vid = f"{scenario['id']}_all_vague"
            elif opt_c == k:
                vid = f"{scenario['id']}_all_optout"
            else:
                vid = f"{scenario['id']}_" + "_".join(parts)

            variant = json.loads(json.dumps(scenario))
            variant["id"] = vid
            variant["name"] = (
                f"{scenario['name']}; balance: {spec_c} specified, {vague_c} vague, {opt_c} opt-out"
            )
            variant["tags"] = [
                *scenario.get("tags", []),
                "imperfect_user_v4",
                f"spec_{spec_c}",
                f"vague_{vague_c}",
                f"optout_{opt_c}",
                f"balance_{spec_c}_{vague_c}_{opt_c}",
            ]

            for d, state in zip(missing, assignment):
                if state == "spec":
                    variant["clarifications"][d] = scenario["clarifications"][d]
                    variant["expected_mapping"][d] = "SPECIFIED"
                elif state == "vague":
                    variant["clarifications"][d] = [
                        VAGUE_ANSWERS[source_id][d],
                        scenario["clarifications"][d],
                    ]
                    variant["expected_mapping"][d] = "SPECIFIED"
                elif state == "optout":
                    variant["clarifications"][d] = OPTOUT_ANSWERS[source_id][d]
                    variant["expected_mapping"][d] = "NOT_REQUESTED"

            profile = (
                "all_specified" if spec_c == k else
                "all_vague" if vague_c == k else
                "all_optout" if opt_c == k else
                "mixed"
            )
            variant["imperfect_user"] = {
                "profile": profile,
                "balance": f"{spec_c}spec_{vague_c}vague_{opt_c}optout",
                "source_variant_id": scenario["id"],
                "source_enabled": source_enabled,
                "specified_count": spec_c,
                "vague_count": vague_c,
                "optout_count": opt_c,
                "specified_dimensions": spec_dims,
                "vague_dimensions": vague_dims,
                "optout_dimensions": optout_dims,
                "expected_turns": spec_c + (vague_c * 2) + opt_c,
            }
            derived.append(variant)

    return derived


def validate_ternary_variants(source: list[dict[str, Any]], derived: list[dict[str, Any]]) -> None:
    """Validate completeness, uniqueness and per-k distribution."""
    ids = [v["id"] for v in derived]
    assert len(ids) == len(set(ids)), f"Duplicate IDs detected: {len(ids)} total, {len(set(ids))} unique"
    assert len(source) == 256, f"Expected 256 source masks, got {len(source)}"
    assert len(derived) == 8192, f"Expected 8192 total scenarios, got {len(derived)}"

    by_k: dict[int, int] = {}
    for v in derived:
        k = v.get("missing_count", 0)
        by_k[k] = by_k.get(k, 0) + 1

    expected_by_k = {0: 8, 1: 120, 2: 720, 3: 2160, 4: 3240, 5: 1944}
    assert by_k == expected_by_k, f"Unexpected distribution: {by_k}"
    print(f"Validation passed: 8,192 scenarios from 256 masks, by k: {by_k}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        default=HERE.parent / "scenarios_v3" / "conversational_scenarios.yaml",
        help="Path to the full combinatorial scenario catalog YAML.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "imperfect_user_v4.yaml",
        help="Path to output YAML file.",
    )
    args = parser.parse_args()

    raw = args.source.read_bytes()
    source = load_source_variants(args.source)
    derived = derive_ternary_variants(source)
    validate_ternary_variants(source, derived)

    header = (
        "# Generated by derive_imperfect_user_v4.py; do not edit by hand.\n"
        f"# source: {args.source.name} sha256={hashlib.sha256(raw).hexdigest()}\n"
        "# V4 design: full combinatorial masks x exhaustive ternary balances "
        "(specified, vague, opt-out).\n"
    )
    content = header + yaml.safe_dump(derived, sort_keys=False, allow_unicode=True, width=120)
    args.output.write_text(content, encoding="utf-8")
    print(f"Successfully generated {len(derived)} scenarios at {args.output}")


if __name__ == "__main__":
    main()
