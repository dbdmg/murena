---
type: Frontend Reference
title: Percorsi e schermate della UI
description: Route React Router e principali funzioni visibili all’utente.
tags:
- frontend
- routing
- pages
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../frontend/src/App.tsx
  title: 'MURENA repository: frontend/src/App.tsx'
- resource: ../../../frontend/src/components/common/ProtectedRoute.tsx
  title: 'MURENA repository: frontend/src/components/common/ProtectedRoute.tsx'
- resource: ../../../frontend/src/pages/SearchPage.tsx
  title: 'MURENA repository: frontend/src/pages/SearchPage.tsx'
- resource: ../../../frontend/src/pages/MapPage.tsx
  title: 'MURENA repository: frontend/src/pages/MapPage.tsx'
---

# Percorsi e schermate della UI

| Percorso | Pagina | Funzione |
|---|---|---|
| `/login` | `LoginPage` | Autenticazione; pagina pubblica |
| `/` | `SearchPage` | Inserimento requisiti, avvio analisi e suggerimenti di query generati dal modello |
| `/processing/:runId` | `ProcessingPage` | Progresso e tracce della run |
| `/map` | `MapPage` | Mappa, risultati, filtri, layer, dettagli e query SQL della run attiva |
| `/history` | `HistoryPage` | Elenco delle analisi precedenti |
| `/logs` | `LogsPage` | Log e trace browser/agent |
| `/benchmark` | `BenchmarkPage` | Consultazione del manifest e delle run del benchmark, con filtri e dettaglio di query, SQL, errori e risultati |
| `/settings` | `SettingsPage` | Impostazioni e preferenze UI |

L'intera UI è in inglese e non offre un selettore di lingua. Quando `ENABLE_SAGE_CLARIFICATION` è attivo, la schermata `/` passa dalla barra iniziale a una conversazione in inglese: la query originale appare come primo messaggio e le domande generate dal modello restano nel thread con le risposte dell'utente. Al termine, `REVIEW` mostra la query riscritta in inglese in un campo modificabile; l'analisi parte solo dopo la conferma dell'utente. `BLOCKED` mostra un messaggio di stato in inglese nel thread e offre l'avvio di una nuova ricerca.

Durante il chiarimento, il pannello usa l'altezza disponibile della finestra: la cronologia scorre in modo indipendente e il composer o i controlli di conferma restano fissi in fondo. L'utente può comprimere/riaprire la conversazione dall'intestazione e regolare verticalmente l'altezza del pannello.

Le pagine eccetto `/login` sono incapsulate in `ProtectedRoute` e `AppLayout`. Gli import sono lazy con `Suspense`, e i provider di stato circondano il router.

## Componenti chiave

- Mappa: `Map`, `ResultsSidebar`, `ResultsCarousel`, `LayersPanel`, `MapRunSelector`, `SQLQueryPanel`.
- Edifici: `BuildingSidebar`, `BuildingDetail`, `AIEvaluationCard`, `EnergyDetailModal`.
- Feedback: `FeedbackPanel`; le tracce restano consultabili nelle schermate di log e dettaglio run.

La mappa non espone più la modifica dei prompt degli agenti. Nel pannello Layers, il layer OMI è etichettato `Cadastral Zones`; il toggle `Districts` è stato rimosso. Per la run selezionata, `SQL Query` è accanto al selettore delle run e mostra la query SQL, con copia negli appunti e schede per eventuali tentativi rilassati.

I filtri della mappa includono tipologia, energia, superficie e periodo di costruzione, oltre ai filtri di visualizzazione. I valori di tipologia corrispondono alle etichette effettivamente presenti in `estates.parquet`. I filtri per utilizzo del bene, vincolo culturale e natura legale non sono esposti: il dataset caricato non contiene questi campi. Il filtro EPC è stato rimosso perché l'inventario disponibile contiene solo edifici con EPC.

La protezione di route frontend **non sostituisce** la verifica dei permessi sul backend.

## Risultati benchmark

La pagina autenticata `/benchmark` visualizza `manifest.json` e `runs.jsonl` del benchmark. Vite risolve i due file dalla cartella indicata da `VITE_BENCHMARK_RESULTS_DIR`, relativa a `frontend/` o assoluta; il valore predefinito è `../backend/experiments/results/all_scenarios_codex`. Configurare il percorso prima di avviare Vite o creare la build. I dati sono incorporati nell'asset frontend: una build statica va ricostruita per includere nuove run. La UI mostra i tentativi registrati, inclusi retry ed errori; non li interpreta come risultati scientifici aggregati.

## Modalità demo con scenari pronti

La modalità scenari è una **modalità di avvio** del frontend: `npm run dev:demo` oppure build statica con `npm run build:demo` e `npm run preview`. `.env.demo` abilita `VITE_DEMO_MODE=true`. La modalità normale (`npm run dev` / `npm run build`) non mostra il pannello scenari. Il flag è fissato all'avvio/build, non modificabile da pulsanti o preferenze salvate.

La modalità scenari entra con un utente frontend locale, senza richiedere il login. Tutte le richieste API usano un adapter locale; il proxy backend Vite è disattivato e nessuna richiesta di analisi o dettaglio raggiunge il backend. La conferma crea una run locale senza immobili perché il catalogo non contiene risultati. La pagina di elaborazione interroga l'adapter locale. Le tile della mappa e le immagini Mapillary/ESRI restano disabilitate.

Per mostrare l'inventario sulla mappa senza backend, il Parquet viene esportato in `frontend/public/data/estates.json`. Rigenerare il file dopo aver aggiornato il dataset con `uv run --project backend python frontend/scripts/export_estates.py`. Il JSON contiene i 36.328 record del Parquet corrente e viene scaricato dal browser quando si apre la mappa in modalità scenari. I dettagli visibili sono limitati ai campi inclusi nell'export; run demo locali e triplets non contengono risultati dell'analisi.

Il pannello scenari nella pagina `/` carica `scenario_triplets.json` dalla cartella configurata con `DEMO_SCENARIOS_DIR` in `frontend/.env.demo`, come asset separato su richiesta. Il valore predefinito `../backend/experiments/data/scenarios_v3` contiene otto gruppi S01–S08, ognuno con 32 varianti. Solo il gruppo base ha `enabled`; la UI mostra tutte le varianti dei gruppi attivi e nessuna di quelli disattivati. Tutte le basi sono inizialmente abilitate. Il JSON contiene `scenarios: [{id, enabled, variants}]`; flag sulle varianti o flag base non booleani rendono il catalogo non valido. Se tutte le basi sono disabilitate il pannello mostra uno stato vuoto. Modificare i flag nel YAML runner e rigenerare per sincronizzare il JSON. I vecchi cataloghi come array piatto senza flag restano supportati. Il percorso è relativo a `frontend/` oppure assoluto; viene risolto da Vite sul filesystem all’avvio/build, senza esporre una selezione di file nella UI. Dopo una modifica alla configurazione riavviare Vite o ricostruire la build statica:

- La selezione demo avviene in due passaggi: prima il caso base (`S01`–`S08`), poi le dimensioni mancanti con sei checkbox. La UI trova la variante pre-generata con la stessa combinazione e mostra il relativo ID; `Load selected scenario` carica la conversazione, senza azzerarla mentre si stanno ancora scegliendo le dimensioni. Una combinazione non presente nel catalogo non è caricabile. Il caricamento sostituisce il thread e la sessione precedenti. Rimossi i pulsanti di inserimento query iniziale/one-shot/oracle e quelli delle risposte pronte.
- Quando è aperta la conversazione demo, il selettore resta a sinistra e `Let’s refine your search` appare a destra su schermi medi e ampi; su schermi stretti i pannelli si dispongono in colonna.
- L'indicatore `DEMO MODE` compare una sola volta nell'angolo superiore; il titolo del selettore è `Select scenario`.
- In modalità demo la sidebar è nascosta e il contenuto principale occupa tutta la larghezza disponibile.
- `loadDemoConversation` carica nel thread la query iniziale e le risposte predefinite per le dimensioni selezionate; la query assemblata resta modificabile nella review. La modalità locale non esegue parsing, riscrittura LLM o strategia SAGE.
- La selezione degli scenari e l'analisi simulata non contattano il backend. La mappa può mostrare l'inventario statico esportato, ma non risultati di ricerca calcolati.
- Il catalogo configurato deve essere un array non vuoto con ID univoci, destinazione d’uso, dimensioni mancanti, tre query e una mappa di risposte testuali per dimensioni note; i metadati aggiuntivi sono ammessi. Un catalogo non valido mostra un errore e non abilita la scelta degli scenari. Una cartella/file inesistente causa un errore di risoluzione Vite; non viene usato un catalogo alternativo.
- La selezione dello scenario resta disponibile durante la conversazione e la review, tranne mentre viene elaborato un invio. Sessioni e run restano in memoria e si azzerano al reload. Non è presente un controllo di upload/importazione.

Il catalogo e l'inventario statico sono risorse di presentazione; non rappresentano risultati scientifici e il selettore non esegue le condizioni one-shot/oracle del benchmark.

Verifiche storiche del simulatore locale: build normale/demo, lint mirato, test del contratto e dei 48 dialoghi con `npm run test:demo`. Da non confondere con la modalità scenari corrente, che inoltra le analisi al backend.

Verifica del caricamento automatico: browser su `MS02_k2` (avvio immediato e risposta), passaggio a `MS01_k0` (review immediata) e a `MS01_k1` (nuovo thread senza residui della review); nessuna richiesta backend o errore JavaScript.

Verifica del caricamento completo: test automatico su tutti i 48 scenari,
ordine e contenuto delle risposte, review confermabile e invalidazione della
sessione precedente al cambio scenario; build normale/demo e lint mirato.
Le precedenti verifiche browser documentano il comportamento storico;
questa revisione è verificata tramite test del simulatore e compilazione.

Verifica della cartella configurabile: build normale e demo, quattro test del
simulatore e lint mirato superati. Build demo aggiuntiva con cartella assoluta
temporanea e catalogo distinto: verificata la presenza del catalogo scelto
negli asset generati.
