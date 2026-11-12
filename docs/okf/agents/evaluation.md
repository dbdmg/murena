---
type: Agent
title: EvaluationAgent
description: Produce valutazioni qualitative dei risultati selezionati.
tags:
- agent
- evaluation
- llm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/evaluation_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/evaluation_agent.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
---

# EvaluationAgent

## Responsabilità

Produce valutazioni qualitative dei risultati selezionati.

## Contratto e implementazione

- Classe: `EvaluationAgent` in `backend/app/services/llm/agents/evaluation_agent.py`.
- Base comune: `BaseAgent`; output tipizzato e strutture intermedie in `agents/schema.py`.
- Prompt centralizzati in `app/services/llm/prompt_config.md`, caricati da `prompt_loader.py`.
- Selezione del modello: `app/services/llm/langchain_client.py` e `app/core/config.py`.

## Comportamento rilevante

Il paper descrive punti di forza e debolezza, di norma per la shortlist di testa; motivazioni da validare contro i dati strutturati. Il contesto inviato al modello deve usare i nomi effettivi del dataset (`address`, `property_type`, `energy_class`, `education`, ecc.) e includere i campi derivati disponibili come `distanza_km` e `poi_riferimento`. Il dataset demo usa nomi inglesi; affidarsi solo agli alias italiani causava la perdita di indirizzo, tipologia, classe energetica e punteggi di prossimità.

Il calcolo di distanza supporta sia le coordinate canoniche `latitude`/`longitude` sia gli alias `latitudine`/`longitudine`. Questo mantiene disponibili distanza e luogo di riferimento per ranking e spiegazioni quando i dati provengono direttamente dall'inventario.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
