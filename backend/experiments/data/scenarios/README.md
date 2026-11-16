# MURENA EDBT: paired use cases (one-shot / conversational / oracle)

Generated from `murena-demo(4).zip` and the `backend/docs/knowledge/normativa/normativa.json` therein.

## Contents

- `scenario_triplets.json`: **24 paired experimental cases** (8 legal use cases × 2, plus 8 robustness/negative cases). Each has the exact same underlying target intent with `one_shot`, `conversational` and `oracle` representations; expected regulatory and state outcomes; and source metadata from the repository.
- `conversational_scenarios.yaml`: directly consumable by the repository's existing `backend/experiments/benchmark_cli.py`. It supplies the initial query, expected unresolved dimensions, all six simulated clarification answers, and expected final status mapping. It does **not** execute one-shot or oracle: those need a separate invocation/harness.
- `queries_by_configuration.csv`: 72 flat rows (24 cases × 3 modes). For conversational mode, `query_to_submit` is the initial query, **not** the final rewritten query: after running SAGE, submit its actual `reviewed_query` downstream.
- `catalog_snapshot_sha256.txt`: source-catalog checksum, to detect source changes.

## Evaluation protocol

For every case, execute (i) `one_shot.query`, (ii) the real SAGE clarification dialogue starting from `conversational.initial_query` and using the simulated answers (save **actual** `refined_query` and `reviewed_query`), and (iii) `oracle.query`, with **the same** model, dataset, agent configuration, and settings. Do not substitute `oracle.query` for SAGE's generated query: that would leak ground truth.

Evaluate: (a) initial unresolved-dimension detection; (b) final dimension status; (c) atomic constraint precision/recall/F1 and constraint preservation, comparing to oracle facts; (d) `matched_use_cases` classification; (e) absence of invalid regulatory gross-area SQL predicates; (f) candidate-set/top-5 Jaccard against oracle if database execution succeeds; and (g) turns and elapsed times. If ranking results are empty, report this fact and define handling explicitly instead of treating two empty results as perfect agreement.

**Important causal limitation:** compared with one-shot, the conversational version receives *additional user information*. The A/B difference measures the value of **interactive elicitation**; it does not, by itself, isolate the benefit of natural-language dialogue versus a static form that collects the same answers.

## Legal scope and validation

Source data contain eight record labels, not 46. All eight have `minimum_gross_property_area_sqm = null` and `gross_filter_parameter.status = not_verified`; therefore none licenses an automatically inferred whole-property gross-area threshold. All gross area numbers in scenario text are **deliberately explicit preferences of the hypothetical user**. The Regulatory Agent's expected `requirements` list is empty, while a relevant exact `matched_use_cases` label can still be returned. Per-mode expected `matched_use_cases` are stored in `expected_matched_use_cases_by_configuration`; a missing D cannot be expected to produce its oracle-only label.

Several records carry important applicability qualifications: `Nursery` refers to design guidance, not an unconditional gross-area statutory minimum; `University Student Residence` uses a **specific CDP/PNRR grant**, not a general student-housing law; and several 0–3 services include an unresolved 2025 regulatory transition. The `use_case` labels/values are taken **from the supplied repository**, not independently re-verified against official acts in this task. Do not present ranking candidates as legally authorized conversions.

The case `UC23_private_student_no_grant` expects semantic match to a catalog record but **no** grant-specific threshold applicability. This distinguishes *use-case matching* from *normative applicability*. `UC22_cohousing_out_of_catalog` and `UC24_no_intended_use` must not match any catalog use case.

## Reproducibility / running

Place `conversational_scenarios.yaml` in the backend experiments folder and run the existing benchmark command with your configured `.env`, model and dataset, for example:

```bash
cd murena-demo
python backend/experiments/benchmark_cli.py --help
```

Check CLI arguments using `--help` before launching: the runner performs network/model calls and requires a configured model and dataset. The source snapshot's runner **only runs conversational mode** and requires nonempty `expected_initial_missing`. You must call the same `analysis_service.run_analysis` for one-shot and oracle, and set an explicit common `analysis_mode`, limits, model, seed/repeats and dataset. Save each run's resulting building IDs and structured agent outputs.

## Suggested demo walkthrough

- **Guided:** `UC20_senior_care_disambiguation`. Start with an ambiguous elder-care purpose, disambiguate **RSA vs senior day center**, specify capacity and personal gross-area requirement, then show the audit trail and ranked results.
- **Open-ended:** `UC19_student_grant_multiturn` (or `UC21_childcare_disambiguation` if student-grant context is not applicable). Let the audience choose between valid user intents and illustrate how the structured query, agent matches, and resulting candidates change.

## Static validation performed

- Parses `conversational_scenarios.yaml` with `benchmark_cli.load_scenarios` from this repository.
- All 24 triplets have nonidentical one-shot and oracle queries, all six simulated answer dimensions and legal matching metadata.
- All eight current catalog use cases are covered.
- **No LLM, geocoder or data-processing pipeline was executed.** This is a scenario dataset, not a claim of experimental results.
