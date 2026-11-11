---
type: Data Schema
title: 'Persistenza SQLite: User, Run, Feedback'
description: Entità ORM, relazioni e ciclo di vita delle analisi applicative.
tags:
- sqlite
- sqlalchemy
- schema
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/database/models.py
  title: 'MURENA repository: backend/app/database/models.py'
- resource: ../../../backend/app/database/connection.py
  title: 'MURENA repository: backend/app/database/connection.py'
- resource: ../../../backend/app/repositories/run_repository.py
  title: 'MURENA repository: backend/app/repositories/run_repository.py'
- resource: ../../../run_app.py
  title: 'MURENA repository: run_app.py'
---

# Persistenza SQLite: User, Run, Feedback

## Tabelle

| Tabella | Chiave | Campi significativi | Relazioni |
|---|---|---|---|
| `users` | `id` | `username` univoco, `password_hash`, `email`, `created_at` | Un utente possiede molte run |
| `runs` | `id`; `run_id` univoco | `query`, `status`, `results` JSON, `gemini_responses` JSON, `location_data`, `dataset_key`, `analysis_mode`, `results_count`, timestamp | `user_id` opzionale, uno-a-molti feedback |
| `feedback` | `id` | `run_id`, `building_id` opzionale, `agent_name` opzionale, `rating`, `helpful`, `comment`, `created_at` | riferimento a run e utente |

`runs.status` usa stati applicativi come `processing`, `completed`, `failed`; la UI conserva lo stesso identificatore di esecuzione.

## Reset di sviluppo

`run_app.py` invoca un reset della SQLite locale ad ogni avvio. È un comportamento intenzionale della demo ma **non adatto alla persistenza operativa**. Evitare dati utenti reali con questo launcher senza modificarne il ciclo di vita.

## Confini

SQLite è storage dell'applicazione; il registro di immobili è Parquet interrogato da DuckDB e non viene popolato come tabella ORM.
