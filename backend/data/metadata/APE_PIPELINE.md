# MURENA APE extraction and dataset pipeline

## Certificate extraction

`ape_extraction.py` is the standalone XML stage. It needs only Python project
dependencies and an input directory; it does not read `.env`, OSM, POI, OMI, or
target-city settings. It writes certificate-level `ape_raw.parquet`, one row per
successfully parsed XML, repeated intervention rows in
`ape_recommendations.parquet`, `ape_data_quality_report.json`, and a JSONL
error ledger. Source identifiers remain strings (including leading zeros),
numeric observations use nullable numeric columns, and boolean source flags are
nullable booleans. Original XML coordinates are kept in `xml_latitude` and
`xml_longitude`.

Example small-sample run:

```bash
uv run python backend/data/metadata/ape_extraction.py /path/to/xml \
  --output-dir /tmp/ape-sample --limit 25 --batch-size 10
```

Full-repository run (resumable):

```bash
uv run python backend/data/metadata/ape_extraction.py "$APE_XML_PATH" \
  --output-dir backend/data/metadata/extracted --batch-size 500
```

Files are traversed deterministically. Work is held in bounded batches and written
as durable Parquet shards; a SQLite manifest records each discovered relative path,
file status, source metadata, parsing outcome and error. A JSONL snapshot and
failure ledger are also emitted. Re-running the same source/output pair skips
completed files and retries an interrupted batch. Public Parquet files are rebuilt
atomically from shards. Failures are recorded with filename, reason, and parser
detail. Malformed or undecodable XML is not converted into a partial record.
Use the error ledger to audit such files. `--limit` always means the first N
sorted files and is intended for development sampling.

## XML findings

Representative files in the supplied `/home/mdeluca/merged` directory use the
APE2015 namespace, with address, civic number, municipality, ISTAT code, climate
zone, and GIS coordinates under `datiCalcolo/datiGenerali`. The same files put
building performance under `prestazioneGlobale/prestazioneEnergeticaGlobale`,
system and CO2 values under `prestazioneImpianti`, heated volume and `ephnd`
under `datiFabbricato`, and repeated measures under
`raccomandazioni/interventoRaccomandato`. The recommendations-level
`raccomandazioni/classificazione` is stored separately from per-intervention
`classificazioneRaggiungibile`. Cadastral string codes are retained verbatim.
In a deterministic 1,000-file sample, 827 files failed strict parsing due to
invalid bytes under the declared UTF-8 encoding; three files were empty or not
XML. The exporter first attempts strict parsing. When invalid UTF-8 is detected,
it decodes valid UTF-8 sequences unchanged and maps only invalid bytes through
Windows-1252, updates the XML declaration to UTF-8 and parses strictly. This
avoids corrupting valid UTF-8 characters while recovering the corpus's isolated
legacy bytes. It records repaired byte counts and parse provenance; no bytes are
silently ignored, and lxml recovery is diagnostic only.

## Verified full-corpus extraction

The 2026-10-16 run inventoried and attempted all 311,836 XML files. It wrote
311,586 certificate rows and 415,499 individual recommendation rows; 259,100
certificates used the mixed UTF-8/CP1252-invalid-byte normalization. There were
250 explicit failures (247 empty/non-XML inputs and 3 XML files containing an
illegal U+FFFF character), and no pending files. The raw and recommendation
schemas validated, source IDs were unique, and recommendation foreign-key
references all resolved. The output report is
`backend/data/metadata/extracted/ape_data_quality_report.json`; the SQLite
manifest and JSONL ledger account for every discovered file. APE IDs are often
blank in the source, so `source_record_id` is the stable record key.

The source profile found 297,059 certificates (95.3%) have complete unit keys
after excluding numeric zero placeholders in sheet/parcel/subaltern values;
alphanumeric codes are retained as source identifiers and zero-coded values are
not rewritten. It found 5,227 unit keys with repeated certificates and 11,559
parcels with multiple DPR 412 codes. Repeated unit keys include certificate
history, and conflicting attributes are summarized in the research profile.
Parcels remain imperfect proxies for physical buildings.

## Enrichment and application export

The legacy `create_estate_dataset.py` remains the application-facing enrichment
and export path. Its callable stages now run in this order: XML-to-application
row mapping and target-comune filtering; record validation; address geocoding;
POI/OMI enrichment; deterministic MURENA scoring; complete-key cadastral
deduplication; metaestate generation; compatible Parquet export. Workers parse
XML without loading OSM, POI, or OMI datasets; OSM geocoding and spatial
enrichment run once in the parent process. The application stage still needs
the target-comune and applicable local geospatial data. Its coordinate logic
retains XML coordinates and uses exact street/house-number OSM matches to fill
only missing or invalid values. Raw extraction remains independent. The
existing `estates.parquet` is not replaced by `ape_raw.parquet` and existing API
loaders continue to use the MURENA-compatible dataset contract.

## Migration notes and known limitations

- `ape_raw.parquet` is certificate-level source data; multiple historical APEs
  for one cadastral unit are expected. Recommendations are individual records,
  not additive estimates or observed post-renovation outcomes.
- No undocumented meanings are assigned to source codes. Existing application
  score mappings remain in the legacy export path.
- The legacy export keeps its application columns while excluding incomplete
  cadastral keys from deduplication and metaestate grouping. It creates a
  metaestate only when constituent units have the same normalized address and
  coordinates within 50 metres. Constituent IDs remain in `id_list`. Areas are
  summed; energy intensities, proximity scores, and component energy scores use
  surface-weighted means when valid weights exist, otherwise null. The modal
  energy class is marked `energy_class_is_estimate`; all reductions are recorded
  in `aggregation_methods`. Treat aggregate values as estimates, not certified
  building-level results.
- Keep the extraction output directory intact when resuming. Its SQLite manifest
  pins the source root and file metadata; a changed source snapshot is rejected.
  Generated corpus outputs are ignored by Git under
  `backend/data/metadata/extracted/`.
