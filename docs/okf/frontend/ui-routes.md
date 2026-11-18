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

La pagina autenticata `/benchmark` visualizza `manifest.json` e `runs.jsonl` del benchmark. Vite risolve i due file dalla cartella indicata da `VITE_BENCHMARK_RESULTS_DIR`, relativa a `frontend/` o assoluta; il valore predefinito e quello configurato in `.env.demo` sono `../backend/experiments/results/imperfect_user_v4_multiseed_seed13`. La stessa cartella alimenta il pannello demo: l'exporter genera `public/data/benchmark_runs.json` leggendo scenari e run dai relativi artefatti. Configurare il percorso prima di avviare Vite o creare la build. I dati sono incorporati nell'asset frontend: riavviare la modalità demo o ricostruire la build per includere nuove run. La UI mostra i tentativi registrati, inclusi retry ed errori; non li interpreta come risultati scientifici aggregati.

## Modalità demo con scenari pronti

La modalità scenari è una **modalità di avvio** del frontend: `npm run dev:demo` oppure build statica con `npm run build:demo` e `npm run preview`. `.env.demo` abilita `VITE_DEMO_MODE=true`. La modalità normale (`npm run dev` / `npm run build`) non mostra il pannello scenari. Il flag è fissato all'avvio/build, non modificabile da pulsanti o preferenze salvate.

La modalità scenari entra con un utente frontend locale, senza richiedere il login. Tutte le richieste API usano un adapter locale; il proxy backend Vite è disattivato e nessuna richiesta di analisi o dettaglio raggiunge il backend. La conferma crea una run locale con il top-10 precomputato per la variante, quando disponibile. La pagina di elaborazione interroga l'adapter locale. Le tile della mappa e le immagini Mapillary/ESRI restano disabilitate.

Gli exporter eseguiti da `npm run dev:demo` e `npm run build:demo` producono un campione deterministico di massimo 5.000 immobili in `public/data/estates.json`, i dettagli di tutti gli immobili presenti nei top benchmark in `public/data/benchmark_estates.json` e il catalogo POI in `public/data/pois_by_category.json`. La mappa applica inoltre il limite visualizzazione configurato dall'utente (500–5.000). I POI vengono caricati per categoria e viewport, con un massimo di 1.000 punti per richiesta. L'exporter di `benchmark_runs.json` legge la stessa `VITE_BENCHMARK_RESULTS_DIR` configurata per `/benchmark`; il selettore e l'adapter demo usano le run refined completate e associano i risultati, SQL e valutazioni salvati. Gli artefatti compatti di schema 3 non contengono output dell'EvaluationAgent; gli artefatti precedenti che conservano la risposta API completa possono invece contenerli.

In modalità scenari, i dieci risultati associati alla run locale vengono mostrati nel carosello inferiore con il titolo `Benchmark Top 10`. Le valutazioni dell'EvaluationAgent e le motivazioni, pro e contro vengono associate ai relativi immobili quando sono presenti nell'artefatto.

Il carosello demo unisce i risultati valutati e gli altri risultati del benchmark fino a dieci elementi. Il pannello `SQL Query` legge la SQL finale salvata nella run esportata e la rende disponibile attraverso l'adapter locale.

La mappa demo mostra un pulsante `Home` nella barra dei controlli per tornare alla schermata di selezione degli scenari.

Il dettaglio in demo arricchisce sia i marker dell'inventario sia i risultati benchmark con i campi catastali disponibili in `estates.parquet` (foglio, particella, subalterno, unità, data e zona OMI). Natura legale, destinazione e vincolo culturale non sono presenti nello schema di questo inventario e quindi non sono mostrate per questi record.

In modalità demo non sono disponibili i rating: `Rate Search`, il feedback per singola property e le stelle associate in mappa e carosello sono nascosti.

Nella modalità backend, i top picks sono i risultati valutati che corrispondono alla query e hanno un punteggio. Il benchmark conserva il punteggio nel top-10 e l'export demo richiede un punteggio numerico finito per ogni risultato; il carosello mostra quel valore.

Il pannello scenari nella pagina `/` non carica più un catalogo separato. Legge le definizioni e le conversazioni associate alle run `refined` completate, tramite l'indice derivato dalla stessa cartella di risultati di `/benchmark`. Dopo l'use case, sei pulsanti compatti mostrano una dimensione ciascuno; il click cicla gli stati omessa, ambigua e specificata, mostrando solo quelli che lasciano almeno una run compatibile con gli altri filtri. Nel mapping demo, una risposta opt-out conta come dimensione omessa, una risposta vaga come ambigua e una risposta specifica o già presente nella richiesta come specificata. Se più run corrispondono alla selezione, un selettore finale consente di scegliere la run. Il pannello mostra la richiesta iniziale e le dimensioni chiarite; la conferma riproduce conversazione e risultati precomputati della stessa run. Non esegue un nuovo parsing SAGE o una nuova analisi LLM:

- La selezione demo avviene per scenario v4 con run completata; `Load recorded conversation` carica il transcript della run e il query review. Il caricamento sostituisce il thread e la sessione precedenti.
- Quando è aperta la conversazione demo, il selettore resta a sinistra e `Let’s refine your search` appare a destra su schermi medi e ampi; su schermi stretti i pannelli si dispongono in colonna.
- L'indicatore `DEMO MODE` compare una sola volta nell'angolo superiore; il titolo del selettore è `Select scenario`.
- In modalità demo la sidebar è nascosta e il contenuto principale occupa tutta la larghezza disponibile.
- `loadDemoConversation` carica nel thread il transcript registrato e il query review osservato, che resta modificabile. La modalità locale non esegue parsing, riscrittura LLM o strategia SAGE.
- La selezione degli scenari e l'analisi simulata non contattano il backend. La mappa può mostrare l'inventario statico esportato, ma non risultati di ricerca calcolati.
- Se la cartella configurata non contiene `manifest.json` o `runs.jsonl`, la pagina benchmark non può caricare i dati; se non ci sono artefatti `refined` completati, il selettore demo mostra uno stato vuoto.
- La selezione dello scenario resta disponibile durante la conversazione e la review, tranne mentre viene elaborato un invio. Sessioni e run restano in memoria e si azzerano al reload. Non è presente un controllo di upload/importazione.

La demo e la pagina benchmark leggono lo stesso esperimento configurato; l'inventario statico è un dato di presentazione separato. I risultati visualizzati non sono aggregati scientifici e il selettore demo riproduce solo run refined, non esegue le condizioni one-shot/oracle.

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
