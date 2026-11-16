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
- resource: ../../../backend/experiments/data/scenarios/conversational_scenarios.yaml
  title: Scenari conversazionali EDBT
- resource: ../../../backend/experiments/data/scenarios/README.md
  title: Descrizione e protocollo previsto degli scenari EDBT
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

Per eseguire la sola configurazione conversational degli scenari EDBT senza avviare API o frontend:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios/conversational_scenarios.yaml \
  --output backend/experiments/results/edbt-conversational \
  --dataset full --repeat 1 --language en --concurrency 2
```

La CLI usa il modello predefinito in `backend/.env` (`settings.LLM_MODEL`) e il dataset configurato come `full`. Richiede un provider LLM e il dataset configurato accessibile. Invoca direttamente `SageClarifier`, anche se `ENABLE_SAGE_CLARIFICATION` è disattivato nel server; le domande sono generate dal modello e la CLI simula le risposte e la conferma della query revisionata prima dell'analisi. `--repeat`, `--map-limit`, `--llm-limit`, `--language`, `--use-relaxation/--no-use-relaxation`, `--resume` e `--concurrency` sono opzioni definite dal parser. La concorrenza predefinita è 2 run; usare `--concurrency 1` per esecuzione sequenziale o un valore maggiore solo se le quote del provider lo consentono. Il valore è registrato nel manifest e deve coincidere per riprendere una run; i manifest precedenti a questa opzione rappresentano run sequenziali e si riprendono con `--concurrency 1`. Per l'elenco corrente: `uv run python backend/experiments/benchmark_cli.py --help`.

Il file `conversational_scenarios.yaml` contiene le 24 istanze eseguibili. Il file delle triplette e `queries_by_configuration.csv` descrivono anche one-shot e oracle, ma il runner non legge quelle configurazioni come prove distinte. Per completare il confronto servono un harness che esegua one-shot e oracle con `analysis_service.run_analysis`, abbini le prove sulle stesse condizioni e salvi artefatti comparabili, oltre all'implementazione delle metriche comparative proposte nel [protocollo EDBT](edbt-conversational-benchmark.md). La CLI attuale non esegue automaticamente le tre configurazioni.

Il formato accettato è YAML (`.yaml`/`.yml`) o JSON. Ogni scenario richiede `id`, `initial_query`, `expected_initial_missing`, `clarifications` e `expected_mapping`. Le dimensioni (`I`, `D`, `L`, `Cb`, `Ce`, `Cp`) inizialmente assenti o ambigue sono associate a risposte simulate; SAGE sceglie quale chiarire e la CLI invia la risposta corrispondente. Il report include F1 del rilevamento iniziale e accuratezza della mappatura finale. Ogni scenario può anche avere `name`, `tags`, `expected_ids`, `repeats` e `options`; `reviewed_query` opzionale permette di simulare una modifica alla query mostrata in revisione. `--repeat` imposta il numero minimo di ripetizioni; un valore `repeats` maggiore sul singolo scenario prevale.

La cartella di output contiene `manifest.json`, `runs.jsonl` (una riga per prova con transcript completo user/assistant, domande, risposte, dimensioni bersaglio e stato della mappatura dopo ogni risposta, query raffinata, SQL e traccia agenti) e `summary.csv` (durata media, turni medi, F1 dei campi inizialmente mancanti, accuratezza della mappatura finale, numero medio di risultati ed eventuale recall rispetto a `expected_ids`). Il JSONL registra la conversazione osservabile e gli stati, non i prompt interni grezzi o il ragionamento privato del modello. `--resume` riprende una cartella esistente saltando le combinazioni modello/scenario/ripetizione già completate; il manifest verifica anche la concorrenza usata. I risultati sono accodati al JSONL quando ciascuna prova termina, così un'interruzione consente la ripresa.

La CLI richiede `backend/.env`, un provider LLM configurato e dataset accessibile tramite la configurazione del backend. Se manca il dataset demo locale, crearlo con `uv run python backend/data/metadata/create_demo_dataset.py`. La CLI risolve i percorsi relativi del backend rispetto alla directory `backend/`, anche quando viene invocata dalla root del repository. I risultati descrivono le esecuzioni fatte su quel setup; non sono da soli una replica dei benchmark del paper.

Per mantenere leggibile l'output, la CLI filtra alcuni warning ripetitivi e noti di LangGraph, pandas e delle chiamate `datetime.utcnow()` del backend, anche durante l'import iniziale di LangGraph; altri warning restano visibili.

Opzioni documentate per l'harness: `--with-qwen`, `--with-gemma`, `--all-models`. La directory `backend/tests/` ospita un **harness sperimentale**, non una suite pytest di unit test completa.

## Controlli per confronti attendibili

Registrare versione del dataset, query, modello/endpoint, prompt, condizioni di geocoding, mapping OSM, hardware e numero di prove. Se una tabella viene rigenerata **da log**, distinguere report derivato da una esecuzione effettiva.

[Vedi risultati](benchmarks.md), [limiti](limitations.md) e [verifica software](../operations/quality.md).
