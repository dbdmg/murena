---
type: Agent
title: SQLAgent
description: Sintetizza vincoli tecnici in una SELECT DuckDB e restituisce la query.
tags:
- agent
- sql
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/sql_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/sql_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# SQLAgent

## Responsabilità

Sintetizza vincoli tecnici in una SELECT DuckDB e restituisce la query.

## Contratto e implementazione

- Classe: `SQLAgent` in `backend/app/services/llm/agents/sql_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Il codice usa `sqlglot` per parsing/formattazione e controlli di keyword; l’esecutore DuckDB applica `EXPLAIN` prima dell’esecuzione. La validazione non costituisce un sandbox SQL formalmente completo.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
