# MURENA: Multi-Agent LLM Pipeline for Large-Scale Real Estate Management

This repository contains the implementation of MURENA, an agentic framework for intelligent real estate analysis that integrates geospatial data, Energy Performance Certifications (EPC), and Point-of-Interest (POI) evaluation through multi-agent orchestration.

---
*Anonymized for blind review - ECML PKDD 2026*
---

## Overview

MURENA introduces a 3-phase multi-agent orchestration architecture designed to transform natural language queries into deterministic, technically validated real estate rankings:

1.  **Requirement extraction**: Specialized agents (Location, Property, Energy, Proximity, Regulatory) extract granular constraints in parallel.
2.  **Standardized execution**: A SQL generation agent translates requirements into DuckDB queries, while a ranking agent computes objective scores based on property alignment.
3.  **Synthesis and justification**: An evaluation agent provides qualitative justifications for top-ranked properties, followed by a Broker agent that synthesizes the final response.

## Repository structure

The project is structured to ensure modularity and reproducibility:

```text
murena/
├── backend/                # FastAPI services, LLM agents, and data management
│   ├── run_app.py          # main entry point for the integrated application
│   ├── run_experiments.py  # entry point for research evaluation and benchmarks
│   └── tests/              # experimental benchmarks and synthetic evaluation suite
├── frontend/               # React-based analytics dashboard
```

## Setup and installation

### Prerequisites

- Python 3.10+
- Node.js & npm (for the frontend dashboard)
- LLM API access (Gemini, OpenAI, or local via vLLM/Ollama)

### Environment configuration

Create a `.env` file in the `backend/` directory based on `.env.example`:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys and configuration
```

## Usage

### 1. Application execution
To launch the full system (backend and frontend):

```bash
python backend/run_app.py
```

This script automatically verifies the availability of datasets. If missing, it executes the generation pipeline to build the analytical Parquet files from source data before starting the FastAPI server (port 8000) and the Vite development server.

### 2. Research evaluation
To replicate the experimental results and benchmarks described in the paper:

```bash
python backend/run_experiments.py --type all
```

Similar to the main application, this script ensures all database dependencies are initialized before running the benchmarks.

The evaluation suite computes metrics for:
- **Agent recall**: Accuracy of specialized agent activation.
- **Ranking stability**: Intersection over Union (IoU) across varied query complexities.
- **Inference latency**: Performance overhead of the multi-agent pipeline.

## User management

The system includes a basic authentication layer for history tracking.

**Default credentials:**
- Username: `admin`
- Password: `admin123`

**CLI management:**
```bash
python backend/run_app.py --create-user
python backend/run_app.py --delete-user
```

## Technical specifications

- **Orchestration**: LangGraph StateGraph for complex agentic workflows.
- **Data engine**: DuckDB for high-performance analytical queries on Parquet datasets.
- **Frontend**: React with Leaflet for geospatial visualization.
- **Scoring**: Deterministic mathematical weighting for property ranking.
