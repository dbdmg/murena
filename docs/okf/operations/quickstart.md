---
type: Playbook
title: Avvio locale e prerequisiti
description: Installazione dipendenze, configurazione minima e comando per avviare la demo.
tags:
- operations
- setup
- playbook
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../README.md
  title: 'MURENA repository: README.md'
- resource: ../../../AGENTS.md
  title: 'MURENA repository: AGENTS.md'
- resource: ../../../run_app.py
  title: 'MURENA repository: run_app.py'
- resource: ../../../frontend/package.json
  title: 'MURENA repository: frontend/package.json'
---

# Avvio locale e prerequisiti

## Dipendenze

Python **3.12+** (vincolo di `pyproject.toml`), `uv` per le dipendenze e Node/npm per il frontend. Per l'inferenza reale serve un provider LLM configurato e raggiungibile.

```bash
# Dalla root del repository
uv sync
cp backend/.env.example backend/.env
# Editare backend/.env localmente, senza committare segreti
python run_app.py
```

Il backend è in genere sulla porta `8000`, il frontend Vite sulla `5173` (il launcher può ricercare porte alternative). Senza npm il launcher può avviare il solo backend; in alternativa:

```bash
python run_app.py --backend-only
cd frontend && npm install && npm run dev
```

## Frontend demo senza backend

```bash
cd frontend
npm install
npm run dev:demo
```

Non occorrono Python, backend, dataset immobiliari o provider LLM. Il browser usa un accesso locale e un simulatore basato sugli scenari v3; il pannello consente anche di importare altri JSON nello stesso formato. I triplets contengono query e risposte, non immobili: la demo non genera risultati di ricerca.

Per una build statica: `npm run build:demo`, quindi `npm run preview` oppure servire `frontend/dist/` con fallback SPA. Il flag demo è incorporato nella build. Per il frontend con backend usare `npm run dev` / `npm run build`. Test del simulatore: `npm run test:demo`. Dettagli e limiti in [Percorsi e schermate](../frontend/ui-routes.md#modalità-demo-offline-con-scenari-pronti).

### Demo pubblica

La build statica corrente è pubblicata su [murena-conversational.vercel.app](https://murena-conversational.vercel.app), nel progetto Vercel `murena-conversational`. È distinta dalla demo storica [murena.vercel.app](https://murena.vercel.app). La distribuzione usa `frontend/vercel.json` per il fallback delle rotte React e non richiede backend, credenziali LLM o variabili runtime. Per aggiornare gli asset pubblici, autenticarsi con Vercel CLI ed eseguire dalla cartella `frontend/`:

```bash
npm run build:demo
vercel deploy dist --project murena-conversational --prod --yes --local-config vercel.json
```

## Comportamenti automatici importanti

- `.env` deve esistere o il launcher si interrompe.
- **La SQLite locale è cancellata a ogni avvio** del launcher.
- Se manca `estates.parquet`, il launcher crea un dataset **sintetico**.
- `--real-data-init` tenta la pipeline con fonti APE/OSM reali, che devono essere fornite separatamente.
- `--skip-init` salta l'inizializzazione del dataset.

## Verifica iniziale

`GET http://localhost:8000/health` restituisce lo stato del backend; gli endpoint documentati sono consultabili in `/docs` quando `DEBUG` è abilitato. La salute del server non dimostra che il provider LLM o le sorgenti dati siano correttamente configurati.
