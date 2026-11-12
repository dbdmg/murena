---
type: Configuration
title: Configurazione e variabili d’ambiente
description: Impostazioni essenziali del server, degli storage, dell’inferenza e della UI.
tags:
- configuration
- environment
- ops
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/core/config.py
  title: 'MURENA repository: backend/app/core/config.py'
- resource: ../../../backend/app/services/llm/providers.py
  title: 'MURENA repository: backend/app/services/llm/providers.py'
- resource: ../../../backend/app/services/llm/codex_exec.py
  title: 'MURENA repository: backend/app/services/llm/codex_exec.py'
- resource: ../../../backend/.env.example
  title: 'MURENA repository: backend/.env.example'
- resource: ../../../frontend/.env.example
  title: 'MURENA repository: frontend/.env.example'
- resource: ../../../frontend/src/api/client.ts
  title: 'MURENA repository: frontend/src/api/client.ts'
---

# Configurazione e variabili d’ambiente

## File

- `backend/.env` è letto da `pydantic-settings` e dal launcher.
- `frontend/.env` può impostare l'URL API Vite.

## Chiavi significative (solo **nomi**, non valori sensibili)

| Ambito | Variabili |
|---|---|
| Server | `HOST`, `PORT`, `DEBUG`, `LOG_LEVEL`, `CORS_ORIGINS` |
| SQLite | `DATABASE_URL`, `DATABASE_PATH` |
| JWT | `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` |
| Modello/provider | `LLM_MODEL`, `LLM_PROVIDER`, `LLM_BASE_URL`, `OPENAI_API_BASE`, `OLLAMA_BASE_URL` |
| Codex CLI | `CODEX_EXECUTABLE`, `CODEX_REASONING_EFFORT`, `CODEX_TIMEOUT_SECONDS` |
| Chiavi provider | `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `INSTITUTIONAL_LLM_API_KEY` e altre supportate |
| Frontend | `VITE_API_URL` (fallback `/api/v1`) |

Le impostazioni hanno altri campi specifici in `app/core/config.py`; usare il codice e `.env.example` come autorità per il set completo.

`LLM_PROVIDER=codex_exec` seleziona Codex dalla factory condivisa `get_llm` per SAGE e per tutti gli agenti MURENA; `LLM_MODEL=gpt-6-luna` e `CODEX_REASONING_EFFORT=low` configurano il modello. Richiede il CLI installato e autenticato con ChatGPT. Per tornare a vLLM, impostare `LLM_PROVIDER=openai-compatible`, `LLM_BASE_URL` e `LLM_MODEL` secondo il servizio. Riavviare il backend dopo aver cambiato provider.

## Regole

Non inserire token, chiavi o URL interni in OKF, commit o log pubblici. In produzione usare secret manager, origini CORS limitate, HTTPS/WSS e una modalità di avvio senza reset della SQLite. Consultare [sicurezza](security.md).
