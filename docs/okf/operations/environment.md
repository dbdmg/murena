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
- resource: ../../../backend/app/services/llm/claude_cli.py
  title: 'MURENA repository: backend/app/services/llm/claude_cli.py'
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
| Modello/provider | `LLM_MODEL`, `LLM_PROVIDER`, `LLM_BASE_URL`, `OPENAI_API_BASE`, `OLLAMA_BASE_URL`, `LLM_DISABLE_THINKING` |
| Codex CLI | `CODEX_EXECUTABLE`, `CODEX_REASONING_EFFORT`, `CODEX_TIMEOUT_SECONDS` |
| Claude Code CLI | `CLAUDE_CLI_EXECUTABLE`, `CLAUDE_CLI_EFFORT`, `CLAUDE_CLI_TIMEOUT_SECONDS` |
| Chiavi provider | `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `INSTITUTIONAL_LLM_API_KEY` e altre supportate |
| Frontend | `VITE_API_URL` (fallback `/api/v1`) |

Le impostazioni hanno altri campi specifici in `app/core/config.py`; usare il codice e `.env.example` come autorità per il set completo.

`LLM_PROVIDER=codex_exec` seleziona Codex dalla factory condivisa `get_llm` per SAGE e per tutti gli agenti MURENA; `LLM_MODEL=gpt-6-luna` e `CODEX_REASONING_EFFORT=low` configurano il modello. Richiede il CLI installato e autenticato con ChatGPT. Per tornare a vLLM, impostare `LLM_PROVIDER=openai-compatible`, `LLM_BASE_URL` e `LLM_MODEL` secondo il servizio. Riavviare il backend dopo aver cambiato provider.

Per i server open-weight compatibili OpenAI (`openai-compatible`, per esempio vLLM), `LLM_DISABLE_THINKING=true` invia `chat_template_kwargs.enable_thinking=false` a qualunque host, `false` non lo invia mai. Se la variabile è vuota, il flag va solo a `localhost`, `127.0.0.1` o host `institutional`. Con Ollama la finestra di contesto è quella del server, perché `ChatOllama` non imposta `num_ctx`: va alzata con `OLLAMA_CONTEXT_LENGTH`. Le istruzioni per una serie benchmark con Codex o con un modello open-weight sono in [riproduzione](../research/reproduction.md#eseguire-una-nuova-serie-con-un-altro-llm-codex-o-open-weight).

`LLM_PROVIDER=claude_cli` (alias `claude-cli`) usa il Claude Code CLI autenticato (`claude -p`), per esempio con `LLM_MODEL=claude-haiku-5-5` e `CLAUDE_CLI_EFFORT=medium`. Ogni chiamata gira in una directory temporanea vuota, con questi parametri:

- nessun tool (`--tools ""`), nessuna impostazione utente/progetto/locale (`--setting-sources ""`), nessun server MCP (`--strict-mcp-config`), nessuna sessione salvata (`--no-session-persistence`);
- i messaggi di sistema diventano il system prompt (`--system-prompt-file`), al posto del prompt agentico di Claude Code; il resto della conversazione è passato su stdin;
- l'output strutturato usa `--json-schema` e legge `structured_output` dal risultato JSON; in mancanza, estrae il JSON dal testo, anche da blocchi recintati.

Robustezza: le chiamate senza risultato o con errore riportato dal CLI vengono ritentate fino a 2 volte, con attesa crescente; i timeout non vengono ritentati. Gli avvii dei processi sono distanziati di 0,3 s, perché avvii simultanei corrompono transitoriamente `~/.claude.json`. La directory temporanea viene pulita ignorando gli errori di file bloccati su Windows. L'ambiente del processo è filtrato: niente `ANTHROPIC_API_KEY` (il CLI usa la propria sessione autenticata) né variabili di una sessione Claude Code esterna. Implementato e testato il 2026-11-17 (`backend/tests/test_claude_cli_adapter.py`).

## Regole

Non inserire token, chiavi o URL interni in OKF, commit o log pubblici. In produzione usare secret manager, origini CORS limitate, HTTPS/WSS e una modalità di avvio senza reset della SQLite. Consultare [sicurezza](security.md).
