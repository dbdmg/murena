---
type: Workflow
title: Flusso analisi end-to-end
description: Trasformazione di una query in vincoli, SQL, shortlist e motivazioni.
tags:
- workflow
- langgraph
- agents
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
- resource: ../../../backend/app/services/analysis_service.py
  title: 'MURENA repository: backend/app/services/analysis_service.py'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Flusso analisi end-to-end

## Sequenza applicativa

1. L'utente invia `POST /api/v1/analysis` con testo, dataset, limiti e lingua.
2. L'API registra la run e avvia l'elaborazione, restituendo un `run_id`.
3. `AnalysisService` carica o riusa un dataset e invoca `GraphOrchestratorAgent`.
4. **Phase 1 — requirements extraction:** il grafo identifica ambiti e vincoli mediante gli agenti specializzati (location, building, energy, proximity, regulatory).
5. **Phase 2 — SQL execution:** `SQLAgent` compone una query per DuckDB; l'esecutore valida la sintassi con `EXPLAIN` e interroga i dati. Sono previsti retry, fallback e rilassamento dei vincoli per zero risultati.
6. **Phase 3 — scoring & synthesis:** arricchimento risultati, attribuzione pesi, ranking numerico, valutazione qualitativa e sintesi del broker quando prevista.
7. La run salva i risultati e comunica percentuale/stato tramite WebSocket; il client carica i dettagli REST, mostrando edifici, mappe e spiegazioni.

## Grafo operativo

```text
analyze_request -> generate_sql -> execute_sql
                                      | retry  -> handle_retry -> generate_sql
                                      | relax  -> relax_query  -> execute_sql
                                      | fallback -> fallback_results
                                      v
                                 enrich_results
                                      -> calculate_ranking_weights
                                      -> rank_results -> evaluate_results
                                      -> (broker_review opzionale)
                                      -> finalize_results -> END
```

Il grafo implementato ha rami condizionali e non è limitato a una sequenza rigida di tre nodi. La distinzione in tre fasi è un modello logico del paper.

## Invarianti raccomandate

- Trattare `run_id` come identificatore condiviso da storico, WS, feedback e tracce.
- Non interpretare la narrazione LLM come sostituto dei filtri realmente eseguiti.
- Esaminare [SQL](../agents/sql.md), [ranking](../data/scoring.md) e [limiti di sicurezza](../operations/security.md) per una modifica al flusso.
