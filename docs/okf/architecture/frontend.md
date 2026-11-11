---
type: Architecture
title: Frontend React
description: Tecnologie UI, navigazione, cache delle richieste e comunicazione con il backend.
tags:
- frontend
- react
- vite
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../frontend/package.json
  title: 'MURENA repository: frontend/package.json'
- resource: ../../../frontend/src/App.tsx
  title: 'MURENA repository: frontend/src/App.tsx'
- resource: ../../../frontend/src/api/client.ts
  title: 'MURENA repository: frontend/src/api/client.ts'
- resource: ../../../frontend/src/hooks/useAnalysis.ts
  title: 'MURENA repository: frontend/src/hooks/useAnalysis.ts'
---

# Frontend React

Il client è basato su React 19, TypeScript, React Router 7, Vite 6, TanStack Query 5 e Axios. Mappe con React Leaflet/Leaflet e clustering; grafici con Recharts; styling tramite Tailwind e componenti locali.

## Organizzazione

- `src/pages/`: ricerca, elaborazione, mappa, storico, log, impostazioni, login.
- `src/components/map/`: mappa, legenda, risultati e layer.
- `src/components/building/`: scheda edificio, dettagli, valutazione AI, energia.
- `src/components/agent/`: tracce, SQL filters, refinement e feedback.
- `src/contexts/`: Auth, Map e Settings.
- `src/api/`: client HTTP, endpoint tipizzati, DTO TypeScript.
- `src/hooks/`: collegamento tra API e stato live, progressi, mappa.

Il browser usa `VITE_API_URL` o, in mancanza, `/api/v1`; Axios legge il bearer token da `localStorage`. Il WebSocket è legato al `run_id` della ricerca. Vedi [routing UI](../frontend/ui-routes.md) e [stato/rete](../frontend/state-and-network.md).
