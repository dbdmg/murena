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
- resource: ../../../backend/experiments/data/scenarios_v2/README.md
  title: Benchmark EDBT a omissione controllata v2
- resource: ../../../backend/experiments/data/scenarios_v2/conversational_scenarios.yaml
  title: Scenari v2 multi-turn consumabili dalla CLI
- resource: ../../../backend/experiments/data/scenarios_v2/validate_missingness.py
  title: Validatore statico degli scenari v2
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

La CLI usa il modello predefinito in `backend/.env` (`settings.LLM_MODEL`) e il dataset configurato come `full`. Richiede un provider LLM e il dataset configurato accessibile. Invoca direttamente `SageClarifier`, anche se `ENABLE_SAGE_CLARIFICATION` è disattivato nel server; le domande sono generate dal modello e la CLI simula le risposte e la conferma della query revisionata prima dell'analisi. Il benchmark usa esclusivamente l'inglese, fissato internamente dal runner; la lingua non è un'opzione né viene salvata nei metadati. `--repeat`, `--map-limit`, `--llm-limit`, `--use-relaxation/--no-use-relaxation`, `--resume`, `--retry-failed`, `--rerun-scenario` e `--concurrency` sono opzioni definite dal parser. La concorrenza predefinita è 2 run; usare `--concurrency 1` per esecuzione sequenziale o un valore maggiore solo se le quote del provider lo consentono. Il valore è registrato nel manifest e deve coincidere per riprendere una run; i manifest precedenti a questa opzione rappresentano run sequenziali e si riprendono con `--concurrency 1`. Per l'elenco corrente: `uv run python backend/experiments/benchmark_cli.py --help`.

Il file `backend/experiments/data/scenarios/conversational_scenarios.yaml` contiene le 24 istanze eseguibili originarie; la nuova famiglia da 40 casi è in `backend/experiments/data/scenarios_v2/conversational_scenarios.yaml`. I rispettivi file delle triplette e `queries_by_configuration.csv` descrivono anche one-shot e oracle, ma il runner non legge quelle configurazioni come prove distinte. Per completare il confronto servono un harness che esegua one-shot e oracle con `analysis_service.run_analysis`, abbini le prove sulle stesse condizioni e salvi artefatti comparabili, oltre all'implementazione delle metriche comparative proposte nel [protocollo EDBT](edbt-conversational-benchmark.md). La CLI attuale non esegue automaticamente le tre configurazioni.

Il formato accettato è YAML (`.yaml`/`.yml`) o JSON. Ogni scenario richiede `id`, `initial_query`, `expected_initial_missing`, `clarifications` e `expected_mapping`. Le dimensioni (`I`, `D`, `L`, `Cb`, `Ce`, `Cp`) inizialmente assenti o ambigue sono associate a risposte simulate; SAGE sceglie quale chiarire e la CLI invia la risposta corrispondente. Il report include F1 del rilevamento iniziale e accuratezza della mappatura finale. Ogni scenario può anche avere `name`, `tags`, `expected_ids`, `repeats` e `options`; `reviewed_query` opzionale permette di simulare una modifica alla query mostrata in revisione. `--repeat` imposta il numero minimo di ripetizioni; un valore `repeats` maggiore sul singolo scenario prevale. Nei 24 scenari EDBT originari `expected_ids` è assente, quindi la colonna di recall degli immobili attesi resta vuota; la nuova famiglia v2 ha lo stesso limite. Per la ragione e le implicazioni valutative vedere il [protocollo EDBT](edbt-conversational-benchmark.md).

### Famiglia a omissione controllata v2

La famiglia `backend/experiments/data/scenarios_v2/` aggiunge 40 casi conversazionali, otto per ciascun livello `k=1..5`, derivati da otto intenti completi. La dimensione `I` resta specificata; le omissioni annidate riguardano `D`, `L`, `Cb`, `Ce` e `Cp`. Otto controlli completi `k=0` sono in `zero_missing_controls.json`, ma non sono accettati dal runner perché richiede almeno una dimensione in `expected_initial_missing`. La famiglia non sostituisce i 24 casi precedenti.

Validazione statica e rigenerazione sono descritte in `backend/experiments/data/scenarios_v2/README.md`. Il validatore confronta il checksum del sorgente: nel presente snapshot il checksum registrato nel manifest non corrisponde al file sorgente, quindi occorre rigenerare la famiglia prima che il comando di validazione passi. Il runner accetta il YAML v2 e usa l'inglese fissato internamente; non passare `--language`.

Una prova end-to-end di `MS01_k1` con `gpt-6-luna` e dataset `full` è stata completata in 66.056 secondi: una run, zero errori, un turno di chiarimento, F1 di rilevamento iniziale 1.0, accuratezza mapping 1.0 e 147 risultati. È un controllo di funzionamento su un caso, non un benchmark comparativo né una stima di prestazione. Il set v2 non definisce `expected_ids`; non misura quindi la rilevanza o la qualità del ranking.

La cartella di output contiene `manifest.json`, `runs.jsonl`, la directory `runs/` e `summary.csv`. Viene scritto un file JSON autonomo per ogni run, `runs/<run_id>.json`, così l'artefatto può essere usato in seguito per riprodurre nel frontend i dati restituiti dall'API. Il JSON contiene definizione dello scenario e ground truth, query iniziale e inviata, transcript user/assistant con le risposte simulate, stati e metriche conversazionali, durata, errori eventuali e `api_response` serializzata in forma JSON-safe. La risposta conserva l'intero array `buildings` con i campi e gli score restituiti dall'AnalysisService, oltre a località, filtri/SQL, sintesi broker, contesto e traccia degli agenti. La traccia contiene input e output registrati dagli agenti e può includere i prompt effettivamente inviati (`[SYSTEM]`/`[USER]`) e i metadati del dataset; la disponibilità dei dettagli dipende da ciò che il logger degli agenti registra.

`runs.jsonl` è l'indice append-only: una riga per run con ID, scenario, modello, ripetizione, stato, durata ed eventuale percorso dell'artefatto. `summary.csv` è ricalcolato leggendo gli artefatti disponibili e riporta per modello/scenario successi, errori, durata media, risultati medi, recall degli ID attesi, turni medi, accuratezza della mappatura e F1 medio delle dimensioni inizialmente mancanti. `manifest.json` registra scenario e checksum, modello, dataset, ripetizioni, versione Python e opzioni, inclusa la concorrenza. La lingua d'output non compare nei metadati. Scrittura atomica dei JSON e aggiornamento serializzato dell'indice riducono il rischio di artefatti parziali quando più run terminano insieme.

Per riprendere un batch interrotto, `--resume` salta una combinazione modello/scenario/ripetizione solo se il suo ultimo tentativo risulta `completed` e l'artefatto per-run esiste; errori e combinazioni mai iniziate vengono eseguiti. Anche le definizioni degli scenari possono essere cambiate: ogni versione resta separata nel riepilogo tramite hash. L'indice viene accodato quando ogni run termina, consentendo la ripresa e il ricalcolo del riepilogo dagli artefatti.

Per riprendere il batch interrotto usando l'output esistente:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios/conversational_scenarios.yaml \
  --output backend/experiments/results/edbt_conversational \
  --dataset full --repeat 3 --concurrency 12 \
  --resume
```

`--retry-failed` è un filtro facoltativo da usare insieme a `--resume`: riesegue solo le combinazioni il cui ultimo tentativo indicizzato è `error`, senza avviare quelle mai iniziate. Modello, dataset, ripetizioni e opzioni runtime devono corrispondere al manifest precedente. L'inglese è fisso e non viene persistito. Per la compatibilità, il resume ignora il vecchio campo `output_language` eventualmente presente nei manifest precedenti. Ogni nuovo artefatto e la relativa riga d'indice registrano lo SHA-256 della singola definizione; per output precedenti privi dell'hash per run, il riepilogo lo ricava da `scenario_definition` nell'artefatto e, se manca, usa l'hash del manifest. Il riepilogo considera l'ultimo tentativo per combinazione modello/scenario/ripetizione; gli artefatti precedenti restano conservati e l'indice resta append-only. Il manifest mantiene la cronologia degli hash dell'intero file scenari.

Per rieseguire **tutte le ripetizioni di un singolo scenario** mantenendo cached gli altri, passare `--rerun-scenario` insieme a `--resume`:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios/conversational_scenarios.yaml \
  --output backend/experiments/results/edbt_conversational \
  --dataset full --repeat 3 --concurrency 12 \
  --resume --rerun-scenario UC08_student_grant_missing_use
```

L'opzione è ripetibile per selezionare più ID. Tutte le ripetizioni definite da `--repeat`/`repeats` vengono rilanciate anche se avevano già un artefatto completato; gli altri scenari restano cached, inclusi quelli pendenti o falliti. `--rerun-scenario` e `--retry-failed` sono alternative. Le nuove run hanno nuovi `run_id` e artefatti append-only; il manifest registra la selezione e il riepilogo mantiene separati gli hash delle definizioni. Per avere un batch composto solo dalla nuova versione dello scenario, usare una nuova directory di output.

La CLI richiede `backend/.env`, un provider LLM configurato e dataset accessibile tramite la configurazione del backend. Se manca il dataset demo locale, crearlo con `uv run python backend/data/metadata/create_demo_dataset.py`. La CLI risolve i percorsi relativi del backend rispetto alla directory `backend/`, anche quando viene invocata dalla root del repository. I risultati descrivono le esecuzioni fatte su quel setup; non sono da soli una replica dei benchmark del paper.

Per mantenere leggibile l'output, la CLI filtra alcuni warning ripetitivi e noti di LangGraph, pandas e delle chiamate `datetime.utcnow()` del backend, anche durante l'import iniziale di LangGraph; altri warning restano visibili.

Opzioni documentate per l'harness: `--with-qwen`, `--with-gemma`, `--all-models`. La directory `backend/tests/` ospita un **harness sperimentale**, non una suite pytest di unit test completa.

## Controlli per confronti attendibili

Registrare versione del dataset, query, modello/endpoint, prompt, condizioni di geocoding, mapping OSM, hardware e numero di prove. Se una tabella viene rigenerata **da log**, distinguere report derivato da una esecuzione effettiva.

[Vedi risultati](benchmarks.md), [limiti](limitations.md) e [verifica software](../operations/quality.md).
