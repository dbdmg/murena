# Controlled missingness benchmark v3 — EDBT MURENA

v3 is the `scenarios_v2` family (8 fully specified reference intents × nested omission of `D, L, Cb, Ce, Cp`, `I` always present) with **one generator fix**: the user capacity is moved from the intended-use fragment `D` to the building-requirements fragment `Cb`. The omission orders, the source intents and the oracle queries are unchanged. `scenarios_v2/` and its results are kept untouched for provenance.

## What changed and why

In the source benchmark (`backend/experiments/data/scenarios/scenario_triplets.json`) the capacity is part of the `D` answer ("I intend to convert it into a micro-nursery **for 18 children**."). In v2, whenever `Cb` was omitted but `D` was present, the query still contained a capacity statement, so SAGE treated `Cb` as (partially) specified and did not flag it as missing.

Observed in `results/missingness_v2` (gpt-6-luna, 3 repeats, latest attempt per run): `Cb` was expected missing in 72 runs and not flagged in 30. **24 of these 30** (all three repeats of `MS02_k1`–`k4`, `MS07_k1`–`k3`, `MS08_k3`) are scenarios where `D` was present, i.e. the capacity leaked through `D`; 6 of the 24 (`MS02_k1`, `MS07_k1`) ended as errors because SAGE asked no question. The other 6 misses (`MS02_k5` ×2, `MS03_k5` ×3, `MS04_k5` ×1) occur at k=5, where `D` is also omitted; they are **not** explained by the leak and remain an open observation.

v3 makes every omitted dimension genuinely absent from `q0`:

| Base intent | Phrase removed from `D` | `Cb'` capacity |
| --- | --- | ---: |
| UC01 micro-nursery | `for 18 children` | 18 |
| UC02 nursery | `for 45 children` | 45 |
| UC03 spring section | `for 14 children` | 14 |
| UC04 baby parking | `for 15 children` | 15 |
| UC05 home nursery | `for four children` | four |
| UC06 senior day center | `for 18 guests` | 18 |
| UC07 RSA | `for 30 residents` | 30 |
| UC08 student residence | `with 60 beds` | 60 |

* `D'` = source `D` with the pre-registered phrase removed (it must occur exactly once; punctuation is re-joined so `D'` stays grammatical).
* `Cb'` = "I need a property with at least N sqm of gross floor area and capacity for X people." The noun "people" is use-neutral, so `Cb'` does not reveal `D`.
* The transform is applied immediately after the source answers are read: `q0`, the one-shot query, the simulated answers and the clarifications all use `D'`/`Cb'`. The source answers and the transform are stored in `scenario_triplets.json` (`conversational.source_answers_by_dimension`, `capacity_transform`) and `generation_manifest.json`.
* The oracle `q*` keeps the source wording (capacity inside the use phrase): same meaning, different surface form from the refined/one-shot inputs.
* k=0 controls are now part of the runner file. Their `q0` is the concatenation of all six derived fragments (same construction as k≥1); `expected_initial_missing` is empty.

## Files

* `conversational_scenarios.yaml` — 48 runner entries (40 k≥1 + 8 k=0). Each entry has `base_case_id`, `missing_count`, `initial_query`, `one_shot_query` (= `q0`), `oracle_query` (= `q*`), `expected_initial_missing`, `clarifications` (derived), `expected_mapping`.
* `scenario_triplets.json` — the same 48 cases with one-shot / conversational / oracle fields, source answers, capacity transform and legal record.
* `generation_manifest.json` — source hash, omission orders, `CAPACITY` map, `Cb'` template, per-intent transform.
* `generate_missingness.py` / `validate_missingness.py` — deterministic generator and static validator (no model calls). The validator checks counts, nesting, preserved derived fragments, that `D'` matches no `\b(\d+|four)\s+(children|guests|residents|beds)\b`, that `D'` loses exactly the capacity words, that `Cb'` carries the capacity, and YAML/triplet consistency.

| k | Scenarios |
| ---: | ---: |
| 0 (controls) | 8 |
| 1–5 | 8 each |
| **Total** | **48** |

## Run from the repository root

```bash
uv run python backend/experiments/data/scenarios_v3/generate_missingness.py \
  --source backend/experiments/data/scenarios/scenario_triplets.json \
  --output backend/experiments/data/scenarios_v3
uv run python backend/experiments/data/scenarios_v3/validate_missingness.py \
  --source backend/experiments/data/scenarios/scenario_triplets.json \
  --catalog backend/docs/knowledge/normativa/normativa.json
```

Three-condition run (refined ×3, one-shot ×3, oracle ×5 per base intent = 144 + 120 + 40 = 304 jobs, interleaved in a seeded order); check the plan first with `--dry-run`:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios_v3/conversational_scenarios.yaml \
  --output backend/experiments/results/missingness_v3 \
  --condition refined --condition one_shot --condition oracle \
  --repeat 3 --oracle-repeat 5 --seed 13 --concurrency 4
uv run python backend/experiments/compare_conditions.py \
  --results backend/experiments/results/missingness_v3
```

The generated files were produced and validated on 2026-11-17. No experiment, SQL query, ranker or legal check was executed to produce them.

## Caveats (unchanged from v2 unless noted)

* All masked criteria are latent desired constraints known to the simulated user; this is a controlled omission stress test, not a study of natural ambiguity.
* Simulated answers reveal the exact requirement, so refined and oracle can become semantically identical; refined-vs-oracle agreement is an agreement measure, not independently judged relevance.
* New in v3: `q0` and `q*` now differ in surface form for the capacity even at k=0 ("capacity for 18 people" vs "for 18 children"). Agreement at k=0 therefore bounds how much wording alone moves the pipeline.
* The capacity is a user preference; the dataset has no capacity column, so it can only influence the pipeline through the agents' interpretation (e.g. regulatory reasoning, evaluation text).
* `k` and the identity of omitted dimensions are not independently randomized; stratify by `k` and cluster uncertainty by base intent (8 clusters).
