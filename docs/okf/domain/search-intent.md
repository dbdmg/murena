---
type: Domain Concept
title: Intento e vincoli immobiliari
description: Modello semantico delle richieste e delle priorità esplicite o implicite.
tags:
- domain
- requirements
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/models/requests.py
  title: 'MURENA repository: backend/app/models/requests.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Intento e vincoli immobiliari

Nel paper una query è modellata come `Q = (I, D, L, C_b, C_e, C_p)`, con intento/tipologia `I`, destinazione d'uso `D`, località `L`, vincoli strutturali `C_b`, energetici `C_e` e di prossimità `C_p`.

## Concetti

- **Vincolo hard / filtering mode:** requisito da tradurre in predicato SQL (`WHERE`).
- **Preferenza soft / ranking mode:** fattore che influenza lo score fra gli edifici candidati.
- **Agente attivo:** ambito pertinente alla query; gli agenti non pertinenti non devono dominare lo score.
- **Priorità:** rank che determina pesi armonici `1 / rank`, poi normalizzati.
- **Rilassamento:** alternativa esplicita quando una query è troppo restrittiva e produce zero match.

Il frontend richiede in `AnalysisRequest` il campo `query` e accetta anche `dataset_key`, `analysis_mode`, `map_limit`, `llm_limit`, `output_language`, `use_relaxation`, `model_type`.

## Collegamenti

[Agente ranking](../agents/ranking.md), [Agenti tecnici](../agents/index.md), [SQL](../agents/sql.md), [scoring](../data/scoring.md).
