---
type: Agent
title: RegulatoryAgent
description: Estrae requisiti di conformità e categorie normative pertinenti.
tags:
- agent
- regulatory
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/regulatory_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/regulatory_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# RegulatoryAgent

## Responsabilità

Estrae requisiti di conformità e categorie normative pertinenti.

## Contratto e implementazione

- Classe: `RegulatoryAgent` in `backend/app/services/llm/agents/regulatory_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Colonne esplicitamente disponibili: `surface_area`, `property_type`, `legal_nature`, `cultural_constraint`. Il paper prevede regole strutturate statiche; l’output è supporto analitico, non parere giuridico.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
