---
type: Architecture
title: Backend FastAPI
description: Stratificazione di API, servizi, modelli, storage, dataset e configurazione Python.
tags:
- backend
- fastapi
- python
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/main.py
  title: 'MURENA repository: backend/app/main.py'
- resource: ../../../backend/app/api/v1/router.py
  title: 'MURENA repository: backend/app/api/v1/router.py'
- resource: ../../../backend/app/services/analysis_service.py
  title: 'MURENA repository: backend/app/services/analysis_service.py'
- resource: ../../../backend/app/core/config.py
  title: 'MURENA repository: backend/app/core/config.py'
---

# Backend FastAPI

## Entry point

`backend/app/main.py` definisce l'oggetto `FastAPI`, il `lifespan`, GZip su risposte grandi, CORS e gli handler d'errore. Include `app.api.v1.router` con prefisso `/api/v1` e pubblica `/health`.

| Livello | Percorsi principali | Ruolo |
|---|---|---|
| API | `app/api/v1/endpoints/` | Parsing, autenticazione, serializzazione HTTP/WS |
| Servizi | `app/services/analysis_service.py`, `real_estate_service.py`, `map_service.py` | Casi d'uso e adattamento dei risultati |
| Agenti | `app/services/llm/agents/` | Estrazione, SQL, ranking, valutazione, broker |
| Modelli | `app/models/`, `app/database/models.py` | Pydantic e ORM |
| Dati | `app/data/`, `backend/data/metadata/` | Loading, preparazione e metadati dataset |
| Infrastruttura | `app/core/`, `app/database/`, `app/repositories/` | Configurazione, sicurezza, connessioni, persistenza |

## Avvertenze

`AnalysisService` effettua lazy import del grafo multi-agente. Il launcher `run_app.py` avvia il backend da `backend/`, configurando l'ambiente e resettando la SQLite locale: [playbook di avvio](../operations/quickstart.md).

Consultare [API](../api/endpoints.md) per gli endpoint e [sicurezza](../operations/security.md) prima di esporre il server a reti non fidate.
