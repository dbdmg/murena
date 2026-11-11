---
type: Agent
title: ProximityAgent
description: Estrae preferenze sulle amenities e servizi urbani richiesti.
tags:
- agent
- proximity
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/proximity_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/proximity_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# ProximityAgent

## Responsabilità

Estrae preferenze sulle amenities e servizi urbani richiesti.

## Contratto e implementazione

- Classe: `ProximityAgent` in `backend/app/services/llm/agents/proximity_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Filtra e valuta score aggregati nelle colonne `healthcare`, `mobility`, `green`, `sport`, `commercial`, `education`; non sono API di navigazione turn-by-turn.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
