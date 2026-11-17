#!/usr/bin/env python3
"""Construct the v3 controlled-missingness family (8 intents x k=0..5).

Derived from ``scenarios_v2/generate_missingness.py``. The only semantic change
is the *capacity split*: in the source benchmark the user capacity
("for 18 children", "with 60 beds", ...) lives inside the intended-use
fragment ``D``. When ``Cb`` was omitted but ``D`` was present, the capacity was
still in the query, so SAGE (correctly) treated ``Cb`` as partially specified
and did not ask for it (v2: 24 of 72 Cb-omitted runs). v3 moves capacity into
``Cb`` so that every omitted dimension is genuinely absent from ``q0``:

* ``D'`` = source ``D`` with the pre-registered capacity phrase removed;
* ``Cb'`` = "I need a property with at least N sqm of gross floor area and
  capacity for X people." ("people" is use-neutral, so ``Cb'`` does not leak
  ``D``).

The transform is applied right after the source answers are read, so ``q0``,
the simulated answers and the clarifications all use derived fragments. The
source answers and the transform are stored in the triplets/manifest. The
oracle ``q*`` keeps the original human-authored wording (same meaning).

No LLM, ranking pipeline, or database is invoked in this generator.

Usage (from the repository root):
    uv run python backend/experiments/data/scenarios_v3/generate_missingness.py \
        --source backend/experiments/data/scenarios/scenario_triplets.json \
        --output backend/experiments/data/scenarios_v3
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import yaml

DIMS = ('I', 'D', 'L', 'Cb', 'Ce', 'Cp')
OPTIONAL_DIMS = ('D', 'L', 'Cb', 'Ce', 'Cp')

# Same pre-registered nested omission orders as v2 (unchanged, for comparability).
ORDERS = [
    ('D', 'Cb', 'Ce', 'Cp', 'L'),
    ('Cb', 'Ce', 'Cp', 'L', 'D'),
    ('Ce', 'Cp', 'L', 'D', 'Cb'),
    ('Cp', 'L', 'D', 'Cb', 'Ce'),
    ('L', 'D', 'Cb', 'Ce', 'Cp'),
    ('D', 'Ce', 'L', 'Cp', 'Cb'),
    ('Cb', 'L', 'Ce', 'D', 'Cp'),
    ('L', 'Cp', 'Cb', 'D', 'Ce'),
]

# Pre-registered capacity phrases (verbatim substrings of the source D answers)
# and the capacity value written into Cb'.
CAPACITY: dict[str, dict[str, str]] = {
    'UC01_micro_nursery_missing_use': {'phrase': 'for 18 children', 'count': '18'},
    'UC02_nursery_missing_use': {'phrase': 'for 45 children', 'count': '45'},
    'UC03_spring_missing_use': {'phrase': 'for 14 children', 'count': '14'},
    'UC04_baby_parking_missing_use': {'phrase': 'for 15 children', 'count': '15'},
    'UC05_home_nursery_missing_use': {'phrase': 'for four children', 'count': 'four'},
    'UC06_senior_day_missing_use': {'phrase': 'for 18 guests', 'count': '18'},
    'UC07_RSA_missing_use': {'phrase': 'for 30 residents', 'count': '30'},
    'UC08_student_grant_missing_use': {'phrase': 'with 60 beds', 'count': '60'},
}

CB_SOURCE_PATTERN = re.compile(r'I need a property with at least (\d+) sqm of gross floor area\.')
CB_TEMPLATE = 'I need a property with at least {area} sqm of gross floor area and capacity for {count} people.'
CAPACITY_REGEX = re.compile(r'\b(\d+|four)\s+(children|guests|residents|beds)\b', re.IGNORECASE)


def split_capacity(case_id: str, answers: dict[str, str]) -> dict[str, str]:
    """Return derived answers with the capacity moved from D to Cb.

    Raises ValueError if the pre-registered phrase does not occur exactly once
    in ``answers['D']`` or if ``answers['Cb']`` does not have the source form.
    """
    if case_id not in CAPACITY:
        raise ValueError(f'No pre-registered capacity for {case_id}')
    phrase = CAPACITY[case_id]['phrase']
    count = CAPACITY[case_id]['count']
    source_d = answers['D']
    if source_d.count(phrase) != 1:
        raise ValueError(f'{case_id}: capacity phrase {phrase!r} must occur exactly once in D: {source_d!r}')
    if source_d.count(' ' + phrase) != 1:
        raise ValueError(f'{case_id}: capacity phrase {phrase!r} must follow a space in D')
    derived_d = source_d.replace(' ' + phrase, '', 1)
    derived_d = re.sub(r'\s+([,.;])', r'\1', derived_d)
    derived_d = re.sub(r'\s{2,}', ' ', derived_d).strip()
    if CAPACITY_REGEX.search(derived_d):
        raise ValueError(f'{case_id}: capacity still present in derived D: {derived_d!r}')
    match = CB_SOURCE_PATTERN.fullmatch(answers['Cb'])
    if not match:
        raise ValueError(f'{case_id}: unexpected Cb form: {answers["Cb"]!r}')
    derived = dict(answers)
    derived['D'] = derived_d
    derived['Cb'] = CB_TEMPLATE.format(area=match.group(1), count=count)
    return derived


def query_from_answers(answers: dict[str, str], missing: set[str]) -> str:
    """Concatenate the (derived) statements of present dimensions in DIMS order."""
    assert 'I' not in missing
    parts = [answers['I']]
    for dim in DIMS[1:]:
        if dim not in missing:
            parts.append(answers[dim])
    return ' '.join(parts)


def make(source: Path, output: Path) -> None:
    raw_bytes = source.read_bytes()
    original = json.loads(raw_bytes)
    bases = []
    for index in range(1, 9):
        prefix = f'UC{index:02d}_'
        matches = [
            row for row in original
            if row['case_id'].startswith(prefix) and row['category'] == 'missing_use'
        ]
        if len(matches) != 1:
            raise ValueError(f'Expected 1 canonical oracle for {prefix}; found {len(matches)}')
        bases.append(matches[0])
    if {b['case_id'] for b in bases} != set(CAPACITY):
        raise ValueError('CAPACITY map does not match the source base intents')

    scenarios, runner, transforms = [], [], {}
    for index, (base, order) in enumerate(zip(bases, ORDERS), 1):
        if set(order) != set(OPTIONAL_DIMS) or len(set(order)) != 5:
            raise ValueError('Invalid missingness order')
        source_answers = base['conversational']['simulated_user_answers_by_dimension']
        if set(source_answers) != set(DIMS):
            raise ValueError(f'Missing source answers: {base["case_id"]}')
        answers = split_capacity(base['case_id'], source_answers)
        transform = {
            'phrase_removed_from_D': CAPACITY[base['case_id']]['phrase'],
            'capacity_written_to_Cb': CAPACITY[base['case_id']]['count'],
            'source_D': source_answers['D'],
            'derived_D': answers['D'],
            'source_Cb': source_answers['Cb'],
            'derived_Cb': answers['Cb'],
        }
        transforms[base['case_id']] = transform
        reference_query = base['oracle']['query']
        oracle_matches = base['expected_matched_use_cases']
        expected_final = base['expectations']['expected_final_dimension_status']
        if any(expected_final[d] != 'SPECIFIED' for d in DIMS):
            raise ValueError(f'Base oracle is not fully specified: {base["case_id"]}')

        for k in range(0, 6):
            missing = list(order[:k])
            present = [d for d in DIMS if d not in missing]
            initial_query = query_from_answers(answers, set(missing))
            status = {d: ('UNCONFIRMED_ABSENT' if d in missing else 'SPECIFIED') for d in DIMS}
            case_id = f'MS{index:02d}_k{k}'
            expected_matches = {
                'one_shot': [] if 'D' in missing else oracle_matches,
                'refined': oracle_matches,
                'oracle': oracle_matches,
            }
            scenarios.append({
                'case_id': case_id,
                'base_case_id': base['case_id'],
                'category': 'controlled_missingness' if k else 'full_input_control',
                'missing_count': k,
                'missing_dimensions': missing,
                'present_dimensions': present,
                'regulatory_use_case': base['regulatory_use_case'],
                'expected_matched_use_cases_by_configuration': expected_matches,
                'legal_record': deepcopy(base['legal_record']),
                'expectations': {
                    'expected_initial_unresolved_dimensions': missing,
                    'expected_initial_dimension_status': status,
                    'expected_final_dimension_status': deepcopy(expected_final),
                    'expected_regulatory_hard_filter_requirements': [],
                    'must_not_infer_gross_area_threshold_from_regulatory_net_parameters': True,
                    'user_requested_gross_area_is_separate_from_legal_metrics': True,
                },
                'one_shot': {'query': initial_query},
                'conversational': {
                    'initial_query': initial_query,
                    'simulated_user_answers_by_dimension': deepcopy(answers),
                    'source_answers_by_dimension': deepcopy(source_answers),
                    'expected_initial_missing': missing,
                    'expected_mapping': deepcopy(expected_final),
                },
                'oracle': {'query': reference_query},
                'capacity_transform': deepcopy(transform),
            })
            runner.append({
                'id': case_id,
                'name': (
                    f'{k} omitted dimensions; intended use: {base["regulatory_use_case"]}'
                    if k else f'Full-input control (k=0); intended use: {base["regulatory_use_case"]}'
                ),
                'tags': ['edbt', 'controlled_missingness_v3', f'missing_{k}', base['case_id']],
                'base_case_id': base['case_id'],
                'missing_count': k,
                'initial_query': initial_query,
                'one_shot_query': initial_query,
                'oracle_query': reference_query,
                'expected_initial_missing': missing,
                'clarifications': deepcopy(answers),
                'expected_mapping': deepcopy(expected_final),
                'repeats': 1,
            })

    assert len(scenarios) == 48 and len(runner) == 48
    assert Counter(x['missing_count'] for x in scenarios) == Counter({k: 8 for k in range(0, 6)})
    output.mkdir(parents=True, exist_ok=True)
    (output / 'scenario_triplets.json').write_text(
        json.dumps(scenarios, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (output / 'conversational_scenarios.yaml').write_text(
        '# v3 controlled missingness (capacity moved from D to Cb); 40 k>=1 + 8 k=0 controls.\n'
        '# Use with benchmark_cli.py --condition refined|one_shot|oracle.\n'
        + yaml.safe_dump(runner, allow_unicode=True, sort_keys=False, width=105),
        encoding='utf-8',
    )
    manifest = {
        'family': 'scenarios_v3',
        'generation_method': (
            'deterministic nested masking of five optional criteria; I always present; '
            'capacity moved from D to Cb before masking'
        ),
        'source_triplets_sha256': hashlib.sha256(raw_bytes).hexdigest(),
        'original_base_cases': [x['case_id'] for x in bases],
        'dimensions': DIMS,
        'varied_dimensions': OPTIONAL_DIMS,
        'orders_by_base_case': {x['case_id']: order for x, order in zip(bases, ORDERS)},
        'capacity_map': CAPACITY,
        'cb_template': CB_TEMPLATE,
        'capacity_regex_forbidden_in_derived_D': CAPACITY_REGEX.pattern,
        'capacity_transform_by_base_case': transforms,
        'main_scenarios': 40,
        'control_scenarios': 8,
        'distribution': {str(k): 8 for k in range(0, 6)},
        'oracle_query_policy': 'source q* wording unchanged (capacity inside the use phrase; same meaning)',
        'k0_initial_query_policy': 'concatenation of all six derived fragments',
        'caveat': (
            'All omitted dimensions treated as latent desired criteria; no natural ambiguity '
            'or deliberate opt-outs in this controlled family.'
        ),
    }
    (output / 'generation_manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Generated {len(scenarios)} scenarios (40 k>=1 + 8 k=0 controls) at {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    make(args.source, args.output)
