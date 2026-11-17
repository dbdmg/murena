#!/usr/bin/env python3
"""Validate the v3 controlled-missingness scenarios without model calls.

Checks (independently of the generator code): counts, nesting, preserved
derived fragments, absence of capacity in derived D, capacity present in
derived Cb, unchanged oracle q*, recorded source answers, YAML consistency
and the source hash stored in generation_manifest.json.

Usage (from the repository root):
    uv run python backend/experiments/data/scenarios_v3/validate_missingness.py \
        --source backend/experiments/data/scenarios_v3/source_triplets.json \
        [--catalog backend/docs/knowledge/normativa/normativa.json]
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import yaml

DIMS = {'I', 'D', 'L', 'Cb', 'Ce', 'Cp'}
OPTIONAL = DIMS - {'I'}
CAPACITY_RE = re.compile(r'\b(\d+|four)\s+(children|guests|residents|beds)\b', re.IGNORECASE)
CB_RE = re.compile(r'I need a property with at least (\d+) sqm of gross floor area and capacity for (\d+|four) people\.')


def _words(text: str) -> list[str]:
    return re.findall(r"[\w/()'-]+", text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True, help='Original 24-case scenario_triplets.json')
    ap.add_argument('--catalog', type=Path, default=None)
    ap.add_argument('--folder', type=Path, default=Path(__file__).resolve().parent)
    a = ap.parse_args()
    folder = a.folder
    original = json.loads(a.source.read_text(encoding='utf-8'))
    entries = json.loads((folder / 'scenario_triplets.json').read_text(encoding='utf-8'))
    parsed_yaml = yaml.safe_load((folder / 'conversational_scenarios.yaml').read_text(encoding='utf-8'))
    manifest = json.loads((folder / 'generation_manifest.json').read_text(encoding='utf-8'))
    assert manifest['source_triplets_sha256'] == hashlib.sha256(a.source.read_bytes()).hexdigest(), \
        'SOURCE CHANGED; REGENERATE DATA'
    assert len(entries) == 48 and len(parsed_yaml) == 48
    assert len({s['case_id'] for s in entries}) == 48
    assert Counter(s['missing_count'] for s in entries) == Counter({k: 8 for k in range(0, 6)})
    by_id = {s['case_id']: s for s in entries}
    capacity_map = manifest['capacity_map']
    bases = sorted({s['base_case_id'] for s in entries})
    assert len(bases) == 8 and set(bases) == set(capacity_map)
    for base in bases:
        related = sorted((s for s in entries if s['base_case_id'] == base), key=lambda s: s['missing_count'])
        assert [x['missing_count'] for x in related] == [0, 1, 2, 3, 4, 5]
        original_base = next(x for x in original if x['case_id'] == base)
        expected_oracle = original_base['oracle']['query']
        source_answers = original_base['conversational']['simulated_user_answers_by_dimension']
        phrase = capacity_map[base]['phrase']
        count = capacity_map[base]['count']
        derived = related[0]['conversational']['simulated_user_answers_by_dimension']
        # Derived fragments: only D and Cb changed.
        assert set(derived) == DIMS
        for d in DIMS - {'D', 'Cb'}:
            assert derived[d] == source_answers[d], (base, d)
        assert source_answers['D'].count(phrase) == 1, (base, 'phrase must occur once in source D')
        assert phrase not in derived['D'] and not CAPACITY_RE.search(derived['D']), (base, derived['D'])
        removed = _words(source_answers['D'])
        for word in _words(phrase):
            removed.remove(word)
        assert _words(derived['D']) == removed, (base, 'D must lose exactly the capacity phrase')
        assert '  ' not in derived['D'] and ' ,' not in derived['D'] and derived['D'].endswith('.')
        cb = CB_RE.fullmatch(derived['Cb'])
        assert cb and cb.group(2) == count, (base, derived['Cb'])
        assert cb.group(1) in source_answers['Cb']
        assert not re.search(r'children|guests|residents|beds', derived['Cb'], re.IGNORECASE), 'Cb leaks D'
        assert CAPACITY_RE.search(expected_oracle), 'oracle keeps original wording'
        for level, s in enumerate(related):
            missing = set(s['missing_dimensions'])
            assert missing.issubset(OPTIONAL) and len(missing) == level
            assert set(s['present_dimensions']) == (DIMS - missing)
            if level > 1:
                assert set(related[level - 1]['missing_dimensions']).issubset(missing)
            assert s['oracle']['query'] == expected_oracle
            assert s['conversational']['simulated_user_answers_by_dimension'] == derived
            assert s['conversational']['source_answers_by_dimension'] == source_answers
            assert s['capacity_transform']['derived_D'] == derived['D']
            assert s['capacity_transform']['derived_Cb'] == derived['Cb']
            q0 = s['one_shot']['query']
            assert q0 == s['conversational']['initial_query']
            assert q0 != expected_oracle
            assert s['conversational']['expected_initial_missing'] == s['missing_dimensions']
            assert s['expectations']['expected_initial_dimension_status'] == {
                d: ('UNCONFIRMED_ABSENT' if d in missing else 'SPECIFIED') for d in DIMS}
            assert s['conversational']['expected_mapping'] == {d: 'SPECIFIED' for d in DIMS}
            for d in OPTIONAL:
                assert (derived[d] in q0) == (d not in missing), (s['case_id'], d)
            assert derived['I'] in q0, 'I must remain as an anchor'
            # Capacity is in q0 iff Cb is present (never via D).
            assert bool(CAPACITY_RE.search(q0)) is False
            assert (f'capacity for {count} people' in q0) == ('Cb' not in missing), s['case_id']
    for row in parsed_yaml:
        m = by_id[row['id']]
        assert row['initial_query'] == m['one_shot']['query'] == row['one_shot_query']
        assert row['oracle_query'] == m['oracle']['query']
        assert row['base_case_id'] == m['base_case_id']
        assert row['missing_count'] == m['missing_count'] == len(row['expected_initial_missing'])
        assert row['expected_initial_missing'] == m['missing_dimensions']
        assert row['clarifications'] == m['conversational']['simulated_user_answers_by_dimension']
    if a.catalog:
        catalog = json.loads(a.catalog.read_text(encoding='utf-8'))
        assert {e['regulatory_use_case'] for e in entries} == {x['use_case'] for x in catalog}
    print('PASS: 48 scenarios (8 at each k=0..5); capacity moved D->Cb for all 8 intents; '
          'nesting, derived fragments, oracle, YAML valid')


if __name__ == '__main__':
    main()
