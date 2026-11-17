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

## Limiti

Gli scenari sono sintetici e costruiti per coprire dimensioni, omissioni, ambiguità e casi normativi selezionati. Non costituiscono una user study e non rappresentano la distribuzione di richieste reali. Le risposte simulate e gli oracle riflettono scelte di costruzione del benchmark. Le run conversational documentate sopra sono risultati osservati su questo setup, ma non stimano il beneficio del chiarimento senza condizioni one-shot e oracle appaiate. La copertura normativa segue il catalogo fornito e non certifica autorizzazioni o aggiornamento giuridico. Il protocollo EDBT va mantenuto distinto dai risultati riportati nel paper originale.

Nel controllo di funzionamento del 2026-11-17, una singola run end-to-end `MS01_k1` è terminata con `gpt-6-luna` e dataset `full` in 66.056 secondi: zero errori, un turno, F1 iniziale 1.0 e accuratezza del mapping finale 1.0. La run ha restituito 147 risultati. Questo smoke test verifica un percorso eseguibile, ma non è una valutazione scientifica, una replica del paper o evidenza di stabilità sulle 40 istanze. Il validatore applicato ai file v2 presenti si arresta sul checksum sorgente del manifest; la rigenerazione temporanea dai sorgenti attuali ha superato i controlli statici di conteggio, annidamento, testi e mapping. Occorre rigenerare i file v2 nel repository per riallineare il manifest prima di ripetere la validazione.

Per i comandi supportati e le lacune operative, vedere [riproduzione](reproduction.md); per i risultati dichiarati nel manoscritto, vedere [benchmark del paper](benchmarks.md).
