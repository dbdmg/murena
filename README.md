# MURENA: Multi-Agent LLM Pipeline for Large-Scale Real Estate Management

This repository contains the implementation of MURENA, an agentic framework for intelligent real estate analysis that integrates geospatial data, Energy Performance Certifications (EPC), and Proximity evaluation through multi-agent orchestration.

## Overview

MURENA introduces a 3-phase multi-agent orchestration architecture designed to transform natural language queries into deterministic, technically validated real estate rankings:

1.  **Requirement extraction**: Specialized agents (Location, Property, Energy, Proximity, Regulatory) extract granular constraints in parallel. All internal logic and nomenclature follow a standardized English schema.
2.  **Standardized execution**: A SQL generation agent translates requirements into DuckDB queries, while a ranking agent computes objective scores based on property alignment.
3.  **Synthesis and justification**: An evaluation agent provides qualitative justifications for top-ranked properties, followed by a Broker agent that synthesizes the final response.

## Repository structure

The project is structured to ensure modularity and reproducibility:

```text
murena/
├── backend/                # FastAPI services, LLM agents, and data management
│   ├── app/                # Core application logic (FastAPI, Agents, Models)
│   ├── data/               # Datasets and metadata (SQLite, Parquet, POIs)
│   └── experiments/        # Evaluation and benchmarks reproduction scripts
├── frontend/               # React-based analytics dashboard (Vite)
├── run_app.py              # Main entry point: handles DB reset, data init, and server launch
└── run_experiments.py      # Entry point for research evaluation and benchmarks
```

## Setup and installation

### Prerequisites

- **Python 3.10+**
- **Node.js & npm** (optional, required if you want to run the React dashboard)
- **No external Database required**: The system uses **SQLite** for user management and **DuckDB** for analytics (Parquet-based).

### Environment configuration

Create a `.env` file in the `backend/` directory based on `.env.example`:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your LLM API keys (Gemini, OpenAI, etc.)
```

## Usage

### 1. Application execution
To launch the full system (backend and frontend):

```bash
python run_app.py
```

**Features of the launcher:**
- **Automatic DB Reset**: Each run clears the local SQLite database to ensure a clean, reproducible state.
- **Data Initialization**: Automatically detects if `estates.parquet` is missing and triggers the generation pipeline (XML parsing, Geocoding, POI scoring).
- **Graceful Execution**: If `npm` is missing, it will start the backend only, allowing API-level testing.

### 2. Research evaluation & Reproduction
To replicate the experimental results and benchmarks described in the paper:

```bash
# To reproduce Table 1 (Routing, Ranking, Qualitative)
python backend/experiments/reproduce_results.py --table 1

# To reproduce Table 2 (Structural SQL Comparison)
python backend/experiments/reproduce_results.py --table 2

# To generate a comprehensive Markdown report from all available logs
python run_experiments.py --type all
```

## User management

The system includes a basic authentication layer.

**Default credentials:**
- Username: `admin`
- Password: `admin`

**CLI management:**
```bash
python run_app.py --create-user
python run_app.py --delete-user
```

## Technical specifications

- **Internationalization**: Full transition to English nomenclature for all data columns and internal LLM reasoning.
- **Orchestration**: LangGraph StateGraph for complex agentic workflows.
- **Data Engine**: DuckDB for high-performance analytical queries on the consolidated `estates.parquet` dataset.
- **Database**: Ported to SQLite for a zero-dependency local setup.
- **Frontend**: React with Leaflet for geospatial visualization.
- **Scoring**: Deterministic mathematical weighting (0-100 percentile) for property ranking.

