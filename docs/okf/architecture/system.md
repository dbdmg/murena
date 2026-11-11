---
type: Architecture
title: Architettura full-stack
description: Responsabilità dei sottosistemi, confini dei componenti e flussi di comunicazione.
tags:
- architecture
- full-stack
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/main.py
  title: 'MURENA repository: backend/app/main.py'
- resource: ../../../backend/app/api/v1/router.py
  title: 'MURENA repository: backend/app/api/v1/router.py'
- resource: ../../../frontend/src/App.tsx
  title: 'MURENA repository: frontend/src/App.tsx'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Architettura full-stack

## Moduli principali

```text
Browser (React / TypeScript / Vite)
   |  REST /api/v1                       WebSocket /api/v1/ws/analysis/{run_id}
   v                                    ^
FastAPI -> endpoint -> AnalysisService -> ProgressManager
                           |
                           v
                  LangGraph Orchestrator
                    |       |       |
               agenti    SQL       ranking e valutazione
                    |       |       |
                    +---- DuckDB <--+---- Parquet immobili
                           |
                    risultati JSON
SQLite (SQLAlchemy): User, Run, Feedback
```

La pipeline è descritta in dettaglio nel [flusso analitico](analysis-flow.md). La parte browser è descritta in [frontend](frontend.md), la parte server in [backend](backend.md).

## Contratti e confini

- **HTTP** fornisce controlli, dati di ricerca, storico e feedback.
- **WebSocket** fornisce progressi e completamento per `run_id`.
- **DuckDB** legge Parquet o DataFrame; la query generata è ispezionabile.
- **SQLite** conserva dati applicativi (non è il data warehouse degli EPC).
- **Fornitori LLM** vengono selezionati tramite impostazioni e adapter; deployment locale e provider cloud hanno requisiti diversi.

L'architettura distingue inferenza semantica e calcolo dei risultati; non implica, da sola, che i suggerimenti testuali del modello siano garantiti corretti.
