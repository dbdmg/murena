#!/usr/bin/env python3
"""Validate generated controlled-missingness scenarios without model calls.

Usage: python validate_missingness.py --source ../scenario_triplets.json
Optionally: --catalog ../../../../docs/knowledge/normativa/normativa.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import yaml

DIMS = {'I','D','L','Cb','Ce','Cp'}
OPTIONAL = DIMS - {'I'}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True,help='Original 24-case scenario_triplets.json')
    ap.add_argument('--catalog',type=Path,default=None)
    ap.add_argument('--folder',type=Path,default=Path(__file__).resolve().parent)
    a=ap.parse_args()
    folder=a.folder
    original=json.loads(a.source.read_text(encoding='utf-8'))
    entries=json.loads((folder/'scenario_triplets.json').read_text(encoding='utf-8'))
    parsed_yaml=yaml.safe_load((folder/'conversational_scenarios.yaml').read_text(encoding='utf-8'))
    zero=json.loads((folder/'zero_missing_controls.json').read_text(encoding='utf-8'))
    manifest=json.loads((folder/'generation_manifest.json').read_text(encoding='utf-8'))
    with (folder/'queries_by_configuration.csv').open(encoding='utf-8-sig',newline='') as f:
        flat=list(csv.DictReader(f))
    assert manifest['source_triplets_sha256'] == hashlib.sha256(a.source.read_bytes()).hexdigest(), 'SOURCE CHANGED; REGENERATE DATA'
    assert len(entries)==40 and len(zero)==8 and len(parsed_yaml)==40 and len(flat)==120
    assert len({s['case_id'] for s in entries})==40
    assert Counter(s['missing_count'] for s in entries)==Counter({k:8 for k in range(1,6)})
    by_id={s['case_id']:s for s in entries}
    for base in set(s['base_case_id'] for s in entries):
        related=sorted((s for s in entries if s['base_case_id']==base),key=lambda s:s['missing_count'])
        assert len(related)==5
        assert [x['missing_count'] for x in related]==[1,2,3,4,5]
        original_base=next(x for x in original if x['case_id']==base)
        expected_oracle=original_base['oracle']['query']
        expected_answers=original_base['conversational']['simulated_user_answers_by_dimension']
        for level,s in enumerate(related,1):
            missing=set(s['missing_dimensions'])
            assert missing.issubset(OPTIONAL) and len(missing)==level
            assert set(s['present_dimensions'])==(DIMS-missing)
            if level>1:
                assert set(related[level-2]['missing_dimensions']).issubset(missing)
            assert s['oracle']['query']==expected_oracle
            assert s['conversational']['simulated_user_answers_by_dimension']==expected_answers
            assert s['one_shot']['query']==s['conversational']['initial_query']
            assert s['one_shot']['query']!=expected_oracle
            assert s['conversational']['expected_initial_missing']==s['missing_dimensions']
            assert s['expectations']['expected_initial_dimension_status']=={d:('UNCONFIRMED_ABSENT' if d in missing else 'SPECIFIED') for d in DIMS}
            assert s['conversational']['expected_mapping']=={d:'SPECIFIED' for d in DIMS}
            for d in OPTIONAL:
                fragment=expected_answers[d]
                assert (fragment in s['one_shot']['query'])==(d not in missing), (s['case_id'],d)
            assert expected_answers['I'] in s['one_shot']['query'], 'I must remain as an anchor'
    for control in zero:
        base=next(x for x in original if x['case_id']==control['base_case_id'])
        assert control['initial_query']==control['oracle_query']==base['oracle']['query']
        assert control['missing_count']==0 and not control['missing_dimensions']
    for row in parsed_yaml:
        m=by_id[row['id']]
        assert row['initial_query']==m['one_shot']['query']
        assert row['expected_initial_missing']==m['missing_dimensions']
        assert row['clarifications']==m['conversational']['simulated_user_answers_by_dimension']
    for row in flat:
        entry=by_id[row['case_id']]
        assert row['mode'] in {'one_shot','refined','oracle'}
        assert row['oracle_query']==entry['oracle']['query']
        assert row['query_to_submit_or_start_with']==(entry['oracle']['query'] if row['mode']=='oracle' else entry['one_shot']['query'])
    if a.catalog:
        catalog=json.loads(a.catalog.read_text(encoding='utf-8'))
        assert {e['regulatory_use_case'] for e in entries}=={x['use_case'] for x in catalog}
    print('PASS: 40 scenarios (8 at each k=1..5); 8 k=0 controls; 120 configurations; nesting, texts, sources, labels, YAML valid')


if __name__=='__main__':
    main()
