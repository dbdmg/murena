# API Guide

This document describes the API endpoints available in the FastAPI backend (located in `backend/`).

- Base URL (dev): `http://localhost:8000`
- API v1 Prefix: `/api/v1`
- Swagger (dev): `/docs`
- Healthcheck: `GET /health`

## Authentication (JWT)
Router: `/api/v1/auth`

- `POST /api/v1/auth/login` (form)
  - Body: `application/x-www-form-urlencoded` with `username`, `password`
  - Response: `{ access_token, token_type, expires_in }`

- `POST /api/v1/auth/register` (JSON)
  - Body (JSON): `{ "username": "...", "password": "...", "email": "..." }`

- `GET /api/v1/auth/me`
  - Header: `Authorization: Bearer <token>`

- `POST /api/v1/auth/refresh`
  - Header: `Authorization: Bearer <token>`

## Analysis
Router: `/api/v1/analysis`

### Start Real Analysis (LLM)
- `POST /api/v1/analysis`
  - Body (JSON):
    ```json
    {
      "query": "Apartments in Turin near the Polytechnic",
      "dataset_key": "full",
      "map_limit": 500,
      "llm_limit": 10,
      "analysis_mode": "agent"
    }
    ```
  - **Note**: `analysis_mode` is `"agent"` by default (the only supported mode). The `"classic"` mode is deprecated.
  - Response (202): `{ run_id, status, message, created_at }`

### Retrieve Results / Status
- `GET /api/v1/analysis/{run_id}`
  - Response: `AnalysisResults`
  - Note: if the run is still `processing`, `buildings` may be empty.
  
  **Detailed Response Format:**
  ```json
  {
    "run_id": "abc123",
    "status": "completed",
    "query": "apartments near Piazza Castello",
    "created_at": "2026-01-18T12:00:00Z",
    "completed_at": "2026-01-18T12:00:30Z",
    
    "buildings": [
      {
        "id": 693768,
        "address": "Via Roma 1",
        "surface_sqm": 150.0,
        "property_type": "Residential",
        "latitude": 45.07,
        "longitude": 7.68,
        "energy_class_epc": "E",
        "epc_score_total": 2.0,
        "distance_km": 0.5,
        "ranking_score": 0.85,
        "is_evaluated": true,
        "evaluation_text": "Building in excellent position...",
        "score": 75,
        "pros": ["Central position", "Good surface"],
        "cons": ["Low energy efficiency"]
      }
    ],
    
    "location": [["Piazza Castello, Turin", 45.0706, 7.6847]],
    
    "filters_applied": {
      "where_clause": "WHERE haversine_km(...) < 3"
    },
    
    "gemini_responses": {
      "analysis_mode": "agent",
      "dataset_key": "full",
      "location_extraction": {...},
      "property_technical_extraction": {...},
      "sql_generation": {...},
      "evaluation": {...},
      "broker_review": "..."
    }
  }
  ```

- `GET /api/v1/analysis/{run_id}/gemini_responses`
  - Returns only `gemini_responses` for a run (useful for expert UI).
  - Query: `keys=...` (optional, comma-separated list to filter top-level keys)

- `GET /api/v1/analysis/{run_id}/agent_steps`
  - Normalized view for expert UI (ordered list of steps with `key`, `label`, `prompt`, `response`, `data`).

### History
- `GET /api/v1/analysis/history?limit=50&offset=0`
  - If not authenticated, returns recent runs (dev convenience).

### Progress Monitoring
- `WS /api/v1/ws/analysis/{run_id}`
  - Messages:
    - `{"type":"progress", ...}`
    - `{"type":"complete","run_id":"...","results_url":"/api/v1/analysis/..."}`

## Demo Runs
These APIs serve "simulated" demos in the frontend using actual artifacts (metadata + results.csv).

- `GET /api/v1/analysis/demos`
  - Lists folders in `runs/admin/*` containing `metadata.json`.

- `POST /api/v1/analysis/demos/{demo_id}?limit=50`
  - Creates a `completed` run in the DB starting from `runs/admin/{demo_id}`.

## Prompt Management (Override Templates)
Router: `/api/v1/prompts`
Thought for expert/dev workflows (editing disabled in production).

- `GET /api/v1/prompts/overrides`
- `PUT /api/v1/prompts/overrides/{agent}/{key}`
- `POST /api/v1/prompts/reset`

## Buildings
Router: `/api/v1`

- `GET /api/v1/buildings`
- `GET /api/v1/buildings/{building_id}`

## Feedback
Router: `/api/v1/feedback`

- `POST /api/v1/feedback/app`
  - Body (JSON):
    ```json
    {
      "run_id": "...",
      "payload": { "query": {"match_quality": 4}, "missing_data": {} },
      "rating": 4,
      "comment": "..." 
    }
    ```

## Maps and Layers
Router: `/api/v1/map` and `/api/v1/layers`

- `GET /api/v1/map/config`
- `GET /api/v1/layers/pois`
- `GET /api/v1/layers/zone-omi`

---

## Technical Notes
- **Analysis Mode**: Only `"agent"` is supported. `"classic"` is deprecated.
- **Dataset**: The `codice_comune` field uses cadastral codes (e.g., `L219` for Turin).
- **LLM Provider**: Configurable via `DEFAULT_LLM_PROVIDER` in `.env` (supports `openai`, `gemini`).
