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

## Comportamenti automatici importanti

- `.env` deve esistere o il launcher si interrompe.
- **La SQLite locale è cancellata a ogni avvio** del launcher.
- Se manca `estates.parquet`, il launcher crea un dataset **sintetico**.
- `--real-data-init` tenta la pipeline con fonti APE/OSM reali, che devono essere fornite separatamente.
- `--skip-init` salta l'inizializzazione del dataset.

## Verifica iniziale

`GET http://localhost:8000/health` restituisce lo stato del backend; gli endpoint documentati sono consultabili in `/docs` quando `DEBUG` è abilitato. La salute del server non dimostra che il provider LLM o le sorgenti dati siano correttamente configurati.
