---
type: Agent
title: RelaxationAgent
description: Propone allentamenti mirati quando il risultato di una query è vuoto.
tags:
- agent
- relaxation
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/relaxation_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/relaxation_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# RelaxationAgent

## Responsabilità

Propone allentamenti mirati quando il risultato di una query è vuoto.

## Contratto e implementazione

- Classe: `RelaxationAgent` in `backend/app/services/llm/agents/relaxation_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Il grafo segue il ramo `relax_query` se la condizione di esecuzione lo richiede e `use_relaxation` è attivo; preservare visibilità della modifica dei vincoli. Il rilassamento scatta quando i risultati sono meno di 10 e, se le proposte LLM non corrispondono esattamente a una condizione, rimuove condizioni dall'ultima alla prima. Dal 2026-11-17 `relaxation_applied` resta vero se un qualsiasi passaggio ha modificato la SQL e la risposta espone il numero di passaggi effettivi e la SQL originale dell'agente (vedere [SQLAgent](sql.md)).

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
