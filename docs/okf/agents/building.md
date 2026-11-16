---
type: Agent
title: BuildingAgent
description: Estrae tipologia, dimensioni e altri criteri fisici/catastali.
tags:
- agent
- building
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/building_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/building_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# BuildingAgent

## Responsabilità

Estrae tipologia, dimensioni e altri criteri fisici/catastali.

## Contratto e implementazione

- Classe: `BuildingAgent` in `backend/app/services/llm/agents/building_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Colonne dichiarate nel prompt: `property_type`, `construction_period`, `id`, `comune_code`, `cadastral_sheet`, `cadastral_parcel`, `cadastral_subaltern`, `cadastral_units_count`, `surface_area`. Il loader normalizza `codice_comune` storico a `comune_code`; i metadati di filtro runtime vengono intersecati con le colonne del dataset caricato. `comune_code` indica un codice catastale comunale: il modello non deve ricavarlo da nomi di città o luoghi; la ricerca geografica usa il LocationAgent. Il paper associa descrittori qualitativi a quantili P25/P75.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
