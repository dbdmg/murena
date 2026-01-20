# API_GUIDE

Questo documento descrive le API effettivamente disponibili nel backend FastAPI (cartella `backend/`).

- Base URL (dev): `http://localhost:8000`
- Prefix API v1: `/api/v1`
- Swagger (dev): `/docs`
- Healthcheck: `GET /health`

## Autenticazione (JWT)
Router: `/api/v1/auth`

- `POST /api/v1/auth/login` (form)
  - Body: `application/x-www-form-urlencoded` con `username`, `password`
  - Response: `{ access_token, token_type, expires_in }`

- `POST /api/v1/auth/register` (JSON)
  - Body (JSON): `{ "username": "...", "password": "...", "email": "..." }`

- `GET /api/v1/auth/me`
  - Header: `Authorization: Bearer <token>`

- `POST /api/v1/auth/refresh`
  - Header: `Authorization: Bearer <token>`

## Analysis
Router: `/api/v1/analysis`

### Avvio analisi reale (LLM)
- `POST /api/v1/analysis`
  - Body (JSON):
    ```json
    {
      "query": "Appartamenti a Torino vicino al Politecnico",
      "dataset_key": "full",
      "map_limit": 500,
      "llm_limit": 10,
      "analysis_mode": "agent"
    }
    ```
  - **Nota**: `analysis_mode` è `"agent"` di default (l'unico modo supportato). Il mode `"classic"` è deprecato.
  - Response (202): `{ run_id, status, message, created_at }`

### Recupero risultati / stato
- `GET /api/v1/analysis/{run_id}`
  - Response: `AnalysisResults`
  - Nota: se la run è ancora `processing`, `buildings` può essere vuoto.
  
  **Response Format Dettagliato:**
  ```json
  {
    "run_id": "abc123",
    "status": "completed",
    "query": "appartamenti vicino piazza castello",
    "created_at": "2026-01-18T12:00:00Z",
    "completed_at": "2026-01-18T12:00:30Z",
    
    "buildings": [
      {
        "id": 693768,
        "indirizzo": "Via Roma 1",
        "superficie_di_riferimento_mq": 150.0,
        "tipologia_bene_immobile": "Abitazione",
        "latitudine": 45.07,
        "longitudine": 7.68,
        "classe_energetica_ape": "E",
        "ape_score_total": 2.0,
        "distanza_km": 0.5,
        "ranking_score": 0.85,
        "is_evaluated": true,
        "evaluation_text": "Immobile in ottima posizione...",
        "score": 75,
        "pros": ["Posizione centrale", "Buona superficie"],
        "cons": ["Classe energetica bassa"]
      }
    ],
    
    "location": [["Piazza Castello, Torino", 45.0706, 7.6847]],
    
    "filters_applied": {
      "where_clause": "WHERE haversine_km(...) < 3"
    },
    
    "gemini_responses": {
      "analysis_mode": "agent",
      "dataset_key": "full",
      "location_extraction": {...},
      "typology_extraction": {...},
      "needs_metric_plan": {...},
      "sql_generation": {...},
      "evaluation": {...},
      "broker_review": "..."
    }
  }
  ```

- `GET /api/v1/analysis/{run_id}/gemini_responses`
  - Restituisce solo `gemini_responses` per una run (utile per UI expert).
  - Query: `keys=...` (opzionale, lista separata da virgole per filtrare le chiavi top-level)

- `GET /api/v1/analysis/{run_id}/agent_steps`
  - Vista normalizzata e più stabile per UI expert (lista ordinata di step con `key`, `label`, `prompt`, `response`, `data`).
  - Query:
    - `keys=...` (opzionale, lista separata da virgole)
    - `include_prompt=true|false` (default `true`)
    - `include_raw=true|false` (default `false`, evita payload molto grandi in `response`)

### Storico
- `GET /api/v1/analysis/history?limit=50&offset=0`
  - Se non autenticato, ritorna le run recenti (dev convenience).

### Cancellazione
- `DELETE /api/v1/analysis/{run_id}`

### WebSocket progress
- `WS /api/v1/ws/analysis/{run_id}`
  - Messaggi:
    - `{"type":"progress", ...}`
    - `{"type":"complete","run_id":"...","results_url":"/api/v1/analysis/..."}`

## Demo runs (senza LLM, basate su `runs/admin/*`)
Queste API servono per demo “simulate” nel frontend: caricano artefatti reali (metadata + results.csv), persistono una run `completed` e non consumano token.

- `GET /api/v1/analysis/demos`
  - Lista cartelle in `runs/admin/*` che contengono `metadata.json`.

- `POST /api/v1/analysis/demos/{demo_id}?limit=50`
  - Crea una run `completed` nel DB a partire da `runs/admin/{demo_id}`.
  - Response (200): `{ run_id, status:"completed", message, created_at }`
  - Poi il frontend usa: `GET /api/v1/analysis/{run_id}`.
  - Artifact opzionale: `gemini_responses.json` (prompt + risposte agent, usato per la UI expert).

## Prompts (override templates)
Router: `/api/v1/prompts`

Queste API espongono il sistema di override basato su `backend/app/services/llm/prompt_config.md`.
Pensato per workflow “expert”/dev (in produzione l’editing è disabilitato).

- `GET /api/v1/prompts/overrides`
  - Lista tutti gli override caricati dal file markdown.

- `GET /api/v1/prompts/overrides/{agent}/{key}`
  - Recupera un singolo blocco override.

- `PUT /api/v1/prompts/overrides/{agent}/{key}`
  - Aggiorna/crea un override nel file markdown.
  - Body: `{ "text": "..." }`

- `POST /api/v1/prompts/reload`
  - Svuota la cache e ricarica gli override dal file.
- `POST /api/v1/prompts/reset`
  - Ripristina TUTTI i prompt ai valori di default (copia `prompt_config.default.md` su `prompt_config.md`).

- `POST /api/v1/prompts/reset/{agent}`
  - Ripristina i prompt di un singolo agente ai valori di default.

- `GET /api/v1/prompts/agents`
  - Lista tutti gli agenti disponibili e le loro chiavi di prompt.
## Buildings
Router: `/api/v1`

- `GET /api/v1/buildings`
  - Query params principali: `run_id`, `min_surface`, `max_surface`, `min_score`, `energy_classes`, `city`, `is_evaluated`, `limit`, `offset`, `dataset_key`

- `GET /api/v1/buildings/{building_id}?dataset_key=full`

## Feedback (app-level)
Router: `/api/v1/feedback`

Per ora supportiamo solo feedback “globale” sull’esperienza/app (non per singolo immobile).
È legato a una `run_id`.

- `POST /api/v1/feedback/app`
  - Body (JSON):
    ```json
    {
      "run_id": "...",
      "payload": { "query": {"corrispondenza_query": 4}, "dati_mancanti": {} },
      "rating": 4,
      "comment": "..." 
    }
    ```

- `GET /api/v1/feedback/app?run_id=...&limit=50`

## Map
Router: `/api/v1/map`

- `GET /api/v1/map/config`
- `GET /api/v1/map/overlays/{overlay_type}`
- `GET /api/v1/map/markers` (con filtri)

## Layers (POI + Zone OMI)
Router: `/api/v1/layers`

- `GET /api/v1/layers/pois`
  - Query: `categories` (pipe-separated), bounding box (`min_lat`, `max_lat`, `min_lon`, `max_lon`), `limit`

- `GET /api/v1/layers/zone-omi` (se presente nel file; vedi router e implementazione in `backend/app/api/v1/endpoints/layers.py`)

## APE
Router: `/api/v1/ape`

- `GET /api/v1/ape/{filename}`

## Gap rispetto alla legacy (Dash)
Dalla legacy in `app/callbacks/*` emergono aree funzionali non ancora esposte come API dedicate:

1. **Feedback per singolo immobile**
   - Legacy: `app/callbacks/feedback_callbacks.py` salva feedback per edificio singolo.
   - Backend: esiste già API per feedback app-level (`POST /api/v1/feedback/app`), manca solo feedback per-building.

2. **Chat / agent chat**
   - Legacy: `app/callbacks/chat_callbacks.py`.
   - Backend: non esiste un endpoint chat dedicato (al momento, non prioritario).

3. **UI state / stores e filtri avanzati**
   - Legacy: `filters.py`, `stores.py`, `filter_callbacks.py`, `modal_callbacks.py`, ecc.
   - Backend: molti filtri sono già esposti via `GET /map/markers` e `GET /buildings`, la parità completa dipende dal frontend React.

## Dove siamo rispetto a migration_plan.md
- Phase 1-2 (Backend foundation + core API): ✅ Completate (auth + analysis + persistence + websocket + buildings + feedback app-level).
- Phase 3 (Map features): ✅ Endpoint pronti (map + overlays + layers POI/OMI); servirà lavoro nel frontend React.
- Phase 4+ (Pagine dettaglio, UX, feedback per-building): Da implementare nel frontend.

## Note tecniche
- **Analysis Mode**: Solo `"agent"` è supportato. Il mode `"classic"` è deprecato e sarà rimosso.
- **Dataset**: Il campo `codice_comune` usa codici catastali (es. `L219` = Torino), non nomi città.
- **LLM Provider**: Configurabile via `DEFAULT_LLM_PROVIDER` in `.env` (supportati: `openai`, `gemini`).

## Prossimi step consigliati
1. Sviluppare frontend React con integrazione API analysis
2. Generare tipi TS dal modello OpenAPI (`/openapi.json`) per allineare frontend
3. Implementare feedback per-building quando necessario
