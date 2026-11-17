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

Il codice usa `sqlglot` per parsing/formattazione e controlli di keyword; l’esecutore DuckDB applica `EXPLAIN` prima dell’esecuzione. Il prompt limita le colonne alla loro intersezione tra schema runtime e allowlist dei metadati del dataset; usa `latitude`/`longitude` canoniche per le distanze e non traduce i nomi di località in `comune_code`, che è un codice catastale. Le colonne storiche `codice_comune`, `latitudine` e `longitudine` sono normalizzate dal loader. La validazione non costituisce un sandbox SQL formalmente completo. Dal 2026-11-17 l'esecutore (`backend/app/services/analysis/executor.py`, `validate_select_sql()`) analizza la SQL con `sqlglot` e accetta una sola istruzione `SELECT`, `WITH` o operazione insiemistica, rifiutando istruzioni multiple, `COPY`, `PRAGMA`, `INSTALL`, `ATTACH` e simili. Dopo la creazione delle viste DuckDB imposta `enable_external_access=false`, consentendo solo il file Parquet del dataset tramite `allowed_paths`.

La risposta di analisi espone `sql_agent_sql` (SQL dell'agente prima di qualsiasi rilassamento), `relaxation_applied` (vero se almeno un passaggio di rilassamento ha modificato la SQL), `relaxation_count` (numero di passaggi che l'hanno modificata), `fallback_activated` (risultati dal percorso di fallback) e `agent_errors` (fallimenti degli agenti gestiti con fallback, come lista di `{agent, error}`). Prima un fallimento di un agente veniva registrato come disattivazione per irrilevanza.

## Osservabilità e dipendenze

L'esito è incluso nel contesto e nelle tracce del [GraphOrchestratorAgent](orchestrator.md) e del [flusso end-to-end](../architecture/analysis-flow.md). Il comportamento concreto dipende da prompt, modello, dati caricati e fallback.

## Tipologie e schema canonico (2026-11-17)

L’orchestratore passa le tipologie estratte all’agente SQL con il nome
`property_type`, coerente con lo schema runtime. Il nome storico
`tipologia_bene_immobile` era ancora inserito nel contesto dei requisiti e
poteva indurre una SELECT su una colonna inesistente. Il contesto iniziale
legge ora `base_dataset.property_type`; i valori disponibili per il building
agent provengono da `db_metadata.fields.property_type.values`.
La correzione riguarda il passaggio dei vincoli, senza riscritture automatiche
della SQL generata o nuove regole di filtro. Test senza LLM verificano il
contesto passato all’agente e l’esecuzione sullo schema canonico.
