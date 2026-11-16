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

La provenienza dichiarata nel README degli scenari è il bundle `murena-demo(4).zip` e il catalogo normativo in esso contenuto. `catalog_snapshot_sha256.txt` registra l'impronta dello snapshot normativo usato nella costruzione. Il validatore statico presente nella directory controlla coerenza strutturale e copertura rispetto al catalogo corrente. Queste tracce documentano la provenienza e la coerenza interna dei dati, **non** una validazione empirica con utenti, una verifica indipendente delle norme o l'esecuzione del benchmark.

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

Non sono implementati nel runner il **Requirement F1** su vincoli atomici, il **Top-5 Jaccard** tra condizioni, il punteggio di **use-case matching** rispetto alle aspettative per configurazione, il confronto delle query one-shot/oracle, né il controllo comparativo dei filtri SQL. Sono obiettivi del protocollo o metadati presenti negli scenari, non metriche già calcolate. La CLI non produce misure comparative di turn count o latency tra configurazioni.

## Limiti

Gli scenari sono sintetici e costruiti per coprire dimensioni, omissioni, ambiguità e casi normativi selezionati. Non costituiscono una user study, non rappresentano la distribuzione di richieste reali e non forniscono risultati sperimentali finché le esecuzioni non vengono effettuate e analizzate. Le risposte simulate e gli oracle riflettono scelte di costruzione del benchmark. La copertura normativa segue il catalogo fornito e non certifica autorizzazioni o aggiornamento giuridico. Il protocollo EDBT va quindi mantenuto distinto dagli esperimenti, dai dataset e dai risultati riportati nel paper originale.

Per i comandi supportati e le lacune operative, vedere [riproduzione](reproduction.md); per i risultati dichiarati nel manoscritto, vedere [benchmark del paper](benchmarks.md).
