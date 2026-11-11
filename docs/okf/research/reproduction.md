---
type: Playbook
title: Riprodurre i benchmark
description: Comandi di experiment harness e dipendenze per ripetere il protocollo sperimentale.
tags:
- experiments
- reproduction
- playbook
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../README.md
  title: 'MURENA repository: README.md'
- resource: ../../../AGENTS.md
  title: 'MURENA repository: AGENTS.md'
- resource: ../../../run_experiments.py
  title: 'MURENA repository: run_experiments.py'
- resource: ../../../backend/experiments/reproduce_results.py
  title: 'MURENA repository: backend/experiments/reproduce_results.py'
- resource: ../../../backend/tests/test_suite.py
  title: 'MURENA repository: backend/tests/test_suite.py'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Riprodurre i benchmark

## Prerequisiti

Ambiente Python sincronizzato via `uv`, modello LLM compatibile e configurato, `.env` locale con i parametri necessari e **dataset adeguato**. Il repository caricato non contiene necessariamente tutti i dataset APE/OSM originali di ricerca; senza tali dati non è corretto aspettarsi i numeri del manoscritto.

## Esecuzioni previste

```bash
# Esempio ridotto sul test harness
python run_experiments.py --type sampled --limit 20

# Esecuzione completa e report Markdown
python run_experiments.py --type all

# Tabelle di risultati del paper dai log disponibili
python backend/experiments/reproduce_results.py --table 1
python backend/experiments/reproduce_results.py --table 2
```

Opzioni documentate per l'harness: `--with-qwen`, `--with-gemma`, `--all-models`. La directory `backend/tests/` ospita un **harness sperimentale**, non una suite pytest di unit test completa.

## Controlli per confronti attendibili

Registrare versione del dataset, query, modello/endpoint, prompt, condizioni di geocoding, mapping OSM, hardware e numero di prove. Se una tabella viene rigenerata **da log**, distinguere report derivato da una esecuzione effettiva.

[Vedi risultati](benchmarks.md), [limiti](limitations.md) e [verifica software](../operations/quality.md).
