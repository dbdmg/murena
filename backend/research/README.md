# APE dataset profiling

## MURENA-CivicBench Phase 2

The structured candidate universe, use-case ontology, schema, independent oracle and pilot benchmark are implemented in [`civicbench/`](civicbench/README.md). Rebuild the candidate snapshot from Phase 1 Parquet, generate 200 scenarios and evaluate them with the versioned scoring configuration using the commands in that guide. The benchmark artifacts and validation/design reports are under `civicbench/output/v1/`. This work does not modify the application dataset or production ranking logic.

`profile_ape_dataset.py` profiles Parquet snapshots with DuckDB, optionally counts XML filenames and parses a deterministic XML sample. It writes only to the selected output directory and does not modify production data. It does not generate synthetic records or benchmark queries. `diagnose_xml_parsing.py` compares strict, byte-preserving normalization and lxml recovery on a reproducible stratified sample.

The workspace currently has `backend/data/metadata/estates.parquet`. A second, differently shaped Torino snapshot is embedded in `backend/data/data_Turin.zip`; the profiler treats these as separate datasets and extracts the ZIP member into the output directory's `.cache/` folder.

Run a quick reproducible sample:

```bash
uv run python backend/research/profile_ape_dataset.py \
  --parquet workspace=backend/data/metadata/estates.parquet \
  --parquet zip_snapshot=backend/data/data_Turin.zip::data/metadata/estates.parquet \
  --xml-root backend/data/xml --xml-sample-size 100 \
  --sample-size 2000 --seed 20261016 \
  --output-dir backend/research/ape_profile_sample
```

Run the encoding diagnostic before extraction:

```bash
uv run python backend/research/diagnose_xml_parsing.py backend/data/xml \
  --sample-size 1000 --seed 20261016 --output-dir backend/research/ape_profile
```

The parser first tries strict XML parsing. For invalid UTF-8 bytes in files declared UTF-8, it preserves valid UTF-8 sequences and maps only invalid bytes through Windows-1252, records the byte count and provenance, and then parses strictly. It does not use ignore/replacement decoding or lxml recovery for exported records. Empty/non-XML inputs remain explicit failures.

Extract a small deterministic prefix for development:

```bash
uv run python backend/data/metadata/ape_extraction.py backend/data/xml \
  --output-dir /tmp/ape-sample --limit 1000 --batch-size 250
```

Run or resume full extraction (the SQLite manifest makes completed file statuses durable; preserve the output directory):

```bash
uv run python backend/data/metadata/ape_extraction.py backend/data/xml \
  --output-dir backend/data/metadata/extracted --batch-size 500
```

Use `--retry-failed` to retry previously failed paths. Do not change the source corpus while resuming; changed file metadata is rejected to prevent mixed snapshots. Outputs include `ape_raw.parquet`, `ape_recommendations.parquet`, `ape_data_quality_report.json`, `ape_extraction_manifest.sqlite3`, `ape_extraction_manifest.jsonl`, and a failure ledger. Parquet shards are committed atomically in bounded batches.

The supplied corpus has now been fully inventoried and processed: 311,836 files
attempted, 311,586 certificates extracted, 250 explicit failures, and zero
pending paths. The failures are 247 empty/non-XML files and 3 files with an
illegal U+FFFF character. The extraction JSON report is the reconciliation
source of truth; the `.gitignore`d Parquet files and manifest remain in
`backend/data/metadata/extracted/`.

Profile all available inputs after extraction:

```bash
uv run python backend/research/profile_ape_dataset.py \
  --parquet workspace=backend/data/metadata/estates.parquet \
  --parquet zip_snapshot=backend/data/data_Turin.zip::data/metadata/estates.parquet \
  --parquet raw=backend/data/metadata/extracted/ape_raw.parquet \
  --parquet recommendations=backend/data/metadata/extracted/ape_recommendations.parquet \
  --xml-root backend/data/xml --xml-sample-size 100 \
  --seed 20261016 --output-dir backend/research/ape_profile
```

Omit `--sample-size` for full Parquet profiling. The XML count is a filesystem inventory; XML sample parsing is a diagnostic sample and is not extrapolated into a corpus-wide parse total. Raw profiling adds surface distributions, joint completeness bundles and candidate availability tables with configurable constraints (`--constraint-config JSON`). Outputs include JSON, CSV, Markdown and SVG figures. Optional fields are reported as unavailable rather than imputed. The results describe APE certificates, not the Italian building stock.

## Current input limits

- The application exports have already been filtered/deduplicated/aggregated and cannot recover certificate history, source identifiers, intervention rows or all XML fields.
- Workspace and ZIP snapshots have different schemas and row counts; do not concatenate them.
- Both snapshots are Torino-focused. No authoritative building-stock denominator was found in the repository.
- Coordinate provenance, geocoding confidence, heating-system details, envelope technical attributes and recommendation outcomes are absent from these snapshots.
- The raw extraction retains XML coordinates as source values; it does not geocode or certify their accuracy. Certificate surface and energy observations do not establish whole-building suitability. Cadastral parcels can contain multiple physical buildings and certificates can recur over time.
- APE XML records are not a random sample of the national building stock. Full extraction reconciles source files and parsed certificates, but failed/empty XML remains explicit and cannot be treated as certificates.
- Raw extraction has 311,586 certificates and 415,499 intervention rows. The complete research results include cadastral identity conflicts, completeness bundles, surface distributions, recommendation outcomes and structured candidate counts. The Torino application snapshots remain separate comparison datasets.
- The profiler's plausibility checks flag observations; they do not remove records. Thresholds such as pre-1800 construction years are review flags, not proof of invalid source data.
