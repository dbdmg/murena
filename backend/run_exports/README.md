# Run Exports

This directory contains JSON exports of query runs for debugging and LLM analysis.

## Format

Each file is named: `YYYYMMDD_HHMMSS_<run_id>.json`

## Contents

- `run_id`: Unique identifier
- `query`: Original user query
- `status`: Run status
- `metrics`: Computed metrics (APE availability, energy class distribution, etc.)
- `agent_outputs`: All agent responses
- `results`: Full building results

## Retention

Only the last 10 exports are kept automatically.

## Disable

Set `ENABLE_RUN_JSON_EXPORT=false` in `.env` or config to disable for production.
