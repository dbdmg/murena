---
type: Data Schema
title: Schema Parquet immobili
description: Campi presenti nel dataset sintetico e colonne ammesse ai technical agent.
tags:
- data
- schema
- duckdb
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/data/metadata/create_demo_dataset.py
  title: 'MURENA repository: backend/data/metadata/create_demo_dataset.py'
- resource: ../../../backend/app/core/constants.py
  title: 'MURENA repository: backend/app/core/constants.py'
- resource: ../../../backend/app/services/analysis/executor.py
  title: 'MURENA repository: backend/app/services/analysis/executor.py'
---

# Schema Parquet immobili

## Asset

Il dataset fisico è `backend/data/metadata/estates.parquet`; DuckDB lo espone con viste `base_properties`, `PROPERTIES`, `ESTATES`, `IMMOBILI` quando usa la lettura Parquet nativa. È uno schema *di riferimento della demo*, non una enumerazione garantita di ogni colonna del dataset reale.

### Identificativi e localizzazione

`id`, `address`, `house_number`, `latitude`, `longitude`, `city`, `codice_comune`, `omi_zone`.

### Catasto, tipologia e dimensioni

`cadastral_sheet`, `cadastral_parcel`, `cadastral_subaltern`, `cadastral_units_count`, `surface_area`, `property_type`, `construction_period`, `construction_year`, `meta_building`, `is_meta`, `id_list`.

### Energia

`energy_class`, `epglnren_ape`, `classe_target_ape`, `energy_score_class`, `energy_score_plant`, `energy_score_envelope`, `energy_score_renewables`, `energy_score_total`, `heating_system`.

### Prossimità

`healthcare`, `mobility`, `green`, `sport`, `commercial`, `education`.

### Proprietà, normativa e contesto

`legal_nature`, `cultural_constraint`, `annual_rent`, `description`.

## Semantica e vincoli

- Coordinate (`latitude`, `longitude`) in gradi geografici; `surface_area` esprime metri quadrati.
- `epglnren_ape` è un indicatore energetico; gli `energy_score_*` rappresentano sottopunteggi, non certificazioni.
- Le macro-categorie POI sono score percentili 0–100; lo score totale energetico nella demo è somma di 4 valori nell'intervallo 1–5.
- `backend/app/core/constants.py` definisce le **colonne visibili/filtrabili** dai technical agent. Alcuni campi del dataset restano solo per visualizzazione.

Attenzione al diverso naming di risposta: l'API `ProximityScores` usa `greenery` e `commerce`, mentre la tabella impiega `green` e `commercial`. È necessaria mappatura esplicita quando si modifica il contratto.
