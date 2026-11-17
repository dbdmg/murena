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
conserva protocollo annidato e misure storiche, distinguendoli dall'estensione.
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

**Esecuzione.**

- Configurazione:
  - modello `claude-haiku-5-5` tramite il provider `claude_cli` (Claude Code CLI, effort `medium`, temperatura 0);
  - dataset `full` (89.200 immobili, SHA-256 `bc6732c8…`), rilassamento attivo;
  - seed 13 con ordine dei job interleaved, concorrenza 10;
  - ripetizioni: refined ×3, one_shot ×3 (k≥1), oracle ×5 per intento.
- Input: `backend/experiments/data/scenarios_v3/nested48_from_4a7c882.yaml`, copia byte per byte del file runner annidato a 48 varianti del commit `4a7c882`, cioè lo stesso disegno della serie parziale. Il catalogo corrente S01–S08 non è stato usato.
- Codice: commit `7fd238d`. Il manifest riporta `dirty=true` perché il file di input non era ancora versionato al lancio; è stato pubblicato subito dopo, senza modifiche (`1bc396f`). Il runner usato è precedente alla rimozione di seed e interleaving (`3e118f5`).
- Esecuzione dalle 17:26 alle 18:28 (ora locale, 62 minuti): **304/304 run completati**, nessun run fallito, nessun `agent_errors`, nessun fallback.
- Rilassamento in 28 run: 19 refined, 3 one_shot, 6 oracle.
- Robustezza del CLI: 1 nuovo tentativo dell'adattatore, per una corruzione transitoria di `~/.claude.json` tra processi concorrenti; il file è risultato integro a fine run.
- Artefatti `runs/` compatti (schema 3), 19 MB, esclusi da Git; versionati `runs.jsonl`, `manifest.json`, `summary.csv`, `comparison*.{json,csv}`.

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
