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

## Modalità demo offline con scenari pronti

La demo è una **modalità di avvio** del frontend: `npm run dev:demo` oppure build statica con `npm run build:demo` e `npm run preview`. `.env.demo` abilita `VITE_DEMO_MODE=true`. La modalità normale (`npm run dev` / `npm run build`) conserva la connessione reale al backend e non mostra il pannello scenari. Il flag è fissato all'avvio/build, non modificabile da pulsanti o preferenze salvate.

La demo entra con un utente locale senza verificare token o richiedere il login, preservando la sessione reale salvata. Tutte le chiamate Axios passano da un adapter in memoria; gli endpoint non supportati falliscono localmente, senza fallback di rete. Il proxy backend Vite e le connessioni WebSocket dell'analisi sono disattivati. Anche tile della mappa e immagini Mapillary/ESRI sono disabilitate; la mappa rimane senza basemap. Il server Vite continua naturalmente a servire asset e il proprio WebSocket di sviluppo.

Il pannello scenari nella pagina `/` carica i 48 casi di `backend/experiments/data/scenarios_v3/scenario_triplets.json` come asset separato su richiesta:

- Il selettore mostra `case_id`, destinazione d'uso e numero di dimensioni mancanti. Il catalogo parte senza selezione: scegliendo un caso, la conversazione si apre automaticamente con `conversational.initial_query` e la prima domanda locale; i casi senza dimensioni mancanti passano direttamente alla review. Rimossi i pulsanti di inserimento query iniziale/one-shot/oracle. Scegliere un altro caso sostituisce il thread e la sessione precedenti, azzerando risposta in bozza, errori e review.
- Il simulatore pone domande generiche seguendo l'ordine di `missing_dimensions`. Le risposte pronte vengono da `conversational.simulated_user_answers_by_dimension`; inserimento e invio sono manuali, con testo modificabile. La review concatena query e risposte; non esegue parsing, riscrittura LLM o strategia SAGE. Il trasporto locale continua ad accettare la query oracle esatta direttamente in review, ma la UI avvia soltanto la query conversazionale.
- Alla conferma viene creata una run locale completata, con messaggio esplicito e **nessun immobile**: i triplets non contengono risultati. Cronologia e dettaglio consultano soltanto queste run locali. Nessun risultato scientifico o prestazione del sistema è deducibile dalla simulazione.
- **Import scenario triplets JSON** sostituisce il catalogo in memoria con un array non vuoto nello stesso formato. Sono richiesti ID univoci, destinazione d'uso, dimensioni mancanti, tre query e una mappa di risposte testuali per dimensioni note; i metadati aggiuntivi sono ammessi. Un file non valido non sostituisce il catalogo precedente.
- La selezione resta disponibile durante la conversazione e la review, tranne mentre viene elaborato un invio. L'importazione è bloccata durante la conversazione; le risposte sono disabilitate nella review. Scenari importati, sessioni e run restano in memoria e si azzerano al reload. Per aggiornare il catalogo incorporato modificare il JSON sorgente e ricostruire il frontend.

È una risorsa di presentazione dell'estensione conversazionale, separata dal sandbox con risultati salvati sul backend. Non modifica pipeline, prompt o protocollo sperimentale. I campi one-shot e oracle restano nel formato importato per compatibilità; la UI non esegue le condizioni del benchmark.

Verifiche: build normale/demo, lint mirato, test del contratto e dei 48 dialoghi con `npm run test:demo`. Verifica browser sul percorso `MS02_k2` e sulle pagine principali: nessuna richiesta backend o WebSocket di analisi, nessun errore JavaScript, token reale preservato.

Verifica del caricamento automatico: browser su `MS02_k2` (avvio immediato e risposta), passaggio a `MS01_k0` (review immediata) e a `MS01_k1` (nuovo thread senza residui della review); nessuna richiesta backend o errore JavaScript.
