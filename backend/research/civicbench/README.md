# MURENA-CivicBench Phase 2

This research-only package creates a unit-level candidate snapshot and a structured, reproducible benchmark. It does not modify `backend/data/metadata/estates.parquet`, production ranking/scoring, the raw APE extraction, or the recommendation export. It generates neither buildings nor natural-language requests and uses no LLM.

## Observed fields and limits

Phase 1 provides `ape_raw.parquet` (311,586 certificates, 71 columns) and `ape_recommendations.parquet` (415,499 intervention rows, 11 columns) in `backend/data/metadata/extracted/`. The candidate snapshot uses stable `source_record_id` and the four source strings `cadastral_municipality`, `cadastral_sheet`, `cadastral_parcel`, `cadastral_subaltern`. Available decision attributes include heated/cooled usable surface, construction year, source DPR 412 code, attestation object code, energy class, EPgl,nren/EPgl,ren, CO2, energy needs, heating/cooling service flags, climate zone, municipality/ISTAT code, and original XML coordinates. Coded values remain unchanged.

The values describe certificates and generally individual units. Neither a complete cadastral key nor parcel establishes one physical building. APE data do not establish ownership, vacancy, structural safety, accessibility, permits, costs, service demand, capacity or real-world suitability for any public service. Recommendation outcomes are potentials reported by certificates, not observed post-renovation results.

## Rebuild the versioned candidate universe

Run from the repository root:

```bash
uv run python -m backend.research.civicbench.cli build-candidates \
  --raw backend/data/metadata/extracted/ape_raw.parquet \
  --output backend/research/civicbench/output/v1/candidate_universe.parquet
```

The selector groups only complete, nonzero four-part cadastral unit keys. It preserves leading zeros and alphanumeric codes, excludes numeric zero placeholders, and flags units with nonnumeric sheet/parcel/subaltern components. For the fixed snapshot date 2026-10-19, it considers certificates with `issue_date <= snapshot_date` and `expiration_date >= snapshot_date`, selects the latest issue date, and breaks equal-date ties by ascending `source_record_id`. This is a reproducible date-based current-certificate rule, not independent legal validation. Every selected candidate retains all historical source IDs in `historical_source_record_ids`; all source certificate records remain in `ape_raw.parquet`. Incomplete identities and units without a certificate meeting the as-of date rule are reported and are not merged or assigned invented IDs.

## Generate, validate and evaluate

Create a small pilot first:

```bash
uv run python -m backend.research.civicbench.cli generate \
  --count 20 --seed 20261019 \
  --output backend/research/civicbench/output/v1/pilot20/benchmark_scenarios.jsonl
uv run python -m backend.research.civicbench.cli evaluate \
  --scenarios backend/research/civicbench/output/v1/pilot20/benchmark_scenarios.jsonl \
  --output-dir backend/research/civicbench/output/v1/pilot20
```

Run the deterministic unit and oracle tests:

```bash
uv run python -m backend.research.civicbench.test_civicbench
```

After validation, generate and evaluate the 200-scenario pilot:

```bash
uv run python -m backend.research.civicbench.cli generate \
  --count 200 --seed 20261019 \
  --output backend/research/civicbench/output/v1/benchmark_scenarios.jsonl
uv run python -m backend.research.civicbench.cli evaluate \
  --scenarios backend/research/civicbench/output/v1/benchmark_scenarios.jsonl \
  --output-dir backend/research/civicbench/output/v1 \
  --scoring-config backend/research/civicbench/oracle_config.json
```

The generator uses 50% fixed experimental constraint sampling (A) and 50% empirical quantile/difficulty sampling (B), balanced approximately across eight use cases. It selects constraints and preferences without first selecting a candidate. A uses explicitly experimental thresholds and observed category vocabularies; B uses candidate-wide quantiles and reports candidates within 1% of the fixed normalization span around numerical hard-constraint boundaries. Thresholds are not regulatory requirements. Generation metadata records seed, strategy, constraint/preferences counts, and retries for duplicate scenario semantics.

## Scenario and oracle semantics

`scenario_schema.json` documents the machine-readable format; `core.validate_scenario()` enforces the matching allowlists and operator/value types. Scenario definitions cannot contain SQL or executable expressions. Hard constraints use three-valued evaluation: confirmed eligible, confirmed ineligible, or unknown when evidence is missing. The benchmark keeps unknowns distinct and only ranks confirmed eligible candidates. Missing preference values yield a null aggregate score; declared weights are not renormalized around missing criteria.

Criterion scores use clipped min-max normalization with fixed, versioned bounds in `oracle_config.json`, independent of each filtered candidate set. `oracle-v1.1` fixes numerical bounds at the candidate universe's 1st and 99th percentiles; new bounds require a new scoring configuration version. Energy class is ordered G–A4 using a fixed explicit scale. Weights must be positive and sum to one. Missing preference values yield a null aggregate rather than silently changing weights. Attributes with no observed values in the candidate snapshot are excluded from generated preferences (cooling energy need is entirely missing). Ties break by stable candidate ID. Ground truth contains one row per scenario-candidate, with eligibility, reasons, criterion scores, aggregate score, Pareto flag and rank. It is written incrementally through a temporary Parquet file and atomically committed when complete. A successful rerun deterministically replaces outputs rather than appending duplicates.

## Outputs

`output/v1/` contains the candidate snapshot and manifest, scenario JSONL and generation report, ground-truth Parquet, per-scenario summaries, a checksum-based run manifest, parcel-grouped candidate and source-certificate split maps, and scenario split manifest. Reports are generated after the pilot evaluation. The original application dataset is not part of this output and its schema is unchanged.

Candidate partitions group every unit on the same municipality+sheet+parcel, which is more conservative than unit-only grouping, while the candidate snapshot retains all linked certificate IDs. `certificate_split_map.parquet` assigns every source certificate a split status; incomplete records without a parcel group are marked ambiguous/excluded. Separate deterministic geographic holdout assignment is supplied. Scenario splits alone are not leakage protection; use candidate partitions/geographic holdout for model evaluation and keep test results isolated from prompt tuning. The local reproducibility pack includes all scenario labels and ground truth, including test assignments, so it is not a hidden test release; withhold test scenarios and labels in any external evaluation service.

All numeric scoring bounds and difficulty bands are experimental benchmark semantics, not regulatory or engineering thresholds. These tasks evaluate constraint satisfaction and ranking on observed APE attributes only; they do not establish a building's legal, structural, regulatory or functional suitability for public-interest reuse.
