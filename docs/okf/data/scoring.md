---
type: Metric
title: Scoring e ranking deterministico
description: Peso degli agenti, normalizzazione e aggregazione dei punteggi immobiliari.
tags:
- ranking
- scoring
- deterministic
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/analysis/ranking.py
  title: 'MURENA repository: backend/app/services/analysis/ranking.py'
- resource: ../../../backend/app/services/llm/agents/ranking_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/ranking_agent.py'
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/graph_agent.py'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Scoring e ranking deterministico

## Peso per dominio

L'agente `RankingAgent` riceve la query e assegna un rank ai domini attivi. Il codice usa peso grezzo `1 / max(1, rank)` e normalizzazione sulla somma, con correzione di arrotondamento a due decimali. I domini ammessi sono `location`, `regulatory`, `energy`, `building`, `proximity`.

## Score per edificio

`calculate_ranking_score(...)` è una **funzione Python** che normalizza i contributi 0–1 e calcola un totale 0–100. Nel percorso corrente può usare colonne già presenti (`poi_score`, `ape_score`, `location_score`, `normative_score`, `property_technical_score`) oppure fallback su sottoscore e distanza. I coefficienti attivi vengono rinormalizzati in base alla disponibilità delle dimensioni. L'output comprende `final_ranking_score` e ordinamento decrescente, con eventuale tie-break sulla distanza.

Formula concettuale:

\[
S(b)=100\cdot \sum_{i \in A} \hat w_i\,s_i(b), \qquad \sum_{i\in A}\hat w_i=1
\]

La formula sintetizza la logica del paper; i fallback, la normalizzazione e l'attivazione di colonne in codice vanno consultati per riprodurre numericamente un risultato concreto.

## Differenze da evitare

- I macro-score di prossimità sono già precomputati e non sono distanze grezze.
- Gli score energetici `1–5`/`4–20` richiedono normalizzazione prima dell'aggregazione.
- Il paper descrive ranking orientato all'intento, pesi armonici e contributi per agenti, ma i dettagli di calcolo possono dipendere dal percorso `agent`/`classic` e dai fallback presenti nel codice.
- La spiegazione LLM non modifica automaticamente il valore numerico restituito dal ranking.

[Scoring POI](geospatial.md) · [RankingAgent](../agents/ranking.md).
