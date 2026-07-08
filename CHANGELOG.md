---
### [2026-07-08 08:44] - Aggiunte dipendenze geopandas e shapely
- File modificati: `pyproject.toml`, `uv.lock`
- Tipo di modifica: modifica
- Dettaglio: Aggiunte le librerie geopandas e shapely alle dipendenze del progetto. Mancando queste librerie, la funzione `get_omi_zone` falliva silenziosamente restituendo `None` per tutte le unità immobiliari, causando l'eliminazione di tutti i record nella fase finale di filtro OMI del dataset (`create_estate_dataset.py`) e portando il conteggio finale a 0 righe.
---
### [2026-07-08 08:09] - Creazione link simbolico per dati APE XML
- File modificati: `backend/data/xml` (collegamento simbolico a `/home/mdeluca/merged`)
- Tipo di modifica: aggiunta
- Dettaglio: Creato il collegamento simbolico `backend/data/xml` che punta alla directory esterna `~/merged` per consentire l'accesso ai dati APE reali XML durante l'inizializzazione del dataset.
---
