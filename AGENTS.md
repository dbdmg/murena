# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project overview

MURENA is a multi-agent LLM pipeline for real estate analysis: natural language queries are turned into validated, ranked property lists using geospatial data, Energy Performance Certifications (EPC), and proximity scoring. Python 3.12 backend (FastAPI + LangGraph), React frontend.

The system is described in the ECML 2026 paper in `paper/` (`Murena_MEF_Immobili_paper_ECML_2026.pdf`) — the authoritative reference for the architecture, scoring formulas, dataset construction (~90k Italian EPCs aggregated into cadastral meta-buildings), and the evaluation protocol that `run_experiments.py` / `backend/experiments/reproduce_results.py` reproduce (Tables 1–2). Key design principles from the paper: the LLM only does semantic orchestration (intent decomposition), while filtering and scoring are deterministic (SQL + math), and the SQL agent follows a strict zero-addition policy (only uses parameters extracted by the technical agents, never latent intent from the raw query).

## Setup and commands

Dependencies are managed with `uv` (see `uv.lock`, `.python-version`):

```bash
uv sync                                  # install backend dependencies
cp backend/.env.example backend/.env     # then fill in LLM API keys (OPENAI_API_KEY, GEMINI_API_KEY, ...)
```

A `backend/.env` file is mandatory — both launchers exit immediately without it.

```bash
python run_app.py                  # full stack: backend (uvicorn, port 8002 default) + frontend (Vite, port 5173)
python run_app.py --backend-only   # skip frontend
python run_app.py --skip-init      # skip dataset initialization check
python run_app.py --create-user    # interactive user creation (default credentials: admin/admin)
```

Important launcher behavior (`run_app.py`):
- **Deletes the SQLite users DB on every launch** (intentional reset for reproducibility).
- If `backend/data/metadata/estates.parquet` is missing, it auto-runs the data generation pipeline (`backend/data/metadata/create_estate_dataset.py`, `pois_download.py`). That pipeline needs raw APE XML sources that are **not in the repo** — for local development generate a synthetic dataset instead: `uv run python backend/data/metadata/create_demo_dataset.py` (1500 fake Turin buildings, schema-complete).
- Backend commands run with `cwd=backend/` and `PYTHONPATH=backend`; the FastAPI app is `app.main:app`.

Frontend (in `frontend/`):

```bash
npm run dev      # Vite dev server
npm run build    # tsc -b && vite build
npm run lint     # eslint
```

Experiments / benchmarks (there is no pytest unit-test suite; `backend/tests/` is the experiment harness):

```bash
python run_experiments.py --type sampled --limit 20    # runs backend/tests/test_suite.py
python run_experiments.py --type all                   # full run + Markdown report
python backend/experiments/reproduce_results.py --table 1   # paper Table 1 (routing, ranking, qualitative)
python backend/experiments/reproduce_results.py --table 2   # paper Table 2 (structural SQL comparison)
```

Model selection for experiments: `--with-qwen`, `--with-gemma`, `--all-models` (reference model always included).

## Architecture

### Backend (`backend/app/`)

FastAPI app (`app/main.py`) with routes under `app/api/v1/endpoints/` (auth, analysis, buildings, energy, feedback, map, prompts, websockets — websockets stream analysis progress to the frontend). Configuration is pydantic-settings loaded from `backend/.env` (`app/core/config.py`); shared column-name constants live in `app/core/constants.py`.

Two storage engines, no external DB:
- **DuckDB** queries the consolidated `backend/data/metadata/estates.parquet` dataset (all analytics).
- **SQLite** (SQLAlchemy) only for users/auth; wiped at each `run_app.py` launch.

### Multi-agent pipeline (`backend/app/services/llm/agents/`)

The core of the system. `graph_agent.py` orchestrates a LangGraph `StateGraph` in three phases:

1. **Requirement extraction** — specialized agents run in parallel: `location_agent`, `building_agent`, `energy_agent`, `proximity_agent`, `regulatory_agent`. Each extracts granular constraints from the user query.
2. **Execution** — `sql_agent` translates requirements into DuckDB SQL (validated with sqlglot); `ranking_agent` computes deterministic 0–100 percentile scores (`app/services/analysis/ranking.py`); `relaxation_agent` proposes SQL constraint relaxations when a query returns no results.
3. **Synthesis** — `evaluation_agent` writes qualitative justifications for the top-ranked properties; `broker_agent` composes the final user-facing answer.

Conventions:
- Every agent extends `BaseAgent` (`base.py`) and returns typed Pydantic models defined in `schema.py`.
- **All prompts live in `prompt_config.md`** (sections `## <agent>.system` / `## <agent>.user`), loaded at startup by `prompt_loader.py`. To change agent behavior, edit that file — not Python strings.
- LLM clients are created via `langchain_client.py` factory; model selected by env `LLM_MODEL`.
- All internal nomenclature, data columns, and LLM reasoning use English.

### Frontend (`frontend/src/`)

React 19 + TypeScript + Vite, Tailwind CSS 4, TanStack Query for API state, react-leaflet (+ supercluster) for the map view, Recharts for analytics. Talks to the backend at `/api/v1` and via websockets for live analysis progress.
