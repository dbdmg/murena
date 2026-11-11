---
type: Agent
title: EnergyAgent
description: Interpreta classe EPC e indicatori di prestazione energetica.
tags:
- agent
- energy
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/energy_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/energy_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# EnergyAgent

## Responsabilità

Interpreta classe EPC e indicatori di prestazione energetica.

## Contratto e implementazione

- Classe: `EnergyAgent` in `backend/app/services/llm/agents/energy_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Colonne: `energy_class`, `epglnren_ape`, `classe_target_ape`, `energy_score_class`, `energy_score_plant`, `energy_score_envelope`, `energy_score_renewables`, `energy_score_total`.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
