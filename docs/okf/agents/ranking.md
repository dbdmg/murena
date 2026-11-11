---
type: Agent
title: RankingAgent
description: Interpreta la priorità relativa dei domini richiesti e produce pesi normalizzati.
tags:
- agent
- ranking
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/ranking_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/ranking_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# RankingAgent

## Responsabilità

Interpreta la priorità relativa dei domini richiesti e produce pesi normalizzati.

## Contratto e implementazione

- Classe: `RankingAgent` in `backend/app/services/llm/agents/ranking_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Supporta modalità filtering (pesi dal ranking armonico) e ranking (calcolo nel percorso dedicato); i valori ricadono nei cinque domini noti.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
