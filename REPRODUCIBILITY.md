# Reproducibility Guide

This document provides detailed instructions to reproduce the experiments and results presented in the paper.

## 1. Environment Setup

### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend, optional for experiments)
- Docker (optional, for deployment)

### Backend Installation
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   Copy `.env.example` to `.env` and fill in the necessary API keys.
   For reproduction, ensure `OPENAI_API_KEY` or `INSTITUTIONAL_LLM_API_KEY` is set.

## 2. Data Preparation

The experiments rely on several datasets (Parquet and GeoJSON).
1. Ensure `backend/data` contains the necessary files.
2. If datasets are missing, run the following scripts to generate them from raw sources (requires source data):
   ```bash
   python -m backend.data.metadata.create_immobili_dataset
   python -m backend.data.metadata.create_ape_dataset
   ```

## 3. Running Experiments

The synthetic test suite evaluates the multi-agent framework against various baselines and configurations.

### Standard Benchmark
To run the full benchmark suite for all supported models:
```bash
cd synthetic_test_suite
python run_sampled_experiment.py
```

### Analysis and Reporting
If results already exist in `synthetic_test_suite/results`, you can run the analysis only:
```bash
python run_sampled_experiment.py --only-analysis
```
The final report will be generated at `synthetic_test_suite/results/report.md`.

### Agent Recall Analysis
To evaluate the precision and recall of agent activation:
```bash
python baseline_agent_recall.py
```

## 4. Evaluation Metrics

The framework is evaluated using:
- **Architectural Fidelity:** Precision/Recall of agent activation compared to ground truth.
- **Ranking Stability (IoU):** Consistency of ranking across multiple runs (Intra-model IoU).
- **Ablation Studies:** Impact of disabling specific agents (Location, APE, POI, etc.) on the final ranking.
- **Performance:** Average latency and throughput of the multi-agent pipeline.

## 5. Anonymization Note

This repository has been anonymized for double-blind review. Institutional API endpoints and personal identifiers have been replaced with generic placeholders.
