#!/usr/bin/env python3
"""Construct 8 x 5 controlled-missingness scenarios from eight source intents.

The original MURENA query dimensions are (I, D, L, Cb, Ce, Cp).
This controlled experiment keeps I as a stable search anchor and varies the
five optional aspects D, L, Cb, Ce, Cp with nested masking.

No LLM, ranking pipeline, or database is invoked in this generator.

Usage:
    python generate_missingness.py \
        --source ../scenario_triplets.json \
        --output .
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path

import yaml

DIMS = ('I', 'D', 'L', 'Cb', 'Ce', 'Cp')
OPTIONAL_DIMS = ('D', 'L', 'Cb', 'Ce', 'Cp')

# Fixed, pre-registered omission orders; all five optional dimensions occur at
# each oracle's maximum missingness level. Prefixes are nested (k=1..5).
# The first missing dimension rotates across the eight intended-use oracles.
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


def query_from_answers(answers: dict[str, str], missing: set[str]) -> str:
    """Preserve the source's human-authored statements for present dimensions."""
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

    scenarios, runner, flat, controls = [], [], [], []
    for index, (base, order) in enumerate(zip(bases, ORDERS), 1):
        if set(order) != set(OPTIONAL_DIMS) or len(set(order)) != 5:
            raise ValueError('Invalid missingness order')
        answers = base['conversational']['simulated_user_answers_by_dimension']
        if set(answers) != set(DIMS):
            raise ValueError(f'Missing source answers: {base["case_id"]}')
        reference_query = base['oracle']['query']
        oracle_matches = base['expected_matched_use_cases']
        expected_final = base['expectations']['expected_final_dimension_status']
        if any(expected_final[d] != 'SPECIFIED' for d in DIMS):
            raise ValueError(f'Base oracle is not fully specified: {base["case_id"]}')

        controls.append({
            'case_id': f'MS{index:02d}_k0',
            'base_case_id': base['case_id'],
            'regulatory_use_case': base['regulatory_use_case'],
            'missing_count': 0,
            'missing_dimensions': [],
            'initial_query': reference_query,
            'oracle_query': reference_query,
            'expected_initial_dimension_status': {d: 'SPECIFIED' for d in DIMS},
            'note': 'Separate full-input control: source benchmark_cli requires at least one missing dimension.',
        })

        for k in range(1, 6):
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
            scenario = {
                'case_id': case_id,
                'base_case_id': base['case_id'],
                'category': 'controlled_missingness',
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
                # Keep the established conversation key for existing scripts;
                # the actual output query of this condition is the REFInED query.
                'conversational': {
                    'initial_query': initial_query,
                    'simulated_user_answers_by_dimension': deepcopy(answers),
                    'expected_initial_missing': missing,
                    'expected_mapping': deepcopy(expected_final),
                },
                'oracle': {'query': reference_query},
            }
            scenarios.append(scenario)
            runner.append({
                'id': case_id,
                'name': f'{k} omitted dimensions; intended use: {base["regulatory_use_case"]}',
                'tags': ['edbt', 'controlled_missingness', f'missing_{k}', base['case_id']],
                'initial_query': initial_query,
                'expected_initial_missing': missing,
                'clarifications': deepcopy(answers),
                'expected_mapping': deepcopy(expected_final),
                'repeats': 1,
            })
            for mode, query in (
                ('one_shot', initial_query),
                ('refined', initial_query),  # start only; generated qhat is saved at execution
                ('oracle', reference_query),
            ):
                flat.append({
                    'case_id': case_id,
                    'base_case_id': base['case_id'],
                    'missing_count': k,
                    'missing_dimensions': ','.join(missing),
                    'mode': mode,
                    'query_to_submit_or_start_with': query,
                    'oracle_query': reference_query,
                    'note': 'Start conversation, submit actual approved qhat' if mode == 'refined' else '',
                })

    assert len(scenarios) == 40 and len(runner) == 40 and len(flat) == 120
    assert len(controls) == 8
    assert Counter(x['missing_count'] for x in scenarios) == Counter({k: 8 for k in range(1,6)})
    output.mkdir(parents=True, exist_ok=True)
    (output/'scenario_triplets.json').write_text(json.dumps(scenarios, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (output/'conversational_scenarios.yaml').write_text(
        '# Use with the current conversation-only benchmark_cli.py\n'
        + yaml.safe_dump(runner, allow_unicode=True, sort_keys=False, width=105),
        encoding='utf-8',
    )
    (output/'zero_missing_controls.json').write_text(json.dumps(controls, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    with (output/'queries_by_configuration.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    manifest = {
        'generation_method': 'deterministic nested masking of five optional criteria; I always present',
        'source_triplets_sha256': hashlib.sha256(raw_bytes).hexdigest(),
        'original_base_cases': [x['case_id'] for x in bases],
        'dimensions': DIMS,
        'varied_dimensions': OPTIONAL_DIMS,
        'orders_by_base_case': {x['case_id']: order for x,order in zip(bases, ORDERS)},
        'main_scenarios': 40,
        'control_scenarios': 8,
        'main_distribution': {str(k): 8 for k in range(1,6)},
        'caveat': 'All omitted dimensions treated as latent desired criteria; no natural ambiguity or deliberate opt-outs in this controlled family.',
    }
    (output/'generation_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(f'Generated {len(scenarios)} controlled cases + {len(controls)} full-query controls at {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    make(args.source, args.output)
