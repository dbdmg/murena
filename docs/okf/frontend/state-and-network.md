---
type: Frontend Reference
title: Stato, dati e rete lato frontend
description: TanStack Query, AuthContext, useAnalysis, Axios e comunicazione WS.
tags:
- frontend
- state
- http
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../frontend/src/App.tsx
  title: 'MURENA repository: frontend/src/App.tsx'
- resource: ../../../frontend/src/api/client.ts
  title: 'MURENA repository: frontend/src/api/client.ts'
- resource: ../../../frontend/src/contexts/AuthContext.tsx
  title: 'MURENA repository: frontend/src/contexts/AuthContext.tsx'
- resource: ../../../frontend/src/hooks/useAnalysis.ts
  title: 'MURENA repository: frontend/src/hooks/useAnalysis.ts'
- resource: ../../../frontend/src/hooks/useAnalysisProgress.ts
  title: 'MURENA repository: frontend/src/hooks/useAnalysisProgress.ts'
---

# Stato, dati e rete lato frontend

## Flusso applicativo

1. `AuthContext` mantiene l'utente e il login; il bearer token è recuperato da `localStorage` tramite l'interceptor Axios.
2. `useAnalysis.startAnalysis()` esegue la POST e memorizza `run_id`.
3. `useAnalysisProgress` sottoscrive lo streaming WS per visualizzare lo stato in `ProcessingPage`.
4. Al completamento, `useAnalysis` richiede via REST l'oggetto `AnalysisResults`.
5. Le pagine map/history consultano endpoint specifici e condividono parte dello stato tramite `MapContext` e `SettingsContext`.

## Cache

In `App.tsx` il `QueryClient` disabilita il refetch al focus, configura un retry e imposta `staleTime` a 5 minuti. Non assumere che ogni query remota passi da TanStack Query: alcuni hook chiamano direttamente le API Axios.

## Configurazione della rete

`apiClient` usa `VITE_API_URL || '/api/v1'`. L'interceptor prova ad allegare l'header `Authorization: Bearer ...` e il timeout è di 30 secondi per la singola richiesta HTTP. L'analisi completa è asincrona e può richiedere più tempo.

Controllare [contratti API](../api/contracts.md) e [WebSocket](../api/progress-events.md) prima di cambiare i DTO.
