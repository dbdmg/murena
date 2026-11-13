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
- resource: ../../../backend/experiments/benchmark_cli.py
  title: CLI per benchmark conversazionali
- resource: ../../../backend/experiments/scenarios.example.yaml
  title: Esempi di conversazioni benchmark
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

## Benchmark di scenari conversazionali

Per confrontare scenari definiti dall'utente senza avviare API o frontend, usare la CLI diretta al servizio di analisi:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/scenarios.example.yaml \
  --output backend/experiments/results/scenario-run \
  --repeat 3
```

La CLI usa il modello predefinito di `backend/.env`, come il frontend: la richiesta della UI non invia `model_type` e il backend seleziona `settings.LLM_MODEL`. In questa fase una singola esecuzione confronta gli scenari sullo stesso modello. Per gli scenari conversazionali la CLI invoca direttamente `SageClarifier`, anche se `ENABLE_SAGE_CLARIFICATION` è disattivato nel server; le domande sono generate dal modello e la CLI simula le risposte utente descritte nello scenario e la conferma della query revisionata prima dell'analisi.

Il formato consigliato è YAML (`.yaml`/`.yml`), che permette commenti; è supportato anche JSON con lo stesso schema multi-turn. Ogni scenario richiede `id`, `initial_query`, `expected_initial_missing` e `clarifications`. Il primo elenca le dimensioni (`I`, `D`, `L`, `Cb`, `Ce`, `Cp`) lasciate intenzionalmente assenti; `clarifications` associa una risposta naturale a ciascuna di esse e può includere risposte di recupero se SAGE chiede una dimensione già specificata. La legenda delle dimensioni e degli stati è commentata in `scenarios.example.yaml`. SAGE sceglie quale dimensione chiedere e la CLI invia la risposta corrispondente. Per dichiarare una dimensione non rilevante si può rispondere esplicitamente, ad esempio “non ho preferenze”. `expected_mapping` confronta gli stati finali attesi (`SPECIFIED`, `NOT_REQUESTED`, ecc.) con quelli prodotti. Il report include F1 del rilevamento iniziale delle dimensioni mancanti e accuratezza della mappatura finale. Ogni scenario può anche avere `name`, `tags`, `expected_ids`, `repeats` e `options`; `reviewed_query` opzionale permette di simulare una modifica alla query mostrata in revisione. `--repeat` imposta il numero minimo di ripetizioni; un valore `repeats` maggiore sul singolo scenario prevale.

La cartella di output contiene `manifest.json`, `runs.jsonl` (una riga per prova con transcript completo user/assistant, domande, risposte, dimensioni bersaglio e stato della mappatura dopo ogni risposta, query raffinata, SQL e traccia agenti) e `summary.csv` (durata media, turni medi, F1 dei campi inizialmente mancanti, accuratezza della mappatura finale, numero medio di risultati ed eventuale recall rispetto a `expected_ids`). Il JSONL registra la conversazione osservabile e gli stati, non i prompt interni grezzi o il ragionamento privato del modello. `--resume` riprende una cartella esistente saltando le combinazioni modello/scenario/ripetizione già completate. Le prove sono sequenziali per mantenere ordinato il carico sul provider.

La CLI richiede `backend/.env`, un provider LLM configurato e dataset accessibile tramite la configurazione del backend. Se manca il dataset demo locale, crearlo con `uv run python backend/data/metadata/create_demo_dataset.py`. La CLI risolve i percorsi relativi del backend rispetto alla directory `backend/`, anche quando viene invocata dalla root del repository. I risultati descrivono le esecuzioni fatte su quel setup; non sono da soli una replica dei benchmark del paper.

Per mantenere leggibile l'output, la CLI filtra alcuni warning ripetitivi e noti di LangGraph, pandas e delle chiamate `datetime.utcnow()` del backend, anche durante l'import iniziale di LangGraph; altri warning restano visibili.

Opzioni documentate per l'harness: `--with-qwen`, `--with-gemma`, `--all-models`. La directory `backend/tests/` ospita un **harness sperimentale**, non una suite pytest di unit test completa.

## Controlli per confronti attendibili

Registrare versione del dataset, query, modello/endpoint, prompt, condizioni di geocoding, mapping OSM, hardware e numero di prove. Se una tabella viene rigenerata **da log**, distinguere report derivato da una esecuzione effettiva.

[Vedi risultati](benchmarks.md), [limiti](limitations.md) e [verifica software](../operations/quality.md).
