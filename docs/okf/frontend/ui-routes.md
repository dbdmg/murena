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
| `/` | `SearchPage` | Inserimento requisiti, avvio analisi |
| `/processing/:runId` | `ProcessingPage` | Progresso e tracce della run |
| `/map` | `MapPage` | Mappa, risultati, filtri, layer e dettagli |
| `/history` | `HistoryPage` | Elenco delle analisi precedenti |
| `/logs` | `LogsPage` | Log e trace browser/agent |
| `/settings` | `SettingsPage` | Impostazioni e preferenze UI |

Quando `ENABLE_SAGE_CLARIFICATION` è attivo, la schermata `/` passa dalla barra iniziale a una conversazione: la query appare come primo messaggio, ogni risposta e successiva domanda restano nel thread, e l'analisi parte solo quando l'API restituisce `READY`. `BLOCKED` mostra l'esito nel thread e offre l'avvio di una nuova ricerca.

Le pagine eccetto `/login` sono incapsulate in `ProtectedRoute` e `AppLayout`. Gli import sono lazy con `Suspense`, e i provider di stato circondano il router.

## Componenti chiave

- Mappa: `Map`, `ResultsSidebar`, `ResultsCarousel`, `LayersPanel`, `MapRunSelector`.
- Edifici: `BuildingSidebar`, `BuildingDetail`, `AIEvaluationCard`, `EnergyDetailModal`.
- Agenti: `AgentTraceViewer`, `AgentRefinementHUD`, `SQLFiltersHUD`, `FeedbackPanel`.

La protezione di route frontend **non sostituisce** la verifica dei permessi sul backend.
