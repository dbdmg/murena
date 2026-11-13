---
type: Data Transformation
title: Geocoding, OMI e punteggi POI
description: Macro-categorie di prossimità e modello spaziale usato nei dati e nel paper.
tags:
- geospatial
- poi
- osm
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/data/metadata/pois_download.py
  title: 'MURENA repository: backend/data/metadata/pois_download.py'
- resource: ../../../backend/data/metadata/amenities_config.py
  title: 'MURENA repository: backend/data/metadata/amenities_config.py'
- resource: ../../../backend/app/data/processors.py
  title: 'MURENA repository: backend/app/data/processors.py'
- resource: ../../../backend/app/services/map_service.py
  title: 'MURENA repository: backend/app/services/map_service.py'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Geocoding, OMI e punteggi POI

## Dati di contesto

- **OSM POI:** importazione e classificazione delle amenities, comprese geometrie puntuali e centroidi.
- **OMI:** associazione a zone di mercato immobiliare (`omi_zone`); il progetto contiene `data/static_data/omi_zones.geojson`.
- **Layer mappa:** l'endpoint `/api/v1/map/overlays/omi` serve il GeoJSON OMI configurato. In UI è etichettato `Cadastral Zones`, pur rappresentando le zone OMI di mercato; `/api/v1/layers/pois` legge `data/metadata/pois_by_category.json` e restituisce i punti delle categorie selezionate, filtrabili per viewport. L'overlay `municipi` non è più supportato.
- **Geocoding:** `app.data.loaders.get_coordinates` risolve landmark locali o interroga Nominatim, con cache in memoria e su file. Il LocationAgent lo usa per filtrare i luoghi estratti; SAGE lo usa anche come verifica best-effort quando la query contiene una città esplicita ma il parser ha classificato la località come critica. La verifica non riuscita lascia attivo il chiarimento. Le richieste Nominatim usano `NOMINATIM_USER_AGENT`; le interazioni esterne inviano il testo del luogo.
- **Macro-score:** colonne `healthcare`, `mobility`, `green`, `sport`, `commercial`, `education` nello schema corrente. Nel testo del paper sono descritte macro-categorie e soglie di camminabilità.

## Metodo paper

Le distanze ai POI vengono **precalcolate** all'ingestion, anziché ricercare tutti i servizi durante ogni query. Il contributo di un servizio a distanza `x` decresce secondo una funzione della forma `exp(-(x/(S·U))^3)`; i valori sono poi normalizzati su scala percentile 0–100. Le soglie riportate nel manoscritto sono circa 340/680/1360 metri per gruppi di walkability.

## Implementazione e cautele

Il processo di ingestion e le trasformazioni risiedono nel codice di metadata e in `app/data/processors.py`. Il catalogo POI contiene ID e coordinate per categoria e sottotipo amenity; non include necessariamente nomi commerciali o dettagli descrittivi. Non assumere che il dataset sintetico riproduca il procedimento OSM: il suo generatore usa una distribuzione parametrica semplificata.

[Schema Parquet](estate-schema.md) · [ProximityAgent](../agents/proximity.md).
