---
type: Research Benchmark
title: Benchmark conversazionale EDBT
description: Definizione, copertura, protocollo e stato di riproducibilità degli scenari sintetici EDBT per il chiarimento delle query MURENA.
tags:
- research
- benchmark
- edbt
- conversational-clarification
sources:
- resource: ../../../backend/experiments/data/scenarios/README.md
  title: Descrizione degli scenari EDBT
- resource: ../../../backend/experiments/data/scenarios/scenario_triplets.json
  title: Triplette one-shot, conversational e oracle
- resource: ../../../backend/experiments/data/scenarios/conversational_scenarios.yaml
  title: Scenari multi-turn consumabili dalla CLI
- resource: ../../../backend/experiments/data/scenarios/queries_by_configuration.csv
  title: Query per le tre configurazioni
- resource: ../../../backend/experiments/data/scenarios/catalog_snapshot_sha256.txt
  title: Impronta dello snapshot normativo sorgente
- resource: ../../../backend/experiments/data/scenarios_v2/README.md
  title: Specifica della famiglia a omissione controllata v2
- resource: ../../../backend/experiments/data/scenarios_v2/scenario_triplets.json
  title: Triplette degli scenari v2
- resource: ../../../backend/experiments/data/scenarios_v2/conversational_scenarios.yaml
  title: Scenari v2 eseguibili dalla CLI
- resource: ../../../backend/experiments/data/scenarios_v2/generation_manifest.json
  title: Manifest di generazione v2
- resource: ../../../backend/experiments/data/scenarios_v2/validate_missingness.py
  title: Validatore statico v2
- resource: ../../../backend/experiments/benchmark_cli.py
  title: Runner per scenari conversazionali
- resource: ../../../backend/docs/knowledge/normativa/normativa.json
  title: Catalogo normativo del repository
- resource: ../references/paper/paper.tex
  title: Manoscritto originale MURENA
---

# Benchmark conversazionale EDBT

## Motivazione

Il paper originale MURENA valuta query iniziali sufficientemente specificate per il proprio protocollo. Il benchmark EDBT esplora una domanda distinta: se una conversazione multi-turno possa recuperare requisiti immobiliari assenti o disambiguare requisiti ambigui prima dell'analisi. Questa è una definizione sperimentale aggiuntiva e non modifica né replica i risultati pubblicati nel paper.

## Dataset e provenienza

Il dataset contiene **24 scenari** sintetici, rappresentati come triplette appaiate in `scenario_triplets.json`. Le tre forme sono: `one_shot` (query sottospecificata), `conversational` (query iniziale più risposte simulate) e `oracle` (query completa di riferimento). `queries_by_configuration.csv` appiattisce le 72 richieste, 24 per configurazione; per il caso conversational la query registrata è quella iniziale, non la riscrittura prodotta da SAGE.

Le categorie e il numero di scenari sono: omissione della destinazione d'uso (`missing_use`, 8); omissione di prossimità (`missing_proximity`, 3); omissione di vincoli edilizi/capienza (`missing_building`, 2); omissione energetica (`missing_energy`, 2); nessuna preferenza d'uso (`no_preference`, 2); uso ambiguo (`ambiguous_use`, 2); località ambigua (`ambiguous_location`, 1); località omessa (`missing_location`, 1); chiarimento multi-turno (`multi_turn`, 1); destinazione fuori catalogo (`negative_no_match`, 1); distinzione di ambito del contributo (`grant_scope_negative`, 1). La copertura comprende omissioni delle dimensioni `I`, `D`, `L`, `Cb`, `Ce`, `Cp`, ambiguità semantiche, casi negativi e distinzioni di applicabilità normativa.

La famiglia separata `backend/experiments/data/scenarios_v2/` contiene 40 casi di omissione controllata: otto casi per ciascun livello `k=1..5`, costruiti dagli otto intenti completi UC01–UC08. `I` resta sempre specificata; i cinque criteri `D`, `L`, `Cb`, `Ce` e `Cp` vengono omessi secondo maschere annidate, con ordine variabile tra gli intenti. Otto casi `k=0` sono conservati in `zero_missing_controls.json` come controlli, ma il runner corrente li rifiuta perché `expected_initial_missing` deve essere non vuoto. I 40 casi sono il formato compatibile con la condizione conversational, non una sostituzione dei 24 casi di robustezza originari.

Questa è una prova di stress a omissione controllata: ogni criterio omesso è trattato dagli autori come un requisito latente desiderato. Non misura rinunce volontarie o la distribuzione naturale dell'ambiguità. `queries_by_configuration.csv` contiene 120 righe che descrivono le condizioni one-shot, refined e oracle, ma la CLI esegue solo conversational; refined rappresenta l'avvio della conversazione, non una query già prodotta dal sistema.

La provenienza dichiarata nel README degli scenari è il bundle `murena-demo(4).zip` e il catalogo normativo in esso contenuto. `catalog_snapshot_sha256.txt` registra l'impronta dello snapshot normativo usato nella costruzione. Il validatore statico presente nella directory controlla coerenza strutturale e copertura rispetto al catalogo corrente. Queste tracce documentano la provenienza e la coerenza interna dei dati, **non** una validazione empirica con utenti o una verifica indipendente delle norme. I risultati delle esecuzioni effettivamente osservate sono riportati separatamente sotto.

## Configurazioni sperimentali

- **One-shot:** passare direttamente alla pipeline la query iniziale incompleta o ambigua.
- **Conversational:** avviare SAGE dalla stessa query iniziale, rispondere ai chiarimenti con le risposte simulate per dimensione, quindi sottoporre la query raffinata/revisionata effettivamente prodotta.
- **Oracle/Complete:** passare alla pipeline la query completa di riferimento. L'oracle è un riferimento sperimentale, non un output osservato del sistema.

Le triplette e il CSV definiscono le tre condizioni, ma `backend/experiments/benchmark_cli.py` implementa solo l'esecuzione conversational: carica scenari multi-turn, simula la conversazione SAGE e invoca `analysis_service.run_analysis` sulla query revisionata. Non esegue automaticamente one-shot e oracle né un confronto appaiato tra i risultati.

## Ground truth

Le intenzioni complete sono rappresentate dalla query oracle e dalle aspettative strutturate nelle triplette: dimensioni attese, stati iniziali/finali, eventuale destinazione d'uso abbinata, requisiti regolatori attesi e fatti/query di riferimento. Nella configurazione conversational, `initial_query` è la richiesta iniziale, `expected_initial_missing` elenca le dimensioni che si intendono non specificate, `clarifications` mappa dimensioni a risposte utente simulate e `expected_mapping` specifica gli stati finali attesi. Il runner usa tali risposte in base alle dimensioni bersaglio selezionate da SAGE. La query raffinata è generata dal sistema durante l'esecuzione e non va sostituita con quella oracle: farlo introdurrebbe leakage della ground truth.

Questa ground truth è una specifica costruita dagli autori degli scenari, non una verità osservata da utenti reali. Le risposte simulate rendono ripetibile l'input conversazionale ma non modellano la variabilità degli utenti.

## Copertura normativa

Gli otto record `use_case` attualmente presenti nel catalogo e coperti dagli scenari sono: micro-nursery; nursery; spring section; play space/baby parking; home-based nursery; senior day center; senior residential care (RSA); university student residence legata allo specifico contributo CDP/PNRR. Due casi negativi distinguono una destinazione fuori catalogo e l'assenza di una destinazione pianificata; un altro caso distingue lo studentato privato senza il contributo specifico.

Il catalogo contiene valori descritti come verificati o come linee guida, ma anche campi `not_verified`, ambiti metrici e condizioni. In particolare, le misure di superficie netta funzionale o di singoli locali non equivalgono a soglie minime di superficie lorda dell'intero immobile. Il catalogo corrente non definisce una soglia lorda generale (`minimum_gross_property_area_sqm` è nullo nei record coperti). I valori di superficie lorda inseriti nelle query sono preferenze esplicite dell'utente ipotetico, non requisiti dedotti dalla normativa.

La corrispondenza a un'etichetta `use_case`, l'ambito di applicazione di una regola e la preferenza dell'utente sono concetti distinti: un'etichetta può essere pertinente senza implicare che uno standard per contributi o una linea guida si applichi al caso; una preferenza dimensionale esplicita non diventa per questo un requisito legale. I riferimenti e gli status sono quelli documentati nel catalogo fornito dal repository; questo documento non attesta un controllo autonomo delle fonti ufficiali né la correttezza legale aggiornata.

## Protocollo di valutazione previsto

Per ciascun caso si prevede di eseguire le tre query con modello, dataset, configurazione degli agenti, limiti e condizioni comuni, salvando output strutturati, query effettivamente inviate, identificativi dei risultati, versioni e ripetizioni. Il confronto conversational deve usare la query prodotta dalla conversazione, non la query oracle. La valutazione proposta include: rilevamento delle dimensioni inizialmente mancanti; stato finale delle dimensioni; estrazione e conservazione dei requisiti atomici rispetto all'oracle; matching delle destinazioni d'uso; controllo dell'assenza di filtri SQL normativi lordi non giustificati; confronto di insiemi di candidati e top-5; numero di turni e durata.

Il confronto one-shot/conversational misura l'effetto dell'elicitazione interattiva con informazione aggiuntiva fornita dall'utente simulato. Non isola da solo il valore dell'interfaccia dialogica rispetto a un modulo statico che raccolga le stesse informazioni. Risultati vuoti in entrambe le condizioni non vanno conteggiati automaticamente come accordo perfetto.

## Metriche: implementazione e proposte

La CLI conversazionale implementa e riporta per la sola esecuzione conversational:

- precision, recall e **F1 del rilevamento iniziale** delle dimensioni mancanti rispetto a `expected_initial_missing`;
- accuratezza della mappatura finale degli stati rispetto alle chiavi di `expected_mapping`;
- numero di turni di chiarimento;
- durata end-to-end in secondi, che include chiarimento e analisi;
- conteggio dei risultati e, se `expected_ids` è valorizzato, precisione sui risultati restituiti e recall degli ID attesi. Il riepilogo CSV espone la recall media.

Nei 24 scenari eseguibili attuali `expected_ids` non è valorizzato: per questo `mean_expected_recall` resta vuota nel riepilogo. Le etichette normative e le query oracle descrivono l'intento e i vincoli, ma non assegnano ID di immobili attesi; non vanno trasformate automaticamente in ground truth dei candidati.

Anche nella famiglia v2 `expected_ids` non è valorizzato. La CLI può verificare il completamento dell'analisi e riportare il numero di risultati, ma non calcolare la recall di immobili attesi né stabilire se il ranking sia migliore.

Non sono implementati nel runner il **Requirement F1** su vincoli atomici, il **Top-5 Jaccard** tra condizioni, il punteggio di **use-case matching** rispetto alle aspettative per configurazione, il confronto delle query one-shot/oracle, né il controllo comparativo dei filtri SQL. Sono obiettivi del protocollo o metadati presenti negli scenari, non metriche già calcolate. La CLI non produce misure comparative di turn count o latency tra configurazioni.

## Risultati osservati: run conversational del 2026-11-16

Gli artefatti sono in `backend/experiments/results/edbt_conversational/` (`manifest.json`, `runs.jsonl`, `summary.csv`, `runs/*.json`): modello `gpt-6-luna` via `codex_exec`, dataset `full`, 3 ripetizioni per scenario, `map_limit=1000`, `llm_limit=10`, concorrenza 12. I valori sotto sono stati ricalcolati il 2026-11-17 con script ad hoc non versionati sui **72 run validi** (24 scenari × 3). Per UC08 sono considerati solo i run della definizione corrente (SHA `888d0f…`); sono esclusi i run su versioni precedenti dello scenario, incluso un errore.

| Metrica | Valore |
|---|---|
| Run completati | 72/72 |
| Rilevamento delle dimensioni inizialmente mancanti (micro) | P 1,00 · R 0,90 · F1 0,95 |
| Rilevamento esatto | 64/72 |
| Accuratezza dello stato finale | 1,00 |
| Turni di chiarimento | media 1,01, massimo 2 |
| `matched_use_cases` del RegulatoryAgent uguale all'atteso per la configurazione conversational | 65/72 |
| Requisiti normativi vincolanti prodotti dal RegulatoryAgent | 0/72 |
| Durata end-to-end | mediana 108,6 s (69,8–169,3 s) |
| Run con zero risultati | 0 (mediana 118 candidati) |
| SQL finale identica nelle 3 ripetizioni | 2/24 scenari |
| Jaccard medio dei top-5 tra ripetizioni | 0,58 (top-10: 0,64) |

Errori osservati:

- **Ambiguità d'uso non rilevate** (UC20, UC21, 0/6 run esatti): SAGE tratta l'uso come specificato e chiede solo la dimensione omessa. In UC21 il RegulatoryAgent associa tutti e cinque gli usi per l'infanzia. In UC20 l'uso RSA viene comunque associato, presumibilmente per la risposta sulla capienza ("residenti"), non per una disambiguazione.
- **UC19** (multi-turno): il secondo turno su `Cb` avviene in 1 run su 3.
- **UC22** (fuori catalogo): in 3/3 run il RegulatoryAgent associa erroneamente la residenza universitaria.
- **UC23**: 1 run su 3 non associa la residenza universitaria. L'applicabilità del contributo CDP/PNRR non è stata verificata separatamente.

Questi risultati riguardano solo la condizione conversational. Non permettono di stimare il beneficio del chiarimento finché one-shot e oracle non vengono eseguiti con le stesse impostazioni. La bassa stabilità tra ripetizioni va riportata insieme a qualsiasi confronto. Il fenomeno delle ambiguità non riconosciute è coerente con quanto riportato in letteratura (vedi [stato dell'arte](related-work.md)).

## Risultati osservati: famiglia v2 a omissione controllata, 2026-11-17

Run completo dei 40 scenari v2 con 3 ripetizioni (120 run): `gpt-6-luna` via `codex_exec` (reasoning `low`) su Windows, dataset `full` locale (89.200 immobili), `map_limit=1000`, `llm_limit=10`, concorrenza 4. Artefatti in `backend/experiments/results/missingness_v2/`; valori calcolati con `analyze_conversational_results.py`.

| k | Run (ok) | P | R | F1 | Rilevamento esatto | Turni medi | Durata mediana |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 24 (18) | 1,00 | 0,75 | 0,86 | 18/24 | 1,00 | 86 s |
| 2 | 24 (24) | 1,00 | 0,88 | 0,93 | 18/24 | 1,75 | 89 s |
| 3 | 24 (24) | 1,00 | 0,88 | 0,93 | 15/24 | 2,62 | 95 s |
| 4 | 24 (24) | 1,00 | 0,97 | 0,98 | 21/24 | 3,88 | 103 s |
| 5 | 24 (24) | 1,00 | 0,95 | 0,97 | 18/24 | 4,75 | 109 s |
| **Totale** | **120 (114)** | **1,00** | **0,92** | **0,96** | **90/120** | **2,89** | **97 s** |

Sui 114 run completati: accuratezza dello stato finale 1,00; `matched_use_cases` uguale all'atteso per la configurazione `refined` in 114/114; nessun requisito normativo vincolante (0/114); SQL finale identica nelle 3 ripetizioni in 11/38 scenari, Jaccard medio dei top-5 tra ripetizioni 0,69 (top-10 0,74). I 6 run non completati (`MS02_k1`, `MS07_k1`) sono terminati senza alcun turno di chiarimento.

Nessun falso positivo: tutte le 30 rilevazioni non esatte sono omissioni di `Cb` non riconosciute (30 dei 72 run in cui `Cb` è omessa). Le cause osservate nello stato iniziale del parser sono due:

- **Capienza nella destinazione d'uso** (24 run: MS02, MS07, MS08): la query omette la superficie ma mantiene, nel testo della destinazione, una capienza come "for 45 children" o "for 30 residents". SAGE classifica la capienza come `Cb` (comportamento documentato), quindi la considera specificata. È un disallineamento tra generatore v2 e definizione di `Cb`, non un errore del parser: va corretto nella costruzione degli scenari o nella definizione attesa.
- **Stato dell'immobile** (6 run: MS02, MS03, MS04): "existing building" o "existing unit" viene letto come vincolo edilizio specificato. È un'interpretazione discutibile del parser.

Il numero di turni cresce quasi linearmente con `k`, e la durata cresce di circa 5–6 secondi per dimensione omessa. Come per v1, la sola condizione conversational non stima il beneficio del chiarimento rispetto a one-shot e oracle.

## Famiglia v3 e protocollo a tre condizioni (2026-11-17)

**Scenari v3** (`backend/experiments/data/scenarios_v3/`): stessa struttura di v2 (8 intenti base, `k=0..5`, 48 scenari, 8 per livello), ma la capienza è spostata dal frammento `D` al frammento `Cb` ("…at least N sqm of gross floor area and capacity for X people.", con sostantivo neutro per non rivelare la destinazione). Così omettere `Cb` rimuove davvero il vincolo dalla query iniziale. Il validatore verifica che `D'` non contenga più la capienza. Le 6 mancate rilevazioni v2 dovute a "existing building/unit" non dipendono dal generatore e sono affrontate con la regola `Cb` del parser (vedere [chiarimento](../architecture/query-clarification.md)).

**Condizioni**, eseguite con la stessa pipeline e le stesse opzioni:

- `refined`: query iniziale `q0` con frammenti omessi, chiarimento SAGE con utente simulato, analisi sulla query rivista (tutti i 48 scenari, inclusi i controlli `k=0`).
- `one_shot`: `q0` analizzata direttamente, senza chiarimento (40 scenari con `k≥1`).
- `oracle`: query completa dell'intento base, analizzata direttamente; ripetuta 5 volte per stimare la variabilità intrinseca della pipeline.

L'oracle è un riferimento di query, non una ground truth sulla rilevanza degli immobili.

**Metriche** (`backend/experiments/compare_conditions.py`, senza chiamate LLM):

- Jaccard dei top-5 e RBO estrapolato con p=0,8 (Webber et al., 2010) di `one_shot` e `refined` rispetto all'oracle, mediati su tutte le coppie di ripetizioni.
- Tetto di rumore: gli stessi indici calcolati tra ripetizioni dell'oracle.
- Versione tie-aware: valore atteso su 1000 permutazioni casuali seminate all'interno dei gruppi a parità di score, oltre all'ordine servito.
- Concordanza dei filtri strutturati: atomi per dimensione (`D:use`, `L:city/radius`, `Cb:area/capacità`, `Ce:classe peggiore ammessa`, `Cp:categoria`, `I:tipologia`) estratti dagli agenti prima del rilassamento, confrontati con il riferimento a maggioranza stretta delle ripetizioni oracle. Si riportano F1, recall per dimensione e atomi inventati.
- Incertezza: bootstrap a cluster sugli 8 intenti base (B=10000, IC percentile 95%) e test esatto di sign-flip sulle differenze a livello di intento.
- Dati operativi: tasso di turni non necessari con `k=0`, completamento, turni e latenza separata tra chiarimento e analisi.

**Stato.** Smoke test reale del 2026-11-17 su `MS02`, una ripetizione per condizione, con `gpt-6-luna` via Codex: 4 run su 4 completati senza errori degli agenti e senza rilassamento.

- Il controllo `k=0` termina senza domande (`no_clarification=true`).
- `MS02_k2` rileva entrambe le omissioni, `Cb` compresa, in 2 turni e ottiene gli stessi 144 risultati dell'oracle.
- Il `one_shot` restituisce 10.006 risultati con top-5 diverso.

Questo è solo un controllo di funzionamento.

## Risultati osservati: benchmark v3 a tre condizioni, 2026-11-17 (parziale)

**Esecuzione.**

- Configurazione: `gpt-6-luna` via Codex CLI, `model_reasoning_effort=low`; dataset `full` (89.200 immobili); rilassamento attivo; seed 13; concorrenza 4. Commit del codice `61545ba`.
- Run pianificati: 304 (refined 144, one_shot 120, oracle 40). Il benchmark è stato **sospeso su richiesta dell'utente** dopo 113 run completati: 54 refined, 43 one_shot, 16 oracle, nessun fallimento.
- Nessun run è stato rieseguito o selezionato. Dati in `backend/experiments/results/missingness_v3/`: `runs.jsonl`, `manifest.json`, `comparison.json`, `comparison_per_k.csv`, `comparison_operational.csv`. Gli artefatti completi `runs/` restano locali.

**Copertura risultante.**

- Ogni cella (k, condizione) contiene 5–7 degli 8 intenti.
- L'intento `UC08` non ha run oracle.
- Il tetto di rumore oracle-vs-oracle si basa sui 5 intenti con almeno due ripetizioni oracle.
- I risultati sono quindi preliminari e gli intervalli larghi.

**Rallentamento del servizio Codex.** Tempi osservati (ora locale, finestre di 15 minuti per fine run):

| Finestra | Run completati | Durata mediana (s) | Analisi mediana (s) | Analisi max (s) | Chiarimento mediano (s) |
|---|---|---|---|---|---|
| 14:00 | 34 | 90 | 76 | 112 | 40 |
| 14:15 | 26 | 109 | 84 | 167 | 45 |
| 14:30 | 24 | 106 | 90 | 320 | 34 |
| 14:45 | 23 | 122 | 89 | 232 | 52 |
| 15:00 | 4 | 604 | 543 | 689 | 74 |
| 15:15 | 2 | 926 | 925 | 1111 | – |

Una chiamata minima di prova (`codex exec … "Reply with OK"`) ha richiesto 63 s alle 15:05 e 167 s alle 15:15.

- I log locali di Codex (`~/.codex/logs_2.sqlite`) non contengono avvisi o errori nell'ultima mezz'ora.
- Gli hook locali completano subito.
- La causa è dunque lato servizio o account; non è stata identificata più precisamente.
- Un'unica chiamata del RankingAgent è andata in timeout (registrata in `agent_errors`, pesi di default).
- Il rilassamento è scattato in 2 run (un oracle `UC03`, un refined `MS07_k2`).

**Chiarimento (refined, 54 run).**

- Rilevamento delle dimensioni omesse esatto in 54/54 (P/R/F1 micro = 1,00).
- Numero di turni uguale a `k` in tutti i run.
- Nessuna domanda nei controlli `k=0` (0/8).
- `mapping_accuracy` 1,0 e use case uguale all'atteso in tutti i run.
- La correzione v3 della capienza e la regola `Cb` del parser eliminano entrambe le cause di mancata rilevazione osservate in v2.

**Accordo con l'oracle** (media sugli intenti [IC 95% bootstrap a cluster], `k≥1` aggregato):

| Condizione | J5 | RBO (p=0,8, top-10) | J5 tie-aware |
|---|---|---|---|
| one_shot | 0,04 [0,00; 0,12] | 0,05 [0,00; 0,14] | 0,04 [0,00; 0,11] |
| refined | 0,73 [0,61; 0,85] | 0,74 [0,64; 0,83] | 0,70 [0,56; 0,83] |
| refined, k=0 | 0,86 [0,72; 0,97] | 0,84 [0,70; 0,95] | 0,82 [0,63; 0,97] |
| oracle vs oracle | 0,74 [0,34; 1,00] | 0,76 [0,37; 0,99] | 0,74 [0,34; 1,00] |
| Δ refined − one_shot | 0,70 [0,58; 0,84] | 0,72 [0,63; 0,83] | 0,67 [0,52; 0,83] |

Il test di sign-flip esatto su 7 intenti dà p=0,016 per tutti e tre gli indici. Per singolo `k` gli intenti sono 5–7 e p varia tra 0,06 e 0,25.

**Concordanza dei filtri** rispetto al riferimento a maggioranza stretta delle ripetizioni oracle:

- refined: F1 tra 0,99 e 1,00 a ogni `k`; atomi inventati rari (0,17 per run a k=2, 0,05 a k=4).
- one_shot: da 0,89 (k=1) a 0,00 (k=5).
- Δ aggregato 0,38 [0,24; 0,52].
- Auto-concordanza dell'oracle: F1 0,98.

**Dimensione dei risultati.** One_shot restituisce mediane da 1.075 immobili (k=1) all'intero dataset (k=5), contro 446 dell'oracle; refined restituisce 144–446.

**Latenza** (mediane):

- Chiarimento: 17 s a k=0, poi 29, 36, 41, 52 e 97 s da k=1 a k=5.
- Analisi: 74–104 s per refined, ~88 s per one_shot, 75 s per oracle.

**Interpretazione e cautele.**

- Con il chiarimento, la query rivista recupera i filtri dell'oracle e raggiunge un accordo con l'oracle sul top-5 paragonabile a quello tra due run dell'oracle stesso. Il divario residuo riflette quindi soprattutto la variabilità della pipeline; senza chiarimento, il top-5 non si sovrappone quasi mai.
- L'oracle è un riferimento di query, non un giudizio di rilevanza.
- L'utente simulato rivela esattamente i frammenti omessi: l'accordo refined-oracle è un limite superiore del recupero con utenti reali.
- Il tetto di rumore è molto variabile tra intenti: `UC03` ha accordo 0 tra due run oracle, `UC04` e `UC05` 1,0.
- Questi numeri non vanno combinati con quelli v1 o v2, ottenuti con versioni precedenti del codice e degli scenari.

## Limiti

Gli scenari sono sintetici e costruiti per coprire dimensioni, omissioni, ambiguità e casi normativi selezionati. Non costituiscono una user study e non rappresentano la distribuzione di richieste reali. Le risposte simulate e gli oracle riflettono scelte di costruzione del benchmark. Le run conversational documentate sopra sono risultati osservati su questo setup, ma non stimano il beneficio del chiarimento senza condizioni one-shot e oracle appaiate. La copertura normativa segue il catalogo fornito e non certifica autorizzazioni o aggiornamento giuridico. Il protocollo EDBT va mantenuto distinto dai risultati riportati nel paper originale.

Nel controllo di funzionamento del 2026-11-17, una singola run end-to-end `MS01_k1` è terminata con `gpt-6-luna` e dataset `full` in 66.056 secondi: zero errori, un turno, F1 iniziale 1.0 e accuratezza del mapping finale 1.0. La run ha restituito 147 risultati. Questo smoke test verifica un percorso eseguibile, ma non è una valutazione scientifica, una replica del paper o evidenza di stabilità sulle 40 istanze. Il 2026-11-17 i file v2 sono stati rigenerati nel repository: l'unica differenza è il checksum sorgente in `generation_manifest.json`, ora allineato a `scenario_triplets.json`. Il validatore statico è passato (40 scenari, 8 per ciascun `k=1..5`, 8 controlli `k=0`, 120 configurazioni, annidamento, testi, fonti, etichette e YAML) e `benchmark_cli.load_scenarios` carica i 40 casi. Nessun benchmark v2 completo è stato eseguito.

Per i comandi supportati e le lacune operative, vedere [riproduzione](reproduction.md); per i risultati dichiarati nel manoscritto, vedere [benchmark del paper](benchmarks.md).
