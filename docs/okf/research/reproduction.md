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
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios/conversational_scenarios.yaml
  title: Scenari conversazionali EDBT
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios/README.md
  title: Descrizione e protocollo previsto degli scenari EDBT
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios_v2/README.md
  title: Benchmark EDBT a omissione controllata v2
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios_v2/conversational_scenarios.yaml
  title: Scenari v2 multi-turn consumabili dalla CLI
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios_v2/validate_missingness.py
  title: Validatore statico degli scenari v2
- resource: ../../../backend/experiments/reproduce_results.py
  title: 'MURENA repository: backend/experiments/reproduce_results.py'
- resource: ../../../backend/tests/test_suite.py
  title: 'MURENA repository: backend/tests/test_suite.py'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

> **Asset correnti (2026-11-17):** le directory `data/scenarios/` e
> `data/scenarios_v2/` sono state rimosse. I riferimenti e le osservazioni
> storiche sotto restano attribuiti alle versioni originarie; le fonti rimosse
> sono collegate alla revisione Git `411b003`. L'unica suite attiva è
> `backend/experiments/data/scenarios_v3/`; la sorgente originale è conservata
> byte per byte come `source_triplets.json` al suo interno. Le descrizioni
> storiche del runner solo conversazionale non descrivono la CLI corrente,
> che supporta refined, one_shot e oracle.


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
  --scenarios backend/experiments/data/scenarios_v3/conversational_scenarios.yaml \
  --output backend/experiments/results/edbt-conversational \
  --dataset full --repeat 1 --concurrency 2
```

La CLI usa il modello predefinito in `backend/.env` (`settings.LLM_MODEL`) e il dataset configurato come `full`. Richiede un provider LLM e il dataset configurato accessibile. Invoca direttamente `SageClarifier`, anche se `ENABLE_SAGE_CLARIFICATION` è disattivato nel server; le domande sono generate dal modello e la CLI simula le risposte e la conferma della query revisionata prima dell'analisi. Il benchmark usa esclusivamente l'inglese, fissato internamente dal runner; la lingua non è un'opzione né viene salvata nei metadati. `--repeat`, `--map-limit`, `--llm-limit`, `--use-relaxation/--no-use-relaxation`, `--resume`, `--retry-failed`, `--rerun-scenario` e `--concurrency` sono opzioni definite dal parser. La concorrenza predefinita è 2 run; usare `--concurrency 1` per esecuzione sequenziale o un valore maggiore solo se le quote del provider lo consentono. Il valore è registrato nel manifest e deve coincidere per riprendere una run; i manifest precedenti a questa opzione rappresentano run sequenziali e si riprendono con `--concurrency 1`. Per l'elenco corrente: `uv run python backend/experiments/benchmark_cli.py --help`.

Il file `backend/experiments/data/scenarios/conversational_scenarios.yaml` contiene le 24 istanze eseguibili originarie; la nuova famiglia da 40 casi è in `backend/experiments/data/scenarios_v2/conversational_scenarios.yaml`. I rispettivi file delle triplette e `queries_by_configuration.csv` descrivono anche one-shot e oracle, ma il runner non legge quelle configurazioni come prove distinte. Per completare il confronto servono un harness che esegua one-shot e oracle con `analysis_service.run_analysis`, abbini le prove sulle stesse condizioni e salvi artefatti comparabili, oltre all'implementazione delle metriche comparative proposte nel [protocollo EDBT](edbt-conversational-benchmark.md). La CLI attuale non esegue automaticamente le tre configurazioni.

Il formato accettato è YAML (`.yaml`/`.yml`) o JSON. Ogni scenario richiede `id`, `initial_query`, `expected_initial_missing`, `clarifications` e `expected_mapping`. Le dimensioni (`I`, `D`, `L`, `Cb`, `Ce`, `Cp`) inizialmente assenti o ambigue sono associate a risposte simulate; SAGE sceglie quale chiarire e la CLI invia la risposta corrispondente. Il report include F1 del rilevamento iniziale e accuratezza della mappatura finale. Ogni scenario può anche avere `name`, `tags`, `expected_ids`, `repeats` e `options`; `reviewed_query` opzionale permette di simulare una modifica alla query mostrata in revisione. `--repeat` imposta il numero minimo di ripetizioni; un valore `repeats` maggiore sul singolo scenario prevale. Nei 24 scenari EDBT originari `expected_ids` è assente, quindi la colonna di recall degli immobili attesi resta vuota; la nuova famiglia v2 ha lo stesso limite. Per la ragione e le implicazioni valutative vedere il [protocollo EDBT](edbt-conversational-benchmark.md).

### Famiglia a omissione controllata v2

La famiglia `backend/experiments/data/scenarios_v2/` aggiunge 40 casi conversazionali, otto per ciascun livello `k=1..5`, derivati da otto intenti completi. La dimensione `I` resta specificata; le omissioni annidate riguardano `D`, `L`, `Cb`, `Ce` e `Cp`. Otto controlli completi `k=0` sono in `zero_missing_controls.json`, ma non sono accettati dal runner perché richiede almeno una dimensione in `expected_initial_missing`. La famiglia non sostituisce i 24 casi precedenti.

Validazione statica e rigenerazione sono descritte in `backend/experiments/data/scenarios_v2/README.md`. Il validatore confronta il checksum del sorgente registrato nel manifest: dopo ogni modifica di `scenarios/scenario_triplets.json` occorre rigenerare la famiglia v2 prima di validarla. Al 2026-11-17 manifest e sorgente sono allineati e la validazione passa. Il runner accetta il YAML v2 e usa l'inglese fissato internamente; non passare `--language`.

`backend/experiments/analyze_conversational_results.py` aggrega una directory di output del runner senza chiamate al modello: rilevamento delle dimensioni mancanti (P/R/F1 micro, corrispondenza esatta, inclusi i run terminati senza turno), turni, accuratezza dello stato finale, `matched_use_cases` rispetto all'atteso, requisiti normativi vincolanti, stabilità tra ripetizioni, stratificati per `missing_count` (v2) o `category` (v1). Usa l'ultimo tentativo registrato per ogni coppia (scenario, ripetizione). Esempio dalla radice del repository:

```bash
python backend/experiments/analyze_conversational_results.py \
  --results backend/experiments/results/missingness_v2 \
  --triplets backend/experiments/data/scenarios_v3/scenario_triplets.json
```

Su Windows il provider `codex_exec` richiede le correzioni dell'adapter descritte in [chiarimento pre-analisi](../architecture/query-clarification.md); le variabili `LLM_PROVIDER`, `LLM_MODEL` e `CODEX_REASONING_EFFORT` possono essere passate come variabili d'ambiente del processo senza modificare `.env`.

Una prova end-to-end di `MS01_k1` con `gpt-6-luna` e dataset `full` è stata completata in 66.056 secondi: una run, zero errori, un turno di chiarimento, F1 di rilevamento iniziale 1.0, accuratezza mapping 1.0 e 147 risultati. È un controllo di funzionamento su un caso, non un benchmark comparativo né una stima di prestazione. Il set v2 non definisce `expected_ids`; non misura quindi la rilevanza o la qualità del ranking.

La cartella di output contiene `manifest.json`, `runs.jsonl`, la directory
`runs/` e `summary.csv`. Ogni nuovo `runs/<run_id>.json` usa
`artifact_schema_version=3` e JSON formattato con indentazione di due spazi. Conserva definizione
dello scenario, query, dialogo e stati conversazionali, tempi, errori e metriche.
`ranking_ids` contiene tutti gli ID corrispondenti, nell'ordine deterministico
finale prima del taglio `map_limit`, escludendo gli immobili di riempimento
non corrispondenti. L'orchestratore acquisisce la lista prima del taglio e
AnalysisService la rende disponibile al runner; filtri e ordinamento restano
quelli della pipeline esistente. `top` conserva solo ID, score e distanza dei
primi 10 matching restituiti, per le metriche esistenti e i pari merito.
`api_response` conserva solo output delle estrazioni e indicatori di
rilassamento/fallback/errori. Non vengono salvati `buildings`, contesto,
HTML, tracce con tutti gli immobili o dettagli dei ranking intermedi.
Questi nuovi artefatti non bastano a riprodurre le schede immobiliari nel
frontend: per i dettagli serve il dataset originale. I vecchi artefatti
(schema 2, con risposta API completa) restano leggibili e non sono riscritti.
Il manifest dichiara `run_artifact_schema_version=3` per le nuove scritture;
un batch ripreso può contenere entrambi i formati. L'indice resta schema 2,
autonomo per le metriche comparative, con gli stessi valori e campi.

`runs.jsonl` è l'indice append-only: una riga per run con ID, scenario, modello, ripetizione, stato, durata ed eventuale percorso dell'artefatto. `summary.csv` è ricalcolato leggendo gli artefatti disponibili e riporta per modello/scenario successi, errori, durata media, risultati medi, recall degli ID attesi, turni medi, accuratezza della mappatura e F1 medio delle dimensioni inizialmente mancanti. `manifest.json` registra scenario e checksum, modello, dataset, ripetizioni, versione Python e opzioni, inclusa la concorrenza. La lingua d'output non compare nei metadati. Scrittura atomica dei JSON e aggiornamento serializzato dell'indice riducono il rischio di artefatti parziali quando più run terminano insieme.

Per riprendere un batch interrotto, `--resume` salta una combinazione modello/scenario/ripetizione solo se il suo ultimo tentativo risulta `completed` e l'artefatto per-run esiste; errori e combinazioni mai iniziate vengono eseguiti. Anche le definizioni degli scenari possono essere cambiate: ogni versione resta separata nel riepilogo tramite hash. L'indice viene accodato quando ogni run termina, consentendo la ripresa e il ricalcolo del riepilogo dagli artefatti.

Per riprendere il batch interrotto usando l'output esistente:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios_v3/conversational_scenarios.yaml \
  --output backend/experiments/results/edbt_conversational \
  --dataset full --repeat 3 --concurrency 12 \
  --resume
```

`--retry-failed` è un filtro facoltativo da usare insieme a `--resume`: riesegue solo le combinazioni il cui ultimo tentativo indicizzato è `error`, senza avviare quelle mai iniziate. Modello, dataset, ripetizioni e opzioni runtime devono corrispondere al manifest precedente. L'inglese è fisso e non viene persistito. Per la compatibilità, il resume ignora il vecchio campo `output_language` eventualmente presente nei manifest precedenti. Ogni nuovo artefatto e la relativa riga d'indice registrano lo SHA-256 della singola definizione; per output precedenti privi dell'hash per run, il riepilogo lo ricava da `scenario_definition` nell'artefatto e, se manca, usa l'hash del manifest. Il riepilogo considera l'ultimo tentativo per combinazione modello/scenario/ripetizione; gli artefatti precedenti restano conservati e l'indice resta append-only. Il manifest mantiene la cronologia degli hash dell'intero file scenari.

Per rieseguire **tutte le ripetizioni di un singolo scenario** mantenendo cached gli altri, passare `--rerun-scenario` insieme a `--resume`:

```bash
uv run python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios_v3/conversational_scenarios.yaml \
  --output backend/experiments/results/edbt_conversational \
  --dataset full --repeat 3 --concurrency 12 \
  --resume --rerun-scenario UC08_student_grant_missing_use
```

L'opzione è ripetibile per selezionare più ID. Tutte le ripetizioni definite da `--repeat`/`repeats` vengono rilanciate anche se avevano già un artefatto completato; gli altri scenari restano cached, inclusi quelli pendenti o falliti. `--rerun-scenario` e `--retry-failed` sono alternative. Le nuove run hanno nuovi `run_id` e artefatti append-only; il manifest registra la selezione e il riepilogo mantiene separati gli hash delle definizioni. Per avere un batch composto solo dalla nuova versione dello scenario, usare una nuova directory di output.

La CLI richiede `backend/.env`, un provider LLM configurato e dataset accessibile tramite la configurazione del backend. Se manca il dataset demo locale, crearlo con `uv run python backend/data/metadata/create_demo_dataset.py`. La CLI risolve i percorsi relativi del backend rispetto alla directory `backend/`, anche quando viene invocata dalla root del repository. I risultati descrivono le esecuzioni fatte su quel setup; non sono da soli una replica dei benchmark del paper.

Per mantenere leggibile l'output, la CLI filtra alcuni warning ripetitivi e noti di LangGraph, pandas e delle chiamate `datetime.utcnow()` del backend, anche durante l'import iniziale di LangGraph; altri warning restano visibili.

Opzioni documentate per l'harness: `--with-qwen`, `--with-gemma`, `--all-models`. La directory `backend/tests/` ospita un **harness sperimentale**, non una suite pytest di unit test completa.

### Benchmark a tre condizioni (v3)

**Ordine del runner corrente:** rimosso `--seed` e il mescolamento dei job.
Le esecuzioni vengono avviate nell’ordine delle condizioni richieste, delle
varianti nel file e delle ripetizioni. Il parallelismo non garantisce lo
stesso ordine di completamento. I seed delle analisi statistiche offline
restano separati e invariati; i riferimenti storici al seed del runner
descrivono le esecuzioni precedenti.

**Selezione operativa corrente:** S01–S08 abilitati nel YAML del runner;
con tre ripetizioni per condizione il piano completo è di 1.536 job.
Il setup solo S01 descritto di seguito resta un esempio ridotto da 192 job.
YAML, JSON frontend e manifest di generazione sincronizzati. Dry-run verificato:
Tutte le condizioni si ripetono **tre volte**: `--repeat 3`, senza override
`--oracle-repeat` (che eredita `--repeat`). Dry-run verificato: 96 refined,
93 one-shot e 3 oracle, **192 job**. Nessuna esecuzione LLM avviata.

```bash
.venv/bin/python -u backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios_v3/conversational_scenarios.yaml \
  --output backend/experiments/results/s01_combinations \
  --condition refined --condition one_shot --condition oracle \
  --repeat 3 --concurrency 20
```

I conteggi con oracle ×5 riportati sotto descrivono il protocollo precedente,
non questa selezione operativa.

**Revisione combinatoria corrente:** `scenarios_v3/` contiene otto scenari
base S01–S08 con 32 varianti ciascuno. Il flag `enabled` compare solo sul
base, nel YAML con struttura `scenarios: [{id, enabled, variants}]`.
Il runner carica tutte le varianti delle basi attive ed esclude tutte quelle
delle basi disattivate, oracle incluso; flag sulle varianti sono rifiutati.
Rigenerare dopo aver modificato i flag YAML per sincronizzare il JSON della
demo; i flag base esistenti sono conservati. Tutte le otto basi sono
inizialmente abilitate: dry-run ×3/×3/×5 = 1.552 job, 194 per base.
Disabilitando S07: 1.358 job; abilitando solo S01: 194.
La nomenclatura delle varianti è `S01_k1_D`, `S01_k2_D_L`, ecc.; UC01–UC08
restano in `source_case_id` per provenienza. Usare una nuova directory output
(ad esempio `missingness_combinations`), distinta dai risultati MS.. storici.
Nessuna nuova esecuzione LLM è stata avviata. Il protocollo annidato con 304
job dei paragrafi storici sotto non descrive il catalogo corrente completo.

**Ultimo tentativo (2026-11-17, 15:18 UTC), interrotto su richiesta.**
I risultati precedenti in `missingness_v3/` sono stati cancellati su richiesta
e la stessa directory è stata ricreata per 304 job con `--concurrency 20`,
refined ×3, one-shot ×3, oracle ×5, seed 13 e gpt-6-luna/low.
Sono presenti quattro tentativi refined in errore per timeout Codex e nessun
run completato; gli altri job avviati non hanno prodotto un record finale.
Il manifest non contiene `completed_at`; non è un benchmark completato.
I risultati preliminari precedenti restano storici, recuperabili in Git alla
revisione `4a7c882`, e restano la fonte del paper corrente.
Il nuovo tentativo usa il dataset SHA-256
`d3956041f120b33de94d1b7b6bd1da1a07c11ded37b077056ef58efd47d4f6da`
e gli scenari SHA-256
`8396ffc8f85eab79ff2a8d09035dbe60026d386d48cb80b15050dc8ae329b837`:
questi checksum differiscono dal manifest storico importato; i due tentativi
non vanno mescolati o presentati come esecuzioni sugli stessi byte.

Diagnosi locale con Codex CLI 0.169.0: login ChatGPT valido e endpoint HTTPS
raggiungibile; la verifica minima standard non ha completato entro 30 secondi.
Una verifica con lo stesso modello e provider temporaneo `name="OpenAI"`,
`requires_openai_auth=true`, `wire_api="responses"`,
`supports_websockets=false` ha completato con `OK` (timeout diagnostico 45 s).
Gli override sono stati passati solo alla CLI, senza modificare `.env` o la
configurazione utente. Il confronto indica un problema del percorso WebSocket;
non verifica ancora il benchmark via HTTPS né dimostra che concorrenza 20 sia
sostenibile. Nessuna rigenerazione comparativa o nuova evidenza scientifica.

Dalla root del repository, senza modificare `backend/.env` (il provider è impostato via variabili d'ambiente del processo):

```bash
LLM_PROVIDER=codex_exec LLM_MODEL=gpt-6-luna CODEX_REASONING_EFFORT=low PYTHONIOENCODING=utf-8 \
uv run --project backend python backend/experiments/benchmark_cli.py \
  --scenarios backend/experiments/data/scenarios_v3/conversational_scenarios.yaml \
  --output backend/experiments/results/missingness_v3 \
  --condition refined --condition one_shot --condition oracle \
  --repeat 3 --oracle-repeat 5 --seed 13 --concurrency 4
uv run --project backend python backend/experiments/compare_conditions.py \
  --results backend/experiments/results/missingness_v3
```

Il piano è di 304 job: refined 144, one_shot 120, oracle 40. `--dry-run` li elenca senza eseguirli. Il resume viene rifiutato se cambiano condizioni, ripetizioni, impostazioni SAGE o LLM, opzioni o hash del dataset. `compare_conditions.py` scrive `comparison.json`, `comparison_per_k.csv` e `comparison_operational.csv`. I file completi `runs/<run_id>.json` restano locali; `runs.jsonl` contiene i campi necessari all'analisi.

**Dimensione degli artefatti storici (prima dello schema 3).** I file completi `runs/<run_id>.json` salvano tutti gli immobili restituiti, e i run one_shot con molte dimensioni omesse restituiscono quasi l'intero dataset: un singolo file arriva a 430 MB. Al 2026-11-17 `missingness_v3/runs` occupa 6,7 GB (122 file), `missingness_v2/runs` 1,0 GB e `edbt_conversational/runs` 296 MB; tutte queste directory sono escluse da git. Per l'analisi basta `runs.jsonl`. **Aggiornamento 2026-11-18:** su richiesta, le copie locali `missingness_v3/runs` (6,7 GB, 123 file) e `missingness_v2/runs` (1,0 GB, 120 file) sono state cancellate. Non erano in Git, quindi le risposte API complete per run di quelle serie non sono più disponibili. `runs.jsonl`, manifest e confronti restano recuperabili alle revisioni Git `4a7c882` (v3 parziale) e `411b003` (v2). Gli artefatti per run della serie Haiku sono invece versionati.

**Latenza delle CLI LLM (prova del 2026-11-17, ~15:45).**

- Prompt: estrazione JSON di requisiti da una richiesta nursery; 3 chiamate in sequenza e 6 in parallelo per ciascuna CLI.
- Codex era misurato mentre il benchmark ripreso era in esecuzione.

| CLI e modello | Media sequenziale | 6 in parallelo (totale) | Output valido |
|---|---|---|---|
| Claude Code CLI, `claude-haiku-5-5`, effort medium | 7,6 s | 9,5 s | 6/6 |
| Antigravity CLI (`agy`), `gemini-4-hydrogen-medium` | 8,4 s | 15,4 s | 6/6 |
| Grok Build CLI, `grok-4.7-build-fast`, effort medium | 10,7 s | 19,8 s | 6/6 |
| Codex CLI, `gpt-6-luna`, effort low | 84,4 s | 185,3 s | 6/6 |

Note sulla prova:

- Haiku a volte racchiude il JSON in un blocco di codice e arricchisce i valori (per esempio `use` con dettagli aggiuntivi).
- Al momento della prova il backend non aveva adattatori per queste CLI. Dal 2026-11-17 esiste il provider `claude_cli` (vedi sotto); Grok Build e Antigravity restano senza adattatore.
- Cambiare modello richiede una nuova serie completa: non si possono mescolare modelli nello stesso confronto.
- Una chiamata minima Codex richiedeva 12 s a benchmark fermo (15:30) e 63–167 s durante il rallentamento.

**Serie completa con Claude Haiku 5.5 (2026-11-17).** Riproduce il disegno annidato del paper, con il runner del commit `7fd238d` (seed 13, ordine interleaved). Con il runner corrente `--seed` non esiste più e l'ordine è fisso; i risultati per run non dipendono dall'ordine, ma il manifest differirebbe.

```bash
LLM_PROVIDER=claude_cli LLM_MODEL=claude-haiku-5-5 CLAUDE_CLI_EFFORT=medium uv run --project backend python backend/experiments/benchmark_cli.py   --scenarios backend/experiments/data/scenarios_v3/nested48_from_4a7c882.yaml   --output backend/experiments/results/missingness_v3_haiku   --condition refined --condition one_shot --condition oracle   --repeat 3 --oracle-repeat 5 --seed 13 --concurrency 10
uv run --project backend python backend/experiments/compare_conditions.py   --results backend/experiments/results/missingness_v3_haiku
```

- Requisiti: `claude` installato e autenticato; le variabili d'ambiente di processo bastano, senza modificare `backend/.env`.
- Tempi: 62 minuti per 304 run con concorrenza 10, cioè circa 5 run al minuto a regime.
- Ritmo misurato: circa 2 run al minuto con concorrenza 8 nei primi minuti, 5–6 al minuto a regime con concorrenza 10.
- Durata per run (mediana): chiarimento 16–49 s, analisi 88–124 s.
- Consumo: le chiamate usano la quota del piano Claude dell'utente. Il consumo in token non è stato misurato.

Problemi riscontrati con molte istanze CLI concorrenti su Windows, e correzioni:

- `WinError 32` nella pulizia della directory temporanea, che faceva fallire una chiamata già riuscita. Corretto con `ignore_cleanup_errors`, anche in `codex_exec`.
- Stdin arrivato oltre i 3 s di attesa del CLI ("no stdin data received"). Corretto passando l'input da file.
- Corruzione transitoria di `~/.claude.json` per avvii simultanei; il CLI la ripristina da `~/.claude/backups/`. Mitigata distanziando gli avvii di 0,3 s, ma non eliminata: 1 episodio nella serie finale, recuperato dal nuovo tentativo.
- Ritentativi dell'adattatore: fino a 2 per chiamate senza risultato o con errore riportato dal CLI; i timeout non vengono ritentati.
- JSON racchiuso in un blocco ```json. Il parser SAGE ora accetta esattamente un blocco recintato; il runner usa `safe_extract_json` per le tracce degli agenti.

Per compilare il paper si usa Tectonic 0.17.0 (binario dalla release GitHub; su Windows non è disponibile via winget). I font Libertinus richiesti da `acmart` vanno resi disponibili localmente se il bundle di Tectonic non li trova.

## Controlli per confronti attendibili

Registrare versione del dataset, query, modello/endpoint, prompt, condizioni di geocoding, mapping OSM, hardware e numero di prove. Se una tabella viene rigenerata **da log**, distinguere report derivato da una esecuzione effettiva.

[Vedi risultati](benchmarks.md), [limiti](limitations.md) e [verifica software](../operations/quality.md).

### Rigenerazione della suite attiva dopo la rimozione dei predecessori

```bash
uv run python backend/experiments/data/scenarios_v3/generate_missingness.py \
  --source backend/experiments/data/scenarios_v3/source_triplets.json \
  --output backend/experiments/data/scenarios_v3
uv run python backend/experiments/data/scenarios_v3/validate_missingness.py \
  --source backend/experiments/data/scenarios_v3/source_triplets.json \
  --catalog backend/docs/knowledge/normativa/normativa.json
```

Durante la rimozione è emerso un checksum sorgente già disallineato:
`d3dd298f33417d6c4a209b4041255fa89c2d077afcccf322a8e4655ceae035d7` nel manifest,
contro `7628197d0575f74752b3dc7e9af0e8dabc0f47a0f931339d91cf886d3045ce47`
del file originale corrente. La rigenerazione temporanea ha prodotto triplette
e YAML identici byte per byte ai file correnti: è stato aggiornato solo
`source_triplets_sha256`. Gli input e risultati del benchmark non cambiano.
I vecchi risultati versionati sono recuperabili dalla revisione Git `411b003`; le definizioni v2 e gli altri file
rimossi sono recuperabili dalla revisione Git `411b003`.

Nota di manutenzione (2026-11-17): le directory risultati
`edbt_conversational/` e `missingness_v2/` sono state eliminate dopo la
rimozione delle suite corrispondenti. I riferimenti a tali directory e le
misure riportate sopra sono storici; i file versionati sono recuperabili
alla revisione Git `411b003`. `missingness_v3/` resta invariata, senza
rigenerazione dei risultati. Gli artefatti locali non versionati eliminati
non sono recuperabili da Git.

### Prova singola Qwen vLLM — S01_k0 (2026-11-17)

Eseguito un solo job refined, una ripetizione, concorrenza 1, modello
`qwen9b` (`Qwen/Qwen3.5-9B`) su `http://130.192.163.76:8000/v1` via
provider `openai-compatible`. Impostazioni passate soltanto all'ambiente
del processo; `.env` invariato. Input isolato dalle selezioni del catalogo,
conservato in `backend/experiments/results/qwen9b_s01_k0/scenario_input.yaml`.
Artefatti nella stessa cartella: manifest, indice, JSON per-run, log e
`execution_settings.json` con endpoint e parametri della prova.

Run `bench_b709ce5268e6`: **errore dopo 122,083 s**, durante il chiarimento:
`Clarification model returned invalid JSON`. Nessuna analisi immobiliare
completata. Il contenuto grezzo della risposta LLM non è conservato, quindi
non si può attribuire con certezza la causa a thinking, Markdown o altri
contenuti. Nessun override thinking è stato passato dal provider per questo
IP; la precedente verifica HTTP minima aveva invece usato
`enable_thinking=false` e restituito `OK`. Sono prove tecniche distinte,
non un confronto di qualità o stabilità e non un risultato scientifico.
Nessun retry o secondo job avviato. Il paper resta invariato.

Snapshot `all_scenarios_codex` incluso nel commit di attivazione completa:
manifest con otto basi attive, gpt-6-luna, ×3 per tutte le condizioni,
concorrenza 20, senza `completed_at`. Al momento dello snapshot è presente
un solo record, `bench_a9c86f0197c9` / `S01_k1_D`, fallito dopo 8,836 s
per dettaglio necessario ancora irrisolto, senza avviare l’analisi.
È un artefatto parziale, non un benchmark completato o una nuova misura
comparativa. Nessuna modifica ai risultati storici del paper.

### Correzione del contesto SQL delle tipologie (2026-11-17)

Durante il batch Codex è stato segnalato un Binder Error su
`tipologia_bene_immobile`. Verificato sul Parquet locale: la colonna presente
è `property_type`, il vecchio nome è assente. L’orchestratore inseriva
ancora il vecchio nome nei requisiti passati all’agente SQL e cercava le
categorie nel percorso metadati obsoleto. Corretti nome nel contesto SQL,
lettura di `fields.property_type.values` e riepilogo iniziale del dataset.
Superati 15 test della pipeline senza LLM, incluso il confine building→SQL
con esecuzione DuckDB; verificato anche il filtro canonico sul Parquet.
Non è stata rieseguita una chiamata LLM per misurare l’effetto della correzione.
Un runner già attivo mantiene il codice caricato: per valutare la correzione
avviare un nuovo processo e usare output separati dai tentativi precedenti.
I risultati storici del paper restano invariati; la correzione ripristina il
contratto di schema della pipeline ereditata, senza cambiare il metodo.
