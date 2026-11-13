---
type: API Reference
title: Catalogo endpoint HTTP e WebSocket
description: Inventario derivato dai decorator FastAPI nel codice caricato.
tags:
- api
- http
- websocket
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/api/v1/router.py
  title: 'MURENA repository: backend/app/api/v1/router.py'
- resource: ../../../backend/app/api/v1/endpoints/auth.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/auth.py'
- resource: ../../../backend/app/api/v1/endpoints/analysis.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/analysis.py'
- resource: ../../../backend/app/api/v1/endpoints/buildings.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/buildings.py'
- resource: ../../../backend/app/api/v1/endpoints/websockets.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/websockets.py'
- resource: ../../../backend/app/api/v1/endpoints/map.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/map.py'
- resource: ../../../backend/app/api/v1/endpoints/energy.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/energy.py'
- resource: ../../../backend/app/api/v1/endpoints/prompts.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/prompts.py'
- resource: ../../../backend/app/api/v1/endpoints/feedback.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/feedback.py'
- resource: ../../../backend/app/api/v1/endpoints/logs.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/logs.py'
- resource: ../../../backend/app/api/v1/endpoints/layers.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/layers.py'
---

# Catalogo endpoint HTTP e WebSocket

## Entry point

Prefisso principale `/api/v1`; `GET /health` è definito in `app/main.py`.

## Endpoint effettivamente definiti

| Area | Metodo | Percorso | Handler |
|---|---|---|---|
| auth | POST | `/api/v1/auth/login` | `login_access_token` |
| auth | POST | `/api/v1/auth/register` | `register_user` |
| auth | GET | `/api/v1/auth/me` | `read_users_me` |
| auth | POST | `/api/v1/auth/refresh` | `refresh_token` |
| analysis | GET | `/api/v1/analysis/{run_id}/gemini_responses` | `get_run_gemini_responses` |
| analysis | GET | `/api/v1/analysis/{run_id}/agent_steps` | `get_run_agent_steps` |
| analysis | GET | `/api/v1/analysis/demos` | `list_demo_runs` |
| analysis | POST | `/api/v1/analysis/demos/{demo_id}` | `start_demo_run` |
| analysis | POST | `/api/v1/analysis` | `start_analysis` |
| analysis | GET | `/api/v1/analysis/history` | `get_analysis_history` |
| analysis | GET | `/api/v1/analysis/{run_id}` | `get_analysis` |
| analysis | DELETE | `/api/v1/analysis/{run_id}` | `delete_analysis` |
| buildings | GET | `/api/v1/buildings` | `list_buildings` |
| buildings | GET | `/api/v1/buildings/{building_id}` | `get_building` |
| websockets | WEBSOCKET | `/api/v1/ws/analysis/{run_id}` | `analysis_progress_websocket` |
| map | GET | `/api/v1/map/config` | `get_map_config` |
| map | GET | `/api/v1/map/overlays/{overlay_type}` | `get_map_overlay` |
| map | GET | `/api/v1/map/markers` | `get_map_markers` |
| map | GET | `/api/v1/map/markers-lite` | `get_map_markers_lite` |
| layers | GET | `/api/v1/layers/pois` | `get_pois` |
| energy | GET | `/api/v1/energy/{filename}` | `get_energy_detail` |
| prompts | GET | `/api/v1/prompts/overrides` | `list_prompt_overrides` |
| prompts | GET | `/api/v1/prompts/overrides/{agent}/{key}` | `get_prompt_override` |
| prompts | PUT | `/api/v1/prompts/overrides/{agent}/{key}` | `put_prompt_override` |
| prompts | POST | `/api/v1/prompts/reload` | `reload_prompt_overrides` |
| prompts | POST | `/api/v1/prompts/reset` | `reset_prompt_overrides` |
| prompts | POST | `/api/v1/prompts/reset/{agent}` | `reset_agent_prompt_overrides` |
| prompts | GET | `/api/v1/prompts/agents` | `list_available_agents` |
| feedback | POST | `/api/v1/feedback/app` | `create_app_feedback` |
| feedback | GET | `/api/v1/feedback/app` | `list_app_feedback` |
| feedback | POST | `/api/v1/feedback/agent` | `create_agent_feedback` |
| feedback | GET | `/api/v1/feedback/agent` | `get_agent_feedback` |
| feedback | GET | `/api/v1/feedback/run/all` | `get_run_all_feedback` |
| feedback | GET | `/api/v1/feedback/export` | `export_feedback` |
| feedback | POST | `/api/v1/feedback/building` | `create_building_feedback` |
| feedback | GET | `/api/v1/feedback/building` | `get_building_feedback` |
| feedback | DELETE | `/api/v1/feedback/{feedback_id}` | `delete_feedback` |
| logs | GET | `/api/v1/logs/stream` | `stream_activity_log` |
| logs | GET | `/api/v1/logs/traces` | `list_agent_traces` |
| logs | GET | `/api/v1/logs/traces/{name}` | `get_agent_trace` |

`GET /api/v1/layers/pois` accetta categorie separate da `|`, limiti geografici opzionali (`min_lat`, `max_lat`, `min_lon`, `max_lon`) e un limite massimo di record.

`GET /api/v1/map/overlays/{overlay_type}` serve gli overlay `omi` e `urbanistiche`; il precedente overlay `municipi` non è più supportato.

L'inventario è estratto staticamente dai decorator dei router; non costituisce una specifica OpenAPI ottenuta avviando il server. Controllare dipendenze di autenticazione e parametri degli handler prima dell'integrazione.

[Contratti DTO](contracts.md) · [Protocollo progressi](progress-events.md).
