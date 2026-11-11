---
type: Security Review
title: 'Sicurezza: osservazioni da revisione statica'
description: Rischi evidenti nel codice e verifiche prioritarie prima di una distribuzione reale.
tags:
- security
- risk
- review
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/core/config.py
  title: 'MURENA repository: backend/app/core/config.py'
- resource: ../../../backend/app/api/v1/endpoints/websockets.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/websockets.py'
- resource: ../../../backend/app/services/llm/agents/sql_agent.py
  title: 'MURENA repository: backend/app/services/llm/agents/sql_agent.py'
- resource: ../../../backend/app/services/analysis/executor.py
  title: 'MURENA repository: backend/app/services/analysis/executor.py'
- resource: ../../../run_app.py
  title: 'MURENA repository: run_app.py'
- resource: ../../../frontend/src/api/client.ts
  title: 'MURENA repository: frontend/src/api/client.ts'
---

# Sicurezza: osservazioni da revisione statica

## Punti da trattare prima del deployment

1. **Segreto JWT in fallback:** `Settings.SECRET_KEY` ha un valore di default codificato nel sorgente. Impostare un segreto unico da ambiente o secret manager e **rimuovere il fallback incorporato**; ruotare la chiave se fosse stata usata fuori dalla demo.
2. **Credenziali demo:** la documentazione menziona un account predefinito noto; disabilitarlo/ruotarlo negli ambienti condivisi.
3. **WebSocket progressi:** l'endpoint accetta `run_id` senza controllo visibile di identità/autorizzazione nel decorator/handler. Aggiungere autenticazione, verifica di ownership e validazione origin.
4. **Controlli SQL limitati:** `_validate_sql` controlla SELECT e keyword vietate via stringa; il controllo **non equivale** a un AST allowlist robusto. Eseguire query in ambiente ristretto, con budget di risorse, limitazioni filesystem/network e controlli AST.
5. **Persistenza token client:** bearer token in `localStorage` è recuperabile da script in caso di XSS; applicare adeguate difese CSP, sanitizzazione e policy token.
6. **Stato e permessi API:** verificare che lettura run, feedback, prompt overrides, tracce e log siano autorizzati per ruolo/utente; la route UI protetta non basta.
7. **Launcher:** esegue reset SQLite e avvia uvicorn con reload, appropriato allo sviluppo ma non alla produzione.

## Campo di questa valutazione

Questi sono *punti osservati staticamente*, non una prova di sfruttabilità, un penetration test o una certificazione di sicurezza. Nessuna credenziale è riportata in questo bundle.
