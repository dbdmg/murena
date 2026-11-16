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
  --dataset full --repeat 1 --concurrency 2
```

La CLI usa il modello predefinito in `backend/.env` (`settings.LLM_MODEL`) e il dataset configurato come `full`. Richiede un provider LLM e il dataset configurato accessibile. Invoca direttamente `SageClarifier`, anche se `ENABLE_SAGE_CLARIFICATION` è disattivato nel server; le domande sono generate dal modello e la CLI simula le risposte e la conferma della query revisionata prima dell'analisi. Il benchmark usa esclusivamente l'inglese: il runner fissa `output_language="en"` e non espone un'opzione lingua. `--repeat`, `--map-limit`, `--llm-limit`, `--use-relaxation/--no-use-relaxation`, `--resume`, `--retry-failed` e `--concurrency` sono opzioni definite dal parser. La concorrenza predefinita è 2 run; usare `--concurrency 1` per esecuzione sequenziale o un valore maggiore solo se le quote del provider lo consentono. Il valore è registrato nel manifest e deve coincidere per riprendere una run; i manifest precedenti a questa opzione rappresentano run sequenziali e si riprendono con `--concurrency 1`. Per l'elenco corrente: `uv run python backend/experiments/benchmark_cli.py --help`.

Il file `conversational_scenarios.yaml` contiene le 24 istanze eseguibili. Il file delle triplette e `queries_by_configuration.csv` descrivono anche one-shot e oracle, ma il runner non legge quelle configurazioni come prove distinte. Per completare il confronto servono un harness che esegua one-shot e oracle con `analysis_service.run_analysis`, abbini le prove sulle stesse condizioni e salvi artefatti comparabili, oltre all'implementazione delle metriche comparative proposte nel [protocollo EDBT](edbt-conversational-benchmark.md). La CLI attuale non esegue automaticamente le tre configurazioni.

Il formato accettato è YAML (`.yaml`/`.yml`) o JSON. Ogni scenario richiede `id`, `initial_query`, `expected_initial_missing`, `clarifications` e `expected_mapping`. Le dimensioni (`I`, `D`, `L`, `Cb`, `Ce`, `Cp`) inizialmente assenti o ambigue sono associate a risposte simulate; SAGE sceglie quale chiarire e la CLI invia la risposta corrispondente. Il report include F1 del rilevamento iniziale e accuratezza della mappatura finale. Ogni scenario può anche avere `name`, `tags`, `expected_ids`, `repeats` e `options`; `reviewed_query` opzionale permette di simulare una modifica alla query mostrata in revisione. `--repeat` imposta il numero minimo di ripetizioni; un valore `repeats` maggiore sul singolo scenario prevale.

La cartella di output contiene `manifest.json`, `runs.jsonl`, la directory `runs/` e `summary.csv`. Viene scritto un file JSON autonomo per ogni run, `runs/<run_id>.json`, così l'artefatto può essere usato in seguito per riprodurre nel frontend i dati restituiti dall'API. Il JSON contiene definizione dello scenario e ground truth, query iniziale e inviata, transcript user/assistant con le risposte simulate, stati e metriche conversazionali, durata, errori eventuali e `api_response` serializzata in forma JSON-safe. La risposta conserva l'intero array `buildings` con i campi e gli score restituiti dall'AnalysisService, oltre a località, filtri/SQL, sintesi broker, contesto e traccia degli agenti. La traccia contiene input e output registrati dagli agenti e può includere i prompt effettivamente inviati (`[SYSTEM]`/`[USER]`) e i metadati del dataset; la disponibilità dei dettagli dipende da ciò che il logger degli agenti registra.

`runs.jsonl` è l'indice append-only: una riga per run con ID, scenario, modello, ripetizione, stato, durata ed eventuale percorso dell'artefatto. `summary.csv` è ricalcolato leggendo gli artefatti disponibili e riporta per modello/scenario successi, errori, durata media, risultati medi, recall degli ID attesi, turni medi, accuratezza della mappatura e F1 medio delle dimensioni inizialmente mancanti. `manifest.json` registra scenario e checksum, modello, dataset, ripetizioni, versione Python e opzioni, inclusa la concorrenza. Scrittura atomica dei JSON e aggiornamento serializzato dell'indice riducono il rischio di artefatti parziali quando più run terminano insieme.

Per riprendere un batch interrotto, `--resume` salta una combinazione modello/scenario/ripetizione solo se il suo ultimo tentativo risulta `completed` e l'artefatto per-run esiste; errori e combinazioni mai iniziate vengono eseguiti. Anche le definizioni degli scenari possono essere cambiate: ogni versione resta separata nel riepilogo tramite hash. L'indice viene accodato quando ogni run termina, consentendo la ripresa e il ricalcolo del riepilogo dagli artefatti.

Per riprendere il batch interrotto usando l'output esistente:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios/conversational_scenarios.yaml \
  --output backend/experiments/results/edbt_conversational \
  --dataset full --repeat 3 --concurrency 12 \
  --resume
```

`--retry-failed` è un filtro facoltativo da usare insieme a `--resume`: riesegue solo le combinazioni il cui ultimo tentativo indicizzato è `error`, senza avviare quelle mai iniziate. Modello, dataset, ripetizioni e opzioni runtime devono corrispondere al manifest precedente. Il benchmark usa ora solo inglese. Nei manifest creati dalla versione precedente, `output_language="it"` è trattato come opzione storica e migrato al valore fisso `en` per consentire la ripresa; le nuove run e i nuovi artefatti registrano `en`. Il riepilogo separa le righe per lingua e hash dello scenario, per non aggregare output di configurazioni o definizioni diverse. Ogni nuovo artefatto e la relativa riga d'indice registrano lo SHA-256 della singola definizione; per output precedenti privi dell'hash per run, il riepilogo lo ricava da `scenario_definition` nell'artefatto e, se manca, usa l'hash del manifest. Nella stessa versione e lingua, il riepilogo considera l'ultimo tentativo per combinazione modello/scenario/ripetizione; gli artefatti precedenti restano conservati e l'indice resta append-only. Il manifest mantiene la cronologia degli hash dell'intero file scenari.

Nel caso di UC08, le ripetizioni già completate con la vecchia query restano cached; viene ripresa la ripetizione fallita con la definizione attuale. Per eseguire nuovamente tutte le ripetizioni con la nuova query e avere un batch omogeneo, usare una nuova directory di output.

La CLI richiede `backend/.env`, un provider LLM configurato e dataset accessibile tramite la configurazione del backend. Se manca il dataset demo locale, crearlo con `uv run python backend/data/metadata/create_demo_dataset.py`. La CLI risolve i percorsi relativi del backend rispetto alla directory `backend/`, anche quando viene invocata dalla root del repository. I risultati descrivono le esecuzioni fatte su quel setup; non sono da soli una replica dei benchmark del paper.

Per mantenere leggibile l'output, la CLI filtra alcuni warning ripetitivi e noti di LangGraph, pandas e delle chiamate `datetime.utcnow()` del backend, anche durante l'import iniziale di LangGraph; altri warning restano visibili.

Opzioni documentate per l'harness: `--with-qwen`, `--with-gemma`, `--all-models`. La directory `backend/tests/` ospita un **harness sperimentale**, non una suite pytest di unit test completa.

## Controlli per confronti attendibili

Registrare versione del dataset, query, modello/endpoint, prompt, condizioni di geocoding, mapping OSM, hardware e numero di prove. Se una tabella viene rigenerata **da log**, distinguere report derivato da una esecuzione effettiva.

[Vedi risultati](benchmarks.md), [limiti](limitations.md) e [verifica software](../operations/quality.md).
