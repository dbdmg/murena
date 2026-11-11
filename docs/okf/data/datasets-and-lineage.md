---
type: Dataset
title: Dataset e provenienza
description: Origine e trasformazioni dei dati demo e sperimentali; dipendenze dai file esterni.
tags:
- data
- lineage
- parquet
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../README.md
  title: 'MURENA repository: README.md'
- resource: ../../../backend/data/metadata/create_demo_dataset.py
  title: 'MURENA repository: backend/data/metadata/create_demo_dataset.py'
- resource: ../../../backend/data/metadata/create_estate_dataset.py
  title: 'MURENA repository: backend/data/metadata/create_estate_dataset.py'
- resource: ../../../backend/app/data/loaders.py
  title: 'MURENA repository: backend/app/data/loaders.py'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Dataset e provenienza

## Dataset utilizzati

- **Demo sintetica:** `backend/data/metadata/create_demo_dataset.py` genera `backend/data/metadata/estates.parquet` (default `n=1500`, seed `42`), per Torino. I record `DEMO-*` e la descrizione testuale riportano la natura sintetica.
- **Pipeline di origine reale:** `backend/data/metadata/create_estate_dataset.py` ed `backend/data/metadata/pois_download.py` preparano i dati da sorgenti APE/OSM, quando effettivamente disponibili. I raw XML APE non sono inclusi nel repository fornito.
- **Paper:** ricostruisce un inventario di circa 90.000 record reali, deduplicati, aggregati in meta-building e arricchiti con coordinate, OMI, POI e regole strutturate.

## Tracciato logico

```text
APE XML + riferimenti catastali
  -> correzioni, normalizzazione, deduplicazione
  -> unità singole / meta-building
  -> geocoding + OMI + POI + macro-score
  -> estates.parquet -> DuckDB -> query/ranking
```

Il fallback sintetico riproduce campi coerenti con lo schema applicativo, non tutta la distribuzione statistica reale. Gli score derivati dalla demo non vanno confrontati con i risultati scientifici del paper.

## Percorsi

`app/data/loaders.py` gestisce loading/alias compatibili; `app/data/processors.py` contiene trasformazioni e funzioni geospaziali. Il livello di compatibilità mappa anche nomi di colonne italiani preesistenti su alias inglesi.
