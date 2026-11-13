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
| `/map` | `MapPage` | Mappa, risultati, filtri, layer e dettagli |
| `/history` | `HistoryPage` | Elenco delle analisi precedenti |
| `/logs` | `LogsPage` | Log e trace browser/agent |
| `/settings` | `SettingsPage` | Impostazioni e preferenze UI |

L'intera UI è in inglese e non offre un selettore di lingua. Quando `ENABLE_SAGE_CLARIFICATION` è attivo, la schermata `/` passa dalla barra iniziale a una conversazione in inglese: la query originale appare come primo messaggio e le domande generate dal modello restano nel thread con le risposte dell'utente. Al termine, `REVIEW` mostra la query riscritta in inglese in un campo modificabile; l'analisi parte solo dopo la conferma dell'utente. `BLOCKED` mostra un messaggio di stato in inglese nel thread e offre l'avvio di una nuova ricerca.

Durante il chiarimento, il pannello usa l'altezza disponibile della finestra: la cronologia scorre in modo indipendente e il composer o i controlli di conferma restano fissi in fondo. L'utente può comprimere/riaprire la conversazione dall'intestazione e regolare verticalmente l'altezza del pannello.

Le pagine eccetto `/login` sono incapsulate in `ProtectedRoute` e `AppLayout`. Gli import sono lazy con `Suspense`, e i provider di stato circondano il router.

## Componenti chiave

- Mappa: `Map`, `ResultsSidebar`, `ResultsCarousel`, `LayersPanel`, `MapRunSelector`.
- Edifici: `BuildingSidebar`, `BuildingDetail`, `AIEvaluationCard`, `EnergyDetailModal`.
- Agenti: `AgentTraceViewer`, `AgentRefinementHUD`, `SQLFiltersHUD`, `FeedbackPanel`.

La protezione di route frontend **non sostituisce** la verifica dei permessi sul backend.
