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
- resource: ../../../backend/docs/knowledge/normativa/normativa.json
  title: 'MURENA repository: user-supplied Turin conversion metrics'
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

Il loader legge ricorsivamente file `.json`, `.md` e `.txt` da `backend/docs/knowledge/normativa/` e inserisce il contenuto nel prompt dell'agente. La fonte corrente contiene otto casi di conversione per servizi per l'infanzia, assistenza diurna/residenziale agli anziani e residenze universitarie legate a uno specifico programma CDP/PNRR. L'unica colonna abilitata per un filtro normativo è `surface_area`.

L'output include `matched_use_cases` con le etichette esatte dei record pertinenti anche quando non è possibile estrarre un filtro. Le metriche di superficie netta si riferiscono a funzioni o locali specifici e non vengono convertite nella superficie lorda del fabbricato; le soglie lorde nulle o `not_verified` non producono filtri. Le condizioni, i controlli e gli standard legati a bandi restano contesto per la valutazione. Il JSON deriva dal file fornito dall'utente e il loader non verifica autonomamente l'esattezza giuridica delle fonti, dei valori o della loro applicabilità.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.
