---
type: Agent
title: LocationAgent
description: Estrae città, distanze e landmark, collaborando con geocoding e filtri geografici.
tags:
- agent
- location
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/location_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/location_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# LocationAgent

## Responsabilità

Estrae città, distanze e landmark, collaborando con geocoding e filtri geografici.

## Contratto e implementazione

- Classe: `LocationAgent` in `backend/app/services/llm/agents/location_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Colonne principali: `address`, `house_number`, `latitude`, `longitude`, `omi_zone`. Nel paper il raggio limite di default è 3 km; controllare default e override del codice per la run.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
