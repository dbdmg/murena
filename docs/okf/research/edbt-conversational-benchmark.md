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
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios/README.md
  title: Descrizione degli scenari EDBT
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios/scenario_triplets.json
  title: Triplette one-shot, conversational e oracle
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios/conversational_scenarios.yaml
  title: Scenari multi-turn consumabili dalla CLI
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios/queries_by_configuration.csv
  title: Query per le tre configurazioni
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios/catalog_snapshot_sha256.txt
  title: Impronta dello snapshot normativo sorgente
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios_v2/README.md
  title: Specifica della famiglia a omissione controllata v2
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios_v2/scenario_triplets.json
  title: Triplette degli scenari v2
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios_v2/conversational_scenarios.yaml
  title: Scenari v2 eseguibili dalla CLI
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios_v2/generation_manifest.json
  title: Manifest di generazione v2
- resource: https://github.com/dbdmg/murena/blob/411b003/backend/experiments/data/scenarios_v2/validate_missingness.py
  title: Validatore statico v2
- resource: ../../../backend/experiments/benchmark_cli.py
  title: Runner per scenari conversazionali
- resource: ../../../backend/docs/knowledge/normativa/normativa.json
  title: Catalogo normativo del repository
- resource: ../references/paper/paper.tex
  title: Manoscritto originale MURENA
---

> **Asset correnti (2026-11-17):** le directory `data/scenarios/` e
> `data/scenarios_v2/` sono state rimosse. I riferimenti e le osservazioni
> storiche sotto restano attribuiti alle versioni originarie; le fonti rimosse
> sono collegate alla revisione Git `411b003`. L'unica suite attiva è
> `backend/experiments/data/scenarios_v3/`; la sorgente originale è conservata
> byte per byte come `source_triplets.json` al suo interno. Le descrizioni
> storiche del runner solo conversazionale non descrivono la CLI corrente,
> che supporta refined, one_shot e oracle.


# Benchmark conversazionale EDBT

**Stato locale aggiornato (2026-11-17):** gli artefatti preliminari v3 descritti
più avanti sono stati cancellati su richiesta e restano recuperabili alla
revisione Git `4a7c882`. La rigenerazione con concorrenza 20 è stata interrotta
su richiesta: quattro errori di timeout, nessun run completato. La directory
`missingness_v3/` contiene ora soltanto questo tentativo incompleto, con
checksum di dataset e scenari diversi dal manifest storico importato.
Diagnosi e provenienza in [riproduzione](reproduction.md). Il tentativo non aggiunge risultati scientifici.

**Serie completa con Claude Haiku 5.5 (2026-11-17, sera):** il disegno annidato
a 48 varianti è stato rieseguito per intero (304/304 run completati) con il
provider `claude_cli`, in `results/missingness_v3_haiku/`. Da questa serie
provengono ora i risultati del paper; la serie parziale `gpt-6-luna` resta
documentata sotto come evidenza storica, senza combinarla. Vedere
[serie Haiku](#risultati-osservati-serie-completa-v3-con-claude-haiku-55-2026-11-17).

## Revisione combinatoria del catalogo (2026-11-17)

Il catalogo corrente contiene otto scenari base **S01–S08**, ognuno con
32 varianti: tutti i sottoinsiemi di `D,L,Cb,Ce,Cp`, con `I` sempre presente.
Distribuzione totale delle 256 varianti per `k=0..5`: **8, 40, 80, 80, 40, 8**.
La revisione corrente `all_combinations_base_enabled_v2` sostituisce la
selezione per singola maschera introdotta nella precedente revisione locale.

`enabled` esiste **solo sullo scenario base** nel file
`conversational_scenarios.yaml`, strutturato come `scenarios` contenente gruppi
con `id`, `enabled`, `variants`. Per esempio, `S01: enabled=true` include
tutte le sue 32 varianti; `S07: enabled=false` le esclude tutte e non genera
oracle per S07. I flag sulle varianti sono rifiutati. I vecchi input piatti
senza flag restano supportati. La rigenerazione conserva i flag base e li
sincronizza nel JSON raggruppato della demo; il frontend mostra solo varianti
degli scenari attivi. Nessuna selezione indipendente delle maschere.

Le varianti hanno ID espliciti come `S01_k0`, `S01_k1_D`, `S01_k2_D_L`;
`base_case_id` è S01–S08 e `source_case_id` conserva UC01–UC08 della sorgente.
I riferimenti MS01–MS08 nelle osservazioni e nel paper restano storici.
Il manifest conserva la mappa fra nuove etichette e sorgenti originali.

Tutti gli otto scenari base sono inizialmente abilitati: con ×3 refined,
×3 one-shot e ×5 oracle si pianificano **1.552 job**, **194 per scenario base**.
Disabilitare S07 lascia sette basi e 1.358 job. Usare una nuova directory
output: ID e formato della definizione cambiano rispetto ai tentativi storici.
`--rerun-scenario S01` seleziona tutte le sue varianti e l'oracle senza
prevalere su un flag disabilitato.

Il catalogo esteso **non è stato eseguito**: validazione statica, test,
simulazione frontend e dry-run non aggiungono risultati LLM. Il paper
descrive la successiva generazione v4 come framework e mantiene la serie
cooperativa come evidenza riportata; le misure storiche restano separate.
Le sezioni seguenti preservano la provenienza storica.

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
- Run pianificati: 304 (refined 144, one_shot 120, oracle 40).
- Prima esecuzione (13:59–15:20): **sospesa su richiesta dell'utente** dopo 113 run completati (54 refined, 43 one_shot, 16 oracle), nessun fallimento.
- Ripresa con `--resume` e concorrenza 6 (15:32–15:58), **fermata su richiesta dell'utente**. Ha aggiunto 10 run: un one_shot e un oracle completati, 8 refined falliti con `Codex CLI LLM call timed out` durante il chiarimento (durate 255–742 s; `MS05_k3`, `MS06_k2`, `MS01_k1`, `MS03_k4`, `MS03_k2`, `MS04_k1`, `MS08_k4`, `MS02_k2`).
- Totale: 123 run eseguiti, 115 completati (54 refined, 44 one_shot, 17 oracle) e 8 falliti. I fallimenti sono contati e non imputati. Le metriche sotto usano i 115 completati; rispetto ai primi 113 cambiano solo il tetto RBO, il Δ di J5 a k=5 e il Δ dei filtri.
- Nessun run è stato rieseguito o selezionato. Dati in `backend/experiments/results/missingness_v3/`: `runs.jsonl`, `manifest.json`, `comparison.json`, `comparison_per_k.csv`, `comparison_operational.csv`. Gli artefatti completi `runs/` erano solo locali e sono stati cancellati su richiesta il 2026-11-18; restano i file versionati.

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

**Accordo con l'oracle.** Valori: media sugli intenti [IC 95% bootstrap a cluster], `k≥1` aggregato. Le righe `one_shot` e `refined` sono medie appaiate (`row_type=intent_mean_paired` in `comparison_per_k.csv`): per ogni intento si mediano solo i livelli con entrambe le condizioni, poi si mediano i 7 intenti comuni. Con questa definizione la differenza tra le due righe coincide con Δ. Nella prima stesura la riga refined usava tutti i livelli disponibili: 0,73 / 0,74 / 0,70.

| Condizione | J5 | RBO (p=0,8, top-10) | J5 tie-aware |
|---|---|---|---|
| one_shot | 0,04 [0,00; 0,12] | 0,05 [0,00; 0,14] | 0,04 [0,00; 0,11] |
| refined | 0,74 [0,62; 0,86] | 0,78 [0,67; 0,88] | 0,71 [0,57; 0,85] |
| refined, k=0 | 0,86 [0,72; 0,97] | 0,84 [0,70; 0,95] | 0,82 [0,63; 0,97] |
| oracle vs oracle | 0,74 [0,34; 1,00] | 0,75 [0,37; 0,97] | 0,74 [0,34; 1,00] |
| Δ refined − one_shot | 0,70 [0,58; 0,83] | 0,72 [0,63; 0,83] | 0,67 [0,52; 0,83] |

Il test di sign-flip esatto su 7 intenti dà p=0,016 per tutti e tre gli indici. Per singolo `k` gli intenti sono 5–7 e p varia tra 0,06 e 0,25.

**Concordanza dei filtri** rispetto al riferimento a maggioranza stretta delle ripetizioni oracle:

- refined: F1 tra 0,99 e 1,00 a ogni `k` (media appaiata 1,00 [0,99; 1,00]); atomi inventati rari (0,17 per run a k=2, 0,05 a k=4).
- one_shot: da 0,89 (k=1) a 0,00 (k=5) (media appaiata 0,56 [0,43; 0,70]).
- Δ aggregato 0,44 [0,30; 0,56] (0,38 [0,24; 0,52] sui primi 113 run).
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

## Risultati osservati: serie completa v3 con Claude Haiku 5.5 (2026-11-17)

> **Superata (2026-11-18).** La serie è stata eseguita sul codice `7fd238d` (dirty), che precede la correzione di pipeline `0e29b52` (markdeluk, 2026-11-17 18:37). Prima di quella correzione `graph_agent.py` leggeva la colonna `tipologia_bene_immobile`, che nel dataset si chiama `property_type`, quindi passava all'agente edilizio un elenco di tipologie vuoto.
>
> Effetto osservato: un atomo `I:typology` compare in 24 run oracle su 40 e in 83 refined su 144. Nella serie "utente imperfetto" su codice `c7b9f7a` compare in 40 oracle su 40 e in 224 refined su 224, e lì J5 oracle-oracle vale 0,94 [0,88; 0,98] contro 0,53.
>
> I confronti interni della serie restano coerenti, perché tutte le condizioni condividono lo stesso codice. Il tetto di rumore e i valori assoluti riflettono però il difetto. Su decisione dell'utente, la serie viene rieseguita sul codice corrente in `missingness_v3_haiku_r2`. I numeri sotto sono conservati come evidenza storica.
>
> Rerun completato (304/304, codice `a5c1b09`): vedere [la sezione 2026-11-18](#risultati-osservati-serie-v3-haiku-rieseguita-sul-codice-corrente-2026-11-18).
>
> Nota sulla temperatura: il valore 0 registrato nel manifest non viene applicato, perché l'adattatore `claude_cli` non lo passa alla CLI, che non ha un'opzione per la temperatura. Il campionamento è quello predefinito della CLI.

**Esecuzione.**

- Configurazione:
  - modello `claude-haiku-5-5` tramite il provider `claude_cli` (Claude Code CLI, effort `medium`; la temperatura 0 registrata non è applicata, vedi nota sopra);
  - dataset `full` (89.200 immobili, SHA-256 `bc6732c8…`), rilassamento attivo;
  - seed 13 con ordine dei job interleaved, concorrenza 10;
  - ripetizioni: refined ×3, one_shot ×3 (k≥1), oracle ×5 per intento.
- Input: `backend/experiments/data/scenarios_v3/nested48_from_4a7c882.yaml`, copia byte per byte del file runner annidato a 48 varianti del commit `4a7c882`, cioè lo stesso disegno della serie parziale. Il catalogo corrente S01–S08 non è stato usato.
- Codice: commit `7fd238d`. Il manifest riporta `dirty=true` perché il file di input non era ancora versionato al lancio; è stato pubblicato subito dopo, senza modifiche (`1bc396f`). Il runner usato è precedente alla rimozione di seed e interleaving (`3e118f5`).
- Esecuzione dalle 17:26 alle 18:28 (ora locale, 62 minuti): **304/304 run completati**, nessun run fallito, nessun `agent_errors`, nessun fallback.
- Rilassamento in 28 run: 19 refined, 3 one_shot, 6 oracle.
- Robustezza del CLI: 1 nuovo tentativo dell'adattatore, per una corruzione transitoria di `~/.claude.json` tra processi concorrenti; il file è risultato integro a fine run.
- Artefatti `runs/` compatti (schema 3): 304 file, 19 MB, il più grande 704 KB. Sono **versionati in Git**, come `runs.jsonl`, `manifest.json`, `summary.csv` e `comparison*.{json,csv}`. Prima del caricamento è stato controllato che non contengano email, chiavi, token o percorsi utente.

**Tentativi precedenti scartati.** Tre lanci della stessa serie, fermati prima di completarla e spostati fuori dal repository, non sono usati:

1. 11 run: errori `WinError 32` nella pulizia della directory temporanea, che facevano fallire agenti con una risposta valida.
2. 11 run: un fallimento di avvio del CLI senza diagnostica.
3. 46 run, con il catalogo corrente nel frattempo cambiato in S01–S08: 2 dialoghi SAGE falliti perché Haiku racchiude talvolta il JSON in un blocco ```json, e ritardi dello stdin.

Ciascun problema è stato corretto nel codice (`fc8496d`, `7fd238d`) prima del lancio definitivo, che è ripartito da zero.

**Chiarimento (refined, 144 run).**

- Rilevamento delle dimensioni omesse esatto in 144/144 (P/R/F1 micro = 1,00).
- Numero di turni uguale a `k` in tutti i run.
- Nessuna domanda nei controlli `k=0` (0/24).
- L'uso normativo atteso è sempre tra quelli riconosciuti; in 12 run è riconosciuto anche un uso affine. Per `MS02` (nido) compare anche il micronido in 11 run; per `MS01` (micronido) compare anche il nido in famiglia in 1 run.

**Accordo con l'oracle.** Valori: media appaiata sugli 8 intenti (`row_type=intent_mean_paired`), [IC 95% bootstrap a cluster, B=10.000], k≥1 aggregato.

| Condizione | J5 | RBO (p=0,8, top-10) | J5 tie-aware |
|---|---|---|---|
| one_shot | 0,11 [0,05; 0,18] | 0,13 [0,06; 0,20] | 0,11 [0,05; 0,17] |
| refined | 0,57 [0,49; 0,66] | 0,63 [0,54; 0,74] | 0,56 [0,49; 0,63] |
| refined, k=0 | 0,64 [0,58; 0,71] | 0,69 [0,62; 0,79] | 0,64 [0,57; 0,70] |
| oracle vs oracle (n=8) | 0,53 [0,43; 0,64] | 0,58 [0,47; 0,71] | 0,52 [0,43; 0,62] |
| Δ refined − one_shot | 0,46 [0,36; 0,56] | 0,49 [0,39; 0,61] | 0,45 [0,36; 0,54] |

- Sign-flip esatto su 8 intenti: p=0,0078 per tutti gli indici aggregati. È il minimo ottenibile con 8 intenti, cioè tutti gli intenti hanno Δ>0.
- Per singolo `k`, p=0,0078 da k=2 a k=5. A k=1 p=0,0625: one_shot conserva ancora gran parte dei filtri.
- J5 refined è stabile su k (0,60; 0,57; 0,55; 0,57; 0,56 da k=1 a k=5). J5 one_shot scende: 0,34; 0,13; 0,05; 0,02; 0,01.

**Concordanza dei filtri** rispetto al riferimento a maggioranza stretta delle ripetizioni oracle:

- refined: F1 tra 0,95 e 0,96 a ogni `k` (media appaiata 0,96 [0,94; 0,97]).
- one_shot: da 0,87 (k=1) a 0,19 (k=5) (media appaiata 0,55 [0,51; 0,59]).
- Δ aggregato 0,40 [0,36; 0,44].
- Auto-concordanza dell'oracle: F1 0,94 [0,93; 0,96].
- Il richiamo dell'atomo `I` nel refined è 0,44–0,83, mentre tutte le altre dimensioni hanno richiamo 0,98–1,00; la causa non è stata analizzata.

**Dimensione dei risultati (mediane).**

- oracle: 121 immobili.
- refined: 78–362.
- one_shot: 247 (k=1), 748, 2.476, 10.923, fino a 80.447 (k=5).

**Latenza (mediane).**

- Chiarimento: 16,5 s a k=0, poi 23,6; 29,8; 35,6; 38,3; 48,7 s da k=1 a k=5.
- Analisi: 88–102 s per refined, 88–124 s per one_shot, 92,5 s per oracle.

**Confronto con la serie parziale `gpt-6-luna`** (solo qualitativo, da non combinare):

- Entrambe le serie mostrano rilevamento esatto, nessuna domanda superflua a k=0 e un ampio Δ refined − one_shot.
- Con Haiku i livelli assoluti di accordo sono più bassi (J5 refined 0,57 contro 0,74). Anche il tetto oracle-vs-oracle è più basso (0,53 contro 0,74): la pipeline con Haiku varia di più tra ripetizioni identiche.
- In entrambe le serie refined è al livello del rispettivo tetto, entro gli intervalli.
- Il confronto fra modelli è confuso con la copertura: la serie parziale ha 7 intenti appaiati e il tetto su 5 intenti.

**Interpretazione e cautele.** Valgono quelle della serie parziale:

- l'oracle è un riferimento di query, non un giudizio di rilevanza;
- l'utente simulato è cooperativo ed esatto, quindi l'accordo refined-oracle è un limite superiore del recupero con utenti reali;
- `k` è accoppiato all'identità delle dimensioni omesse.

Refined supera di poco il tetto oracle-vs-oracle (0,57 contro 0,53), con intervalli sovrapposti; non va letto come "migliore dell'oracle". Il riferimento confronta coppie refined-oracle, il tetto coppie oracle-oracle: entrambi misurano la stessa variabilità della pipeline.

## Risultati osservati: serie v3 Haiku rieseguita sul codice corrente (2026-11-18)

Riesecuzione della serie precedente sul codice successivo alla correzione della colonna tipologia (`0e29b52`). Sostituisce come evidenza corrente la serie `missingness_v3_haiku` del 2026-11-17, che resta evidenza storica e **non va combinata** con questa.

**Configurazione.**

- Modello `claude-haiku-5-5` tramite il provider `claude_cli` (Claude Code CLI, effort `medium`). La temperatura 0 registrata nel manifest non è applicata, come nella serie precedente.
- Dataset `full` (89.200 immobili, SHA-256 `bc6732c8…`, invariato), rilassamento attivo, concorrenza 10.
- Ripetizioni: refined ×3, one_shot ×3 (k≥1), oracle ×5 per intento.
- Input: lo stesso `nested48_from_4a7c882.yaml` della serie precedente (SHA-256 `be783d82…`).
- Codice: `a5c1b09`. Il manifest registra `659f97f` per il primo segmento e `4071a3a` per la ripresa, entrambi `dirty=true`. Nessuno dei due differisce da `a5c1b09` sotto `backend/`, esclusi i risultati (verificato con `git diff`). Il manifest non contiene i campi di provenienza introdotti da `62630c0` (per esempio `temperature_applied`), coerentemente con il codice `a5c1b09`.
- Ordine dei job fisso, non interleaved: il runner corrente non ha `--seed`. Ordinati per avvio, i run sono 144 refined, poi 120 one_shot, poi 40 oracle. Le condizioni sono quindi eseguite in finestre temporali diverse, a differenza della serie precedente.

**Esecuzione** (ora locale, UTC+1).

- Lanciata verso le 04:10; il computer è andato in sospensione e il primo run registrato è partito alle 07:05.
- Sospesa alle 07:25 per lo spegnimento, con 117 run registrati.
- Ripresa con `--resume` alle 08:45, stessa configurazione; fine alle 09:14 (`completed_at` del manifest).
- **304/304 run completati**: 144 refined, 120 one_shot, 40 oracle. Nessun run fallito, nessun `agent_errors`, nessun fallback, nessun run con zero risultati.
- Dati versionati in `backend/experiments/results/missingness_v3_haiku_r2/`: `runs.jsonl`, `manifest.json`, `summary.csv`, `comparison.json`, `comparison_per_k.csv`, `comparison_operational.csv` e gli artefatti compatti `runs/` (304 file, 16 MB, il più grande 1,1 MB).
- Analisi: `compare_conditions.py` con le impostazioni predefinite (1000 permutazioni, B=10.000, seed 13, p=0,8, maggioranza stretta delle ripetizioni oracle). Nessun run escluso.

**Atomi di tipologia.** Un atomo `I:typology` (da `filter_atoms`) compare in 144/144 run refined, 120/120 one_shot e 40/40 oracle. Nella serie precedente: 83/144, 100/120 e 24/40.

**Chiarimento (refined, 144 run).**

- Rilevamento delle dimensioni omesse esatto in 144/144 (360 VP, 0 FP, 0 FN; P/R/F1 micro = 1,00).
- Numero di turni uguale a `k` in 144/144; stato finale `READY` e `mapping_accuracy` 1,0 in tutti i run.
- Nessuna domanda nei controlli `k=0` (0/24).
- L'uso normativo atteso è sempre tra quelli riconosciuti (144/144). In 9 run, tutti di `MS02` (nido), è riconosciuto anche il micronido; in uno di questi anche la sezione primavera.

**Accordo con l'oracle.** Valori: media appaiata sugli 8 intenti (`row_type=intent_mean_paired`), [IC 95% bootstrap a cluster, B=10.000], k≥1 aggregato. Tutti gli 8 intenti sono presenti in ogni cella.

| Condizione | J5 | RBO (p=0,8, top-10) | J5 tie-aware |
|---|---|---|---|
| one_shot | 0,16 [0,07; 0,25] | 0,20 [0,10; 0,30] | 0,15 [0,07; 0,24] |
| refined | 0,88 [0,81; 0,96] | 0,94 [0,90; 0,97] | 0,87 [0,79; 0,95] |
| refined, k=0 | 0,87 [0,77; 0,95] | 0,94 [0,89; 0,97] | 0,86 [0,76; 0,95] |
| oracle vs oracle (n=8) | 0,87 [0,79; 0,95] | 0,94 [0,89; 0,98] | 0,85 [0,76; 0,94] |
| Δ refined − one_shot | 0,72 [0,63; 0,82] | 0,74 [0,65; 0,82] | 0,72 [0,63; 0,82] |

- Sign-flip esatto su 8 intenti: p=0,0078 per tutti gli indici aggregati, il minimo ottenibile con 8 intenti (tutti con Δ>0).
- Per singolo `k`: p=0,0078 da k=2 a k=5; a k=1 p=0,0625 per J5 e J5 tie-aware, p=0,023 per RBO.
- J5 refined per `k` (da 1 a 5): 0,88; 0,85; 0,87; 0,90; 0,90. J5 one_shot: 0,50; 0,15; 0,08; 0,05; 0,01.
- L'RBO tie-aware (non nella tabella) vale 0,86 [0,81; 0,91] per refined, 0,18 [0,08; 0,27] per one_shot e 0,86 [0,81; 0,91] oracle-oracle.

**Concordanza dei filtri** rispetto al riferimento a maggioranza stretta delle ripetizioni oracle:

- refined: F1 tra 0,98 e 0,99 a ogni `k` (0,98 anche a k=0); media appaiata 0,98 [0,96; 1,00].
- one_shot: 0,88 (k=1), 0,77, 0,63, 0,49, 0,27 (k=5); media appaiata 0,61 [0,57; 0,65].
- Δ aggregato 0,37 [0,33; 0,41], p=0,0078.
- Auto-concordanza dell'oracle: F1 0,99 [0,98; 1,00]. Coerenza SQL-atomi 1,00 in tutte le condizioni.
- Richiamo per dimensione nel refined: 1,00 per `L`, `Cb`, `Ce`, `Cp`; 0,98–1,00 per `I`; 0,94–0,98 per `D`. Atomi inventati: 0,08–0,33 per run.
- Il richiamo di `D` sotto 1 viene da `MS02`: il riferimento di `UC02` contiene sia `D:use=nursery` sia `D:use=micro-nursery`, perché 4 run oracle su 5 riconoscono anche il micronido. I run refined che riconoscono solo il nido hanno quindi richiamo `D` 0,5.

**Rilassamento** (sempre di un solo passo): 52 run, cioè 36 refined, 6 one_shot e 10 oracle. È legato agli intenti: tutti i run refined e oracle di `UC03` (sezione primavera) e `UC07` (RSA), più i 6 one_shot di `UC07` a k=1 e k=2. Serie precedente: 28 run (19, 3, 6).

**Dimensione dei risultati (mediane).**

- oracle: 51,5 immobili.
- refined: 49–51,5 a ogni `k` (51 a k=0).
- one_shot: 53,5 (k=1), 103, 148, 500,5, 2.429 (k=5).

**Latenza (mediane).**

- Chiarimento: 11,1 s a k=0, poi 17,2; 23,3; 26,4; 30,8; 38,4 s da k=1 a k=5.
- Analisi: 73,8–75,7 s per refined, 75,5–82,6 s per one_shot, 72,3 s per oracle.

**Confronto con la serie superata** (solo provenienza, da non combinare):

- Invariati: rilevamento esatto, turni uguali a `k`, nessuna domanda a k=0, Δ ampio con p minimo.
- Il tetto oracle-vs-oracle passa da 0,53 a 0,87 (J5), J5 refined da 0,57 a 0,88, Δ da 0,46 a 0,72.
- I risultati sono molto più piccoli: oracle da 121 a 51,5 immobili; one_shot a k=5 da 80.447 a 2.429.
- Auto-concordanza dei filtri oracle da 0,94 a 0,99; F1 refined da 0,96 a 0,98.
- Queste differenze sono coerenti con la presenza del filtro tipologia in tutti i run. Cambiano però anche l'ordine dei job e la fascia oraria, e non si possono separare i contributi.
- Il tetto J5 oracle-oracle (0,87 [0,79; 0,95]) resta sotto quello della serie "utente imperfetto" su codice `c7b9f7a` (0,94 [0,88; 0,98]), con intervalli sovrapposti; sono serie diverse, non confrontate formalmente.

**Esempio `MS02_k2`** (nido; omesse `Cb` e `Ce`), campi `submitted_query` verbatim da `runs.jsonl`:

- `one_shot` **bench_dc898ec9a30c** (repeat 1, 26 risultati): "I am looking for an existing school building. I intend to convert it into a nursery. The location is in Turin. I prefer properties near green spaces."
- `refined` **bench_24b7eb94f445** (repeat 1, due turni, 16 risultati): "I am looking for an existing school building in Turin to convert into a nursery. It must have at least 600 sqm of gross floor area and capacity for 45 people. I prefer a property in energy class D or better. I also prefer properties near green spaces."
- `oracle` **bench_d3c744f2613b** (`UC02_nursery_missing_use`, repeat 1, 16 risultati): "Find an existing school building to convert it into a nursery for 45 children in Turin with at least 600 sqm of gross floor area in energy class D or better near green spaces."

Le query one_shot e oracle sono input predefiniti, identici alla serie precedente; la riscrittura refined è quella osservata in questa serie.

**Interpretazione e cautele.**

- Con il filtro tipologia corretto, refined raggiunge il tetto oracle-vs-oracle a ogni `k` (0,85–0,90 contro 0,87), e anche il controllo k=0 è al tetto. Il divario residuo dall'unità riflette la variabilità della pipeline tra run identici.
- Senza chiarimento, l'accordo crolla già a k=2 e la mediana dei risultati cresce di circa 45 volte da k=1 a k=5.
- Valgono le cautele delle serie precedenti: l'oracle è un riferimento di query, non un giudizio di rilevanza; l'utente simulato è cooperativo ed esatto, quindi l'accordo refined-oracle è un limite superiore; `k` è accoppiato all'identità delle dimensioni omesse.
- Aggiornamento: dal commit `cd0e18b` il paper riporta questa serie.

## Risultati osservati: serie "utente imperfetto" con Claude Haiku 5.5 (2026-11-18)

**Scenari.** `scenarios_v3/imperfect_user.yaml`, generato in modo deterministico da `derive_imperfect_user.py` a partire da `nested48_from_4a7c882.yaml`. Ogni variante cambia esattamente una risposta simulata di uno dei 40 scenari con k≥1:

- **35 varianti opt-out:** la prima dimensione di preferenza omessa (Cb 17, Ce 9, Cp 9) riceve "I have no requirement on …" e lo stato atteso diventa `NOT_REQUESTED`. Per Cb la frase copre superficie, capienza e caratteristiche strutturali.
- **40 varianti vague:** la prima dimensione omessa (D 10, L 10, Cb 10, Ce 5, Cp 5) riceve prima "It depends; something suitable for the project, I guess.", poi il frammento esatto se viene chiesta di nuovo.

Query iniziali, one-shot e oracle restano identiche al disegno annidato.

**Esecuzione.**

- Configurazione: `claude-haiku-5-5` via `claude_cli`, effort medium; refined ×3, oracle ×5 per intento; concorrenza 10; dataset `full`.
- Codice `62630c0`: per `claude_cli` differisce da `a5c1b09` (serie cooperativa) solo per i campi di provenienza aggiunti al manifest.
- Svolgimento: il 2026-11-18 tra le 09:13 e le 10:08 circa, 265 run su 265 completate, 0 errori.
- Risultati in `results/imperfect_user_haiku/`; analisi `analyze_imperfect_user.py` → `imperfect_user_summary.json`.

**Risultati** (media sugli 8 intenti; IC 95% bootstrap a cluster).

| Profilo | Misura | Valore |
|---|---|---|
| opt-out (105 run) | dimensione finale `NOT_REQUESTED` | 105/105 |
| | chiesta una sola volta; turni = k | 105/105; 105/105 |
| | nessun atomo di filtro sulla dimensione rifiutata | 0,90 [0,69; 1,00] (95/105 run) |
| | F1 dei filtri sulle altre dimensioni vs oracle a maggioranza | 0,98 [0,95; 1,00] |
| vague (120 run) | follow-up sulla dimensione vaga; turni = k+1 | 120/120; 120/120 |
| | dimensione finale `SPECIFIED` | 120/120 |
| | F1 dei filtri vs oracle a maggioranza | 0,99 [0,97; 1,00] |
| | J5 vs oracle della stessa serie | 0,93 [0,89; 0,97] |
| | RBO vs oracle | 0,95 [0,93; 0,97] |
| | durata mediana del chiarimento | 36 s (media per intento 43 s); serie cooperativa: 26 s |
| oracle | J5 oracle-vs-oracle | 0,93 [0,88; 0,98] |

- **Unica eccezione opt-out:** tutti i 10 run con atomi sulla dimensione rifiutata appartengono a MS08 (studentato), con opt-out su Cp. L'agente di prossimità ereditato ricava `Cp:education`, e in un run anche `Cp:mobility`, dalla destinazione d'uso. La query raffinata non contiene il requisito. È un comportamento della pipeline MURENA, non del chiarimento.
- **Verifica manuale** di 3 run per profilo (MS02_k2, MS06_k4, MS08_k5 opt-out; MS07_k3, MS01_k3, MS03_k1 vague): domande, risposte simulate (`times_asked_before`) e stati finali sono quelli attesi.
- **Confronti:** il J5 della condizione vague si confronta con gli oracle della stessa serie; la serie non viene combinata con quella cooperativa. Il tetto oracle-oracle (0,93) è più alto di quello della serie cooperativa (0,87), con le stesse query oracle eseguite in un'altra finestra oraria: è variabilità fra esecuzioni.
- **Esecuzioni precedenti, non riportate:**
  - Una prima esecuzione (codice `a9a31cf`, 159 run su 265, interrotta) aveva mostrato blocchi dopo risposte vaghe classificate come *unknown* e dopo un opt-out parziale su Cb.
  - Una seconda (`c7b9f7a`, 264 run completate su 265, in `results/imperfect_user_haiku_c7b9f7a`) aveva un blocco dovuto alla soglia di arresto EVPI.
  - Entrambi i difetti sono stati corretti (`c7b9f7a`, `a5c1b09`) prima della serie riportata.
- **Limiti:** utente simulato con un'unica formulazione per l'opt-out e per la risposta vaga; non è uno studio con utenti reali.

## Analisi successiva: serie imperfetta Codex / gpt-6-luna (2026-11-18)

La directory `backend/experiments/results/imperfect_user_codex_vlast/` contiene
75 varianti, 225 run refined (3 repliche) e 40 oracle (5 per intento), tutte
completate: 265/265. Il manifest registra `codex_exec`, `gpt-6-luna`, dataset
`full` con SHA-256 `d3956041…d4f6da`, seed 13, concorrenza 20 e codice
`37e0732` con working tree dirty. L'analisi è stata rigenerata con
`analyze_imperfect_user.py`; intervalli al 95% ottenuti con bootstrap cluster
sugli otto intenti.

| Profilo | Misura | Valore |
|---|---|---|
| opt-out (105 run) | stato `NOT_REQUESTED`; chiesta una volta; turni = k | 105/105 per ciascuna |
| | nessun atomo sulla dimensione rifiutata | 0,898 [0,710; 1,000] |
| | F1 filtri sulle altre dimensioni vs oracle a maggioranza | 0,992 [0,982; 1,000] |
| vague (120 run) | follow-up; turni = k+1; stato `SPECIFIED` | 120/120 per ciascuna |
| | F1 filtri vs oracle a maggioranza | 0,999 [0,997; 1,000] |
| | Jaccard@5 e RBO@10 vs oracle della stessa serie | 0,735 [0,587; 0,881]; 0,818 [0,722; 0,911] |
| | tempo di chiarimento medio per run | 74,4 s [71,5; 76,7] |
| oracle | Jaccard@5 oracle-vs-oracle | 0,703 [0,513; 0,893] |

Questa serie è distinta da Haiku e non sostituisce i risultati attivi nel
paper. Per l'opt-out non si calcola accordo di ranking con l'oracle, che
conserva il vincolo rifiutato. I valori misurano accordo con riferimenti
costruiti nel benchmark, non rilevanza immobiliare indipendente; restano inoltre
risultati su utenti simulati.

## Limiti

Gli scenari sono sintetici e costruiti per coprire dimensioni, omissioni, ambiguità e casi normativi selezionati. Non costituiscono una user study e non rappresentano la distribuzione di richieste reali. Le risposte simulate e gli oracle riflettono scelte di costruzione del benchmark. Le run conversational documentate sopra sono risultati osservati su questo setup, ma non stimano il beneficio del chiarimento senza condizioni one-shot e oracle appaiate. La copertura normativa segue il catalogo fornito e non certifica autorizzazioni o aggiornamento giuridico. Il protocollo EDBT va mantenuto distinto dai risultati riportati nel paper originale.

Nel controllo di funzionamento del 2026-11-17, una singola run end-to-end `MS01_k1` è terminata con `gpt-6-luna` e dataset `full` in 66.056 secondi: zero errori, un turno, F1 iniziale 1.0 e accuratezza del mapping finale 1.0. La run ha restituito 147 risultati. Questo smoke test verifica un percorso eseguibile, ma non è una valutazione scientifica, una replica del paper o evidenza di stabilità sulle 40 istanze. Il 2026-11-17 i file v2 sono stati rigenerati nel repository: l'unica differenza è il checksum sorgente in `generation_manifest.json`, ora allineato a `scenario_triplets.json`. Il validatore statico è passato (40 scenari, 8 per ciascun `k=1..5`, 8 controlli `k=0`, 120 configurazioni, annidamento, testi, fonti, etichette e YAML) e `benchmark_cli.load_scenarios` carica i 40 casi. Nessun benchmark v2 completo è stato eseguito.

Per i comandi supportati e le lacune operative, vedere [riproduzione](reproduction.md); per i risultati dichiarati nel manoscritto, vedere [benchmark del paper](benchmarks.md).

### Esempio delle tre condizioni nel paper (2026-11-17)

Il paragrafo `Conditions` del manoscritto riporta integralmente i campi
`submitted_query` di tre run già registrati in
`backend/experiments/results/missingness_v3/runs.jsonl`:
`one_shot` **bench_b8213f8cebdf** (`MS02_k2`, repeat 1),
`refined` **bench_a9cf4b8903e0** (`MS02_k2`, repeat 1) e
`oracle` **bench_2eb0d7722958** (`UC02_nursery_missing_use`, repeat 1).
Il caso omette inizialmente `Cb` e `Ce`; la run refined registra due turni.
L'esempio conserva le formulazioni osservate, compresa la differenza tra
“capacity for 45 people” e “for 45 children”. L'oracle è un input predefinito,
la refined una riscrittura osservata; non viene sostituita con l'oracle.
È una spiegazione del protocollo con dati esistenti, senza nuove esecuzioni
o variazioni dei risultati.

**Aggiornamento (2026-11-17, serie Haiku):** l'esempio del paper usa ora le
run `missingness_v3_haiku/runs.jsonl` dello stesso caso: `one_shot`
**bench_4219923a116f**, `refined` **bench_7fccc469c00d** (`MS02_k2`, repeat 1,
due turni) e `oracle` **bench_c41f87c72646** (`UC02_nursery_missing_use`,
repeat 1). Il testo one_shot e l'oracle sono identici a prima, essendo input
predefiniti; la riscrittura refined è quella osservata con Haiku. Gli ID
precedenti restano validi per la serie `gpt-6-luna` (Git `4a7c882`).

### Esportazione del confronto con copertura parziale (2026-11-17)

`comparison_per_k.csv` distingue `n_bases_refined`, `n_bases_one_shot` e
`n_bases_paired`, sostituendo la precedente colonna ambigua `n_bases`.
Le righe `row_type=per_k` mantengono le medie per condizione su tutti gli
intenti disponibili; `refined_paired` e `one_shot_paired` usano invece solo
gli intenti comuni al confronto, e la loro differenza coincide con `delta`.
La riga `row_type=intent_mean_paired` riporta anche le medie e gli IC 95%
delle due condizioni: per ogni intento si mediano solo i livelli k>=1 con
entrambe le condizioni, poi si mediano gli intenti, come per il delta.
I relativi conteggi si riferiscono quindi alla copertura appaiata.
`comparison_status=not_applicable_k0` esplicita l'assenza prevista di
one-shot/delta per i controlli; `no_paired_data` segnala confronti senza
intenti comuni. Questi valori restano vuoti, senza essere convertiti in zero.
`comparison.json` conserva i nuovi riepiloghi in `paired_by_condition`.

Artefatti rigenerati dalle stesse 113 run, con i parametri precedenti
(1000 permutazioni, 10000 bootstrap, seed 13, p=0.8): tutti i campi numerici
JSON preesistenti sono invariati. Test sintetico con copertura sbilanciata
superato insieme alla suite delle metriche. Nessuna nuova esecuzione LLM.
Il paper resta invariato: delta, intervalli, risultati e protocollo scientifico
non cambiano; si chiarisce e completa il formato di esportazione.

Nota di manutenzione (2026-11-17): le directory risultati
`edbt_conversational/` e `missingness_v2/` sono state eliminate dopo la
rimozione delle suite corrispondenti. I riferimenti a tali directory e le
misure riportate sopra sono storici; i file versionati sono recuperabili
alla revisione Git `411b003`. `missingness_v3/` resta invariata, senza
rigenerazione dei risultati. Gli artefatti locali non versionati eliminati
non sono recuperabili da Git.

## Suite a omissione controllata v4 (2026-11-18)

La directory `backend/experiments/data/scenarios_v4/` introduce la formulazione v4 degli scenari imperfetti:
* **Motivazione:** superare tre limitazioni di v3: la frase vaga fissa e generica (*"It depends; something suitable for the project, I guess."*), l'alterazione di una sola risposta per scenario e l'opt-out ristretto alle preferenze. V4 adotta 40 frasi vaghe contestualizzate ($8 \times 5$), 40 rinunce specifiche per use case e dimensione, e la **generalizzazione massima**: tutte le 32 maschere di omissione dei cinque criteri opzionali incrociate con tutti i bilanciamenti ternari tra specificato, vago e opt-out ($n_{\text{spec}} + n_{\text{vague}} + n_{\text{optout}} = k$).
* **Sorgente e conteggio:** il generatore legge il catalogo combinatorio `scenarios_v3/conversational_scenarios.yaml` (8 intenti × 32 maschere = 256) invece delle sei traiettorie annidate. Per ogni maschera con $k$ omissioni si generano $3^k$ assegnazioni, per un totale di $8 \times \sum_{k=0}^{5}\binom{5}{k}3^k = 8 \times 4^5 = \mathbf{8.192}$ scenari: 8 controlli $k=0$, 120 a $k=1$, 720 a $k=2$, 2.160 a $k=3$, 3.240 a $k=4$, 1.944 a $k=5$.
* **Componenti:**
  * `imperfect_user_v4.yaml`: 8.192 scenari (8 `control`, 248 `all_specified`, 248 `all_vague`, 248 `all_optout`, 7.440 `mixed`) generati deterministicamente; ogni scenario conserva `source_variant_id`, `balance`, le tre liste di dimensioni ed `expected_turns`.
  * `derive_imperfect_user_v4.py`: generatore deterministico senza chiamate a modelli LLM.
  * `validate_scenarios_v4.py`: validatore statico superato (conteggi, distribuzione per $k$, 256 maschere distinte, formati e coerenza degli stati attesi).
* **Cautele:** i profili `all_vague` a $k=5$ richiedono fino a 10 turni, ora entro il nuovo default `max_turns = 20` (le serie v3 furono eseguite con 6). Un'omissione semplice di $D$ o $L$ diventa `UNCONFIRMED_ABSENT` come per ogni altra dimensione e un rifiuto esplicito porta a `NOT_REQUESTED`: $L$ non è `MISSING_CRITICAL` per il solo fatto di essere assente (lo diventa solo se il parser dichiara un valore non ancorato alla query o in caso di contraddizione). Rinunciare a $L$ significa cercare su tutto il dataset, senza filtro geografico. `analyze_imperfect_user.py` riconosce solo i profili storici e salta i nuovi.
* **Piano iniziale di esecuzione:** la CLI supporta campioni uniformi riproducibili con `--sample-fraction`, `--sample-seed` singolo o `--sample-seeds` multiplo. Ogni seed usa una directory e un manifest separati. La configurazione documentata usa 1% (82/8.192 scenari per seed), cinque seed e `--repeat 3` comune a refined e oracle: 1.230 run refined + 120 oracle = 1.350 job pianificati. Il modello proviene da `LLM_MODEL` in `backend/.env`; il runner non offre un'opzione `--model`. Il manifest registra parametri e ID campionati; `--dry-run` mostra il piano senza invocare LLM. L'oracle resta un riferimento statico e non è un obiettivo di ranking condizionato per gli scenari con opt-out.
* **Esecuzioni v4 registrate (2026-11-18):**
  * **Codex / ChatGPT 6 Luna** (`codex_exec`, `gpt-6-luna`): artefatti originariamente in `imperfect_user_v4_oracle_first_seed13/`, ora confluiti in [`imperfect_user_v4_comparison_seed13/`](../../../backend/experiments/results/imperfect_user_v4_comparison_seed13/). Serie terminata secondo `completed_at` nel manifest; 1% del catalogo, seed 13, condizioni `oracle` e `refined`, tre ripetizioni, concorrenza 20. Sono registrati 270 tentativi: 233 `completed` e 37 `error`.
  * **vLLM / Qwen 3.8** (`openai-compatible`, ID modello `Qwen/Qwen3.8-27B`): artefatti in [`imperfect_user_v4_multiseed_qwen3-8b_seed13/`](../../../backend/experiments/results/imperfect_user_v4_multiseed_qwen3-8b_seed13/). Serie in corso al controllo; manifest senza `completed_at`, con 8 run `completed` già registrate. Configurazione: 1%, seed 13, condizioni `refined` e `oracle`, tre ripetizioni, concorrenza 2.
* **Stato scientifico prima dell'aggregazione:** i percorsi e conteggi documentavano lo stato operativo delle esecuzioni; il confronto tra le tre condizioni è stato calcolato successivamente ed è descritto qui sotto.
* **Rappresentazione nel paper prima della sostituzione (2026-11-18):** il manoscritto descriveva il paradigma v4 come framework di generazione ma riportava la serie Haiku v3. Tale versione è conservata come commento nel sorgente LaTeX e non rappresenta più i risultati attivi.
* **Run parziale seed 13 (2026-11-18):** in `backend/experiments/results/imperfect_user_v4_multiseed_seed13/` il manifest registra `gpt-6-luna` (`codex_exec`), dataset `full`, campionamento 1% (82 scenari previsti), 3 repliche e condizioni refined/oracle. Dopo l'interruzione, gli artefatti contenevano 107 run refined (93 completate, 14 errori) e nessun oracle. In seguito sono state copiate dalla cartella `imperfect_user_v4_oracle_first_seed13/` le 24 run oracle completate (8 intenti × 3), verificando checksum di dataset/scenari, impostazioni e identità byte-per-byte dei 24 artefatti. Il totale corrente è 131 run: 93 refined completate, 14 refined fallite e 24 oracle completate. `compare_conditions.py` calcola accordo refined-oracle per gli intenti con run valide: Jaccard@5 medio per k = 0,484 (k=2, 2 intenti), 0,250 (k=3, 4), 0,221 (k=4, 3), 0,121 (k=5, 2); F1 dei filtri = 0,909, 0,832, 0,785 e 0,785 rispettivamente. Jaccard@5 oracle-oracle è 0,580 (8 intenti). Non ci sono run `one_shot`, quindi il confronto refined-one-shot e le differenze non sono calcolabili. Inoltre i profili v4 `mixed` comprendono opt-out: l'oracle include comunque quei vincoli, quindi l'accordo con oracle non è un obiettivo valido per tutte le run; queste metriche sono descrittive, non una misura complessiva di qualità o rilevanza immobiliare. I 14 errori refined restano inclusi nei conteggi operativi ma esclusi dalle metriche di ranking completate. Risultati e limiti sono salvati in `comparison.json`, `comparison_per_k.csv` e `comparison_operational.csv`; non sono aggregati con la serie v3 né riportati nel paper.
* **Risultati osservati: serie utente imperfetto v4 seed 13 (2026-11-18):** i risultati delle tre condizioni sono stati aggregati da `imperfect_user_v4_one_shot_seed13/` e `imperfect_user_v4_oracle_first_seed13/` in `imperfect_user_v4_comparison_seed13/` (516 righe: 246 one-shot completate, 209 refined completate e 37 errori refined, 24 oracle completate). Modello `gpt-6-luna`, `codex_exec`, campione 1% (82 varianti), tre ripetizioni per variante/refined e tre oracle per intento, seed 13. Sui run completi, la media per otto intenti dà Jaccard@5 refined 0,249 (IC cluster-bootstrap 95% 0,175–0,319) contro one-shot 0,000; RBO@10 0,322 (0,233–0,404) contro 0,000; F1 atomico refined 0,815 (0,782–0,846) contro 0,320 (0,272–0,374). Delta rispettivi 0,249, 0,322 e 0,495; test sign-flip esatto p=0,0078125 per ognuno. Il rumore oracle-oracle è Jaccard@5 0,580 (0,359–0,777) e RBO@10 0,695 (0,470–0,878). Il campione non contiene k=0 o k=1; i tassi di completamento refined sono 33/33, 63/72, 63/72, 50/69 per k=2–5. Gli zeri one-shot sono sovrapposizione nulla degli ID memorizzati nelle liste top-5/top-10 con quelle oracle, non dati mancanti. L'oracle mantiene i vincoli anche negli scenari opt-out, quindi l'accordo non è un criterio appropriato per tutte le istanze; nessuna metrica attesta rilevanza immobiliare indipendente. I risultati sono descrittivi di questo modello/campione/seed e non si combinano con la serie Haiku v3.
  - Successivamente, su richiesta dell'utente, il paper torna a riportare `missingness_v3_haiku_r2` e `imperfect_user_haiku`, senza combinarle; la tabella attiva riassume la serie cooperativa e il testo mantiene i risultati imperfetti separati. Il v4 seed 13, compresi protocollo e metriche dettagliate, resta nel sorgente LaTeX inattivo. La curva attiva usa i dati Haiku in `paper/data/per_k.csv`; la curva v4 è conservata in `paper/data/per_k_v4_seed13_archived.csv`. La descrizione del generatore v4 non implica che i risultati Haiku siano stati generati dalla suite v4. PDF non compilato su richiesta; pagine e layout non verificati.
* **Analisi e conservazione:** `compare_conditions.py` ha aggregato le tre condizioni dai due `runs.jsonl` sorgente in una cartella combinata, senza spostare gli artefatti originali. Vedere `comparison.json`, `comparison_per_k.csv` e `comparison_operational.csv` nella cartella v4 seed 13.
* **Aggiornamento del paper (ripristino Haiku):** la versione attiva riporta di nuovo le serie Claude Haiku 5.5 `missingness_v3_haiku_r2` (304/304) e `imperfect_user_haiku` (265/265), senza pooling. V4 seed 13 resta come evidenza separata, archiviata nel sorgente e nella sua curva CSV. Aggiornati i confini dell'evidenza; il PDF non è stato compilato su richiesta.
