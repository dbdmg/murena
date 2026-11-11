---
type: API Contract
title: Aggiornamenti progressivi WebSocket
description: Canale live di avanzamento e completamento per un run_id.
tags:
- websocket
- api
- progress
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/api/v1/endpoints/websockets.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/websockets.py'
- resource: ../../../backend/app/services/progress_manager.py
  title: 'MURENA repository: backend/app/services/progress_manager.py'
- resource: ../../../frontend/src/hooks/useAnalysisProgress.ts
  title: 'MURENA repository: frontend/src/hooks/useAnalysisProgress.ts'
---

# Aggiornamenti progressivi WebSocket

## Connessione

`WS /api/v1/ws/analysis/{run_id}` invia notifiche di progresso per una run già avviata.

Messaggi previsti nel codice: aggiornamenti JSON (es. `type: progress`, `progress`, `step`, `detail`, `steps_state`) e, alla fine, `type: complete` con `run_id` e `results_url`. Gli errori usano `type: error`.

## Consumo UI

`useAnalysisProgress` apre il socket; `useAnalysis` usa l'evento di completamento per richiedere i risultati definitivi tramite REST. La perdita del WebSocket non equivale automaticamente al fallimento dell'analisi: occorre prevedere un refresh/polling dei risultati.

## Attenzione alla sicurezza

Nel sorgente ispezionato la funzione WebSocket accetta il collegamento direttamente con `websocket.accept()` e non mostra una dipendenza di autenticazione. Prima del deployment verificare **autorizzazione sulla singola run**, origine del client e privacy degli eventi, non soltanto il possesso del `run_id`. [Vedi sicurezza](../operations/security.md).
