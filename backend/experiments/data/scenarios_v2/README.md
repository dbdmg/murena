# Controlled missingness benchmark — EDBT MURENA

This is a **new stratified scenario family** constructed from the 8 fully specified reference intents already contained in the previous 24-case benchmark. It does not replace the old benchmark's separate ambiguity, regulatory-scope, and no-preference stress tests.

## Design

MURENA uses the existing dimensions `I, D, L, Cb, Ce, Cp`. This benchmark keeps `I` (original property type/search anchor) **specified in every input**, and systematically removes 1–5 of the other five dimensions (`D, L, Cb, Ce, Cp`). All six dimensions are present in the fully specified reference (`q*`). Each of the eight reference intents has five nested incomplete versions: the missing dimensions at level `k` are a strict subset of those at level `k+1`. Missingness order varies across the eight reference intents.

| k (omitted dimensions) | Paired scenarios |
| ---: | ---: |
| 1 | 8 |
| 2 | 8 |
| 3 | 8 |
| 4 | 8 |
| 5 | 8 |
| **Total** | **40** |

There are also **8 full-input (`k=0`) controls**, kept separately because the current `benchmark_cli.py` rejects an empty `expected_initial_missing` list.

**Why `I` is kept fixed:** this prevents `k=5` cases from degenerating into an unanchored "find something" request. It also means the current benchmark does **not** measure missing `I`; add a separate experiment if this is important.

## Files

- `scenario_triplets.json` — 40 paired scenarios, with `one_shot`, `conversational` and `oracle` fields. The **refined query is not prewritten**; it must be obtained by running the dialogue.
- `conversational_scenarios.yaml` — 40 cases in the exact source benchmark's expected input format; applies to **conversational-only** runner.
- `zero_missing_controls.json` — 8 `k=0` controls, **not accepted by the current conversation runner**.
- `queries_by_configuration.csv` — 120 rows, one-shot / refined (dialogue starting query only) / oracle.
- `generation_manifest.json` — deterministic per-use-case omission orders and source file hash.
- `generate_missingness.py` — standalone deterministic generator, for regenerating all files from original `scenario_triplets.json`.
- `validate_missingness.py` — static QA of counts, nested masks, expected states and preserved fragments; no model calls.

The reference `q*` and simulated answers are taken unchanged from `UC01` to `UC08` in the source benchmark. Every numeric area in those queries is a **synthetic user preference**, not an inferred legal whole-property area threshold. The regulatory record is copied to provide provenance, not legal validation.

## Run from this repository

The files are stored in `backend/experiments/data/scenarios_v2/`. Keep the source file `backend/experiments/data/scenarios/scenario_triplets.json`; the generator and validator use it as their source.

From the repository root, validate the generated files with:

```bash
uv run python backend/experiments/data/scenarios_v2/validate_missingness.py \
  --source backend/experiments/data/scenarios/scenario_triplets.json \
  --catalog backend/docs/knowledge/normativa/normativa.json
```

If the source triplets have changed, regenerate the files first:

```bash
uv run python backend/experiments/data/scenarios_v2/generate_missingness.py \
  --source backend/experiments/data/scenarios/scenario_triplets.json \
  --output backend/experiments/data/scenarios_v2
```

Then run the conversational condition:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios_v2/conversational_scenarios.yaml \
  --output backend/experiments/results/missingness_v2 \
  --dataset full --repeat 1 --concurrency 1
```

The CLI fixes the conversation language to English; `--language` is not a supported option. The command above is a one-repeat run, not a recommended statistical sample. To collect three repetitions, set `--repeat 3`; the full run then covers 120 scenario executions. The CLI runs the **conversational condition only**. One-shot and oracle still require separate pipeline invocations under matching model, data and settings.

The validator checks the source hash stored in `generation_manifest.json` and asks for regeneration whenever the source triplets change. The checked-in files were regenerated on 2026-11-17 and pass validation.

## What to measure

1. **Requirement reconstruction** (atomic constraint F1) after clarification, and preservation of initially specified constraints.
2. **Completion and failure rate vs. k**, plus number of clarification turns and wall-clock time (not just mean missing-dimension F1, which can reach ceiling on simple omission tasks).
3. **One-shot vs. oracle ranking impact** when the three-condition runner is available: e.g., Top-5 Jaccard and rank-sensitive RBO, recognizing these are agreement measures rather than independently judged relevance.
4. **Stratified results by k**, ideally paired within the same oracle intent. Cluster uncertainty/bootstrapping at oracle-case level (there are only 8 base intents), not as if all 40 derived cases were independent.
5. `k=0` controls to quantify unnecessary clarification, once the runner supports empty expected_missing lists.

## Important caveats

- The masked criteria are known to the scenario author but not to the system. Because **all five masked criteria are treated as latent desired constraints**, this benchmark does not distinguish voluntary omission from genuine underspecification: this is a *controlled omission stress test*, not a realistic study of natural user ambiguity.
- Simulated answers reveal the intended exact requirement when asked, so refined and oracle may become semantically identical. That is expected; it does not independently prove that the dialogue improves the ranking.
- `k=5` is a strong artificial stress condition, not representative of a realistic request. Partial dialogue and non-responding users require separate robustness scenarios.
- The number of omissions and the identity of omitted dimensions are not independently randomized. Different dimensions can have different downstream impacts; stratification by `k` supports a controlled stress test but is **not** a pure causal estimate of missingness count alone.
- This set does not replace the 24 old scenarios, which contain ambiguity, explicit non-preference and out-of-catalog tests. Those should remain as a separate robustness suite.
- No experiments, SQL queries, rankers or legal checks were executed in generating these files. The validation is static only.
