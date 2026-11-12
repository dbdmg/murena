---
type: API Contract
title: Contratti della ricerca e degli edifici
description: Strutture di richiesta e risposta Pydantic e corrispondenza con la UI.
tags:
- api
- dto
- pydantic
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/models/requests.py
  title: 'MURENA repository: backend/app/models/requests.py'
- resource: ../../../backend/app/models/responses.py
  title: 'MURENA repository: backend/app/models/responses.py'
- resource: ../../../frontend/src/api/types.ts
  title: 'MURENA repository: frontend/src/api/types.ts'
- resource: ../../../frontend/src/api/endpoints/analysis.ts
  title: 'MURENA repository: frontend/src/api/endpoints/analysis.ts'
---

# Contratti della ricerca e degli edifici

## Avvio analisi

`POST /api/v1/analysis` riceve un `AnalysisRequest`.

| Campo | Tipo | Default o vincolo |
|---|---|---|
| `query` | `str` | Obbligatorio, linguaggio naturale |
| `dataset_key` | `str` | `full` (`full`, `meta`, `ape` sono valori descritti) |
| `map_limit` | `int` | 1000, tra 1 e 5000 |
| `llm_limit` | `int` | 10, tra 1 e 10 |
| `analysis_mode` | `str` | `agent` (`classic` ammesso) |
| `output_language` | `str` | `en` (`it` disponibile) |
| `use_relaxation` | `bool` | `true` |
| `model_type` | `str|null` | `null` |
| `clarification_session_id` | `str|null` | Sessione esistente quando si risponde a una domanda SAGE |
| `clarification_response` | `str|null` | Risposta alla domanda in sospeso |

Restituisce `AnalysisResponse`: `run_id`, `status`, `message`, `created_at`.

Con `ENABLE_SAGE_CLARIFICATION=true`, lo stesso endpoint può restituire `ClarificationResponse` con `status=ASK` o `BLOCKED`, `session_id`, domanda o messaggio. Con `READY`, la normale risposta `AnalysisResponse` viene restituita dopo aver avviato la run sulla query raffinata. Flag disabilitato: risposta e flusso correnti invariati.

### Esempio minimo

```json
{"query":"Find large buildings near the Polytechnic of Turin","output_language":"it","map_limit":500,"llm_limit":5}
```

## Risultati e modelli

`GET /api/v1/analysis/{run_id}` fornisce `AnalysisResults`, che include identificatore, query, stato e array di `BuildingResponse`. Quest'ultimo contiene coordinate, indirizzo, area, classe energetica, metadati catastali, score numerici e pesi, con molte proprietà opzionali. `BuildingsListResponse` usa `buildings`, `total`, `limit`, `offset`, `has_more`.

L'API include anche DTO per storico, tracce degli agenti, energia e punteggi di prossimità. Mantenere sincronizzate definizioni Pydantic e `frontend/src/api/types.ts`.

## Risposta asincrona

Il `POST` non implica che tutti i risultati siano già calcolati. Usare il [WebSocket](progress-events.md) e poi leggere l'endpoint `GET` per la run.
