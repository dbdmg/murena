"""Static validation of the generated benchmark, no LLM calls required.

Usage:
  python validate_triplets.py --catalog /path/to/murena-demo/backend/docs/knowledge/normativa/normativa.json
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
DIMS = {'I', 'D', 'L', 'Cb', 'Ce', 'Cp'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path, required=True)
    args = parser.parse_args()
    kb = json.loads(args.catalog.read_text(encoding='utf-8'))
    records = {rec['use_case']: rec for rec in kb}
    cases = json.loads((HERE/'scenario_triplets.json').read_text(encoding='utf-8'))
    runner = yaml.safe_load((HERE/'conversational_scenarios.yaml').read_text(encoding='utf-8'))
    with (HERE/'queries_by_configuration.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(cases)==24 and len(runner)==24 and len(rows)==72
    assert len({case['case_id'] for case in cases})==len(cases)
    assert {case['regulatory_use_case'] for case in cases if case['regulatory_use_case']} == set(records)
    assert all(rec['minimum_gross_property_area_sqm'] is None for rec in records.values())
    for case, conv in zip(cases,runner):
        assert case['case_id']==conv['id']
        assert case['one_shot']['query']==case['conversational']['initial_query']==conv['initial_query']
        assert case['one_shot']['query']!=case['oracle']['query']
        assert set(case['conversational']['simulated_user_answers_by_dimension'])==DIMS
        assert set(case['expectations']['expected_initial_dimension_status'])==DIMS
        assert set(case['conversational']['expected_initial_missing']).issubset(DIMS)
        assert case['expectations']['expected_regulatory_hard_filter_requirements']==[]
        expected = [case['regulatory_use_case']] if case['regulatory_use_case'] else []
        assert case['expected_matched_use_cases']==expected
        assert case['conversational']['expected_mapping']==conv['expected_mapping']
        for conf in ('one_shot', 'conversational', 'oracle'):
            actual = [row for row in rows if row['scenario_id']==case['case_id'] and row['configuration']==conf]
            assert len(actual)==1
            assert actual[0]['query_to_submit']==(case[conf]['initial_query'] if conf=='conversational' else case[conf]['query'])
    print(f'PASS: {len(cases)} scenario triplets, {len(rows)} requests, {len(records)} source use cases')

if __name__=='__main__':
    main()
