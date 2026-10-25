# Handoff: `estates.parquet` (APE Torino aggregati)

Documento autonomo per portare questo dataset in un altro progetto Cursor. Copia **questo file** insieme al parquet (o allo zip Torino). Non serve il resto di MURENA.

## Path locali

| Ruolo | Path |
|---|---|
| File canonico usato dall’app | `C:\Users\danie\_DEV\Claude\murena\backend\data\metadata\estates.parquet` |
| Copia snapshot Torino | `C:\Users\danie\_DEV\Claude\murena\backend\data\Turin\metadata\estates.parquet` |
| Bundle già impacchettato | `C:\Users\danie\_DEV\Claude\murena\backend\data\data_Turin.zip` |

Path relativo da `backend/`: `data/metadata/estates.parquet` (variabile `DATASET_FULL` in `backend/.env`).

Il parquet è **gitignored**. Non è versionato nel repo.

## Cosa è (e cosa non è)

Dataset aggregato di immobili di **Torino** costruito dagli Attestati di Prestazione Energetica (APE / EPC) SIPEE.

- **89.200 righe**, **36 colonne**, circa **8.4 MB**
- Ogni riga è un’unità catastale o un **meta-edificio** (`meta_immobile = true`) ottenuto aggregando più APE sullo stesso `foglio` + `particella`
- I certificati XML originali **non** sono nel repo e **non** sono ricostruibili da questo file
- Non è il dataset demo sintetico (1500 edifici finti, schema inglese)

Pipeline di costruzione (quando gli XML esterni sono disponibili):

1. Parse XML SIPEE (`APE_XML_PATH`, default `backend/data/xml`, assente in questo checkout)
2. Filtro comune `TARGET_COMUNE_CODE=L219` (Torino)
3. Geocoding OSM
4. Assegnazione zona OMI
5. Dedupe catastale (`foglio` / `particella` / `subalterno`, APE più recente)
6. Aggregazione meta-edifici per `foglio` + `particella`
7. Scrittura parquet

Script di build: `backend/data/metadata/create_estate_dataset.py`.

## Come caricarlo

```python
import pandas as pd

df = pd.read_parquet(r"C:\Users\danie\_DEV\Claude\murena\backend\data\metadata\estates.parquet")
```

```python
import duckdb

con = duckdb.connect()
df = con.execute(
    r"SELECT * FROM read_parquet('C:/Users/danie/_DEV/Claude/murena/backend/data/metadata/estates.parquet')"
).fetchdf()
```

DuckDB sul file raw vede **solo i nomi italiani**. Gli alias inglesi non sono nel parquet.

In MURENA, `app.data.loaders.load_and_merge_data()` aggiunge in memoria le colonne inglesi da `COMPATIBILITY_ALIASES`.

## Schema sul disco (nomi italiani)

Ordine e tipi del file locale.

### Identità e catasto

| Colonna | Tipo | Significato |
|---|---|---|
| `id` | str | ID riga. I meta-edifici usano prefisso `M` (es. `M00001`) |
| `meta_immobile` | bool | `true` se riga aggregata foglio/particella |
| `numero_immobili_per_catasto` | int64 | Unità catastali nel gruppo |
| `id_list` | str | Lista degli `id` originali aggregati (stringa) |
| `codice_comune` | str | Codice catastale comune (`L219` = Torino) |
| `foglio` | int64 | Foglio catastale |
| `particella` | int64 | Particella catastale |
| `subalterno` | int64 | Subalterno (`0` convenzionale sui meta) |
| `indirizzo` | str | Indirizzo |
| `numero_civico` | str | Civico |
| `superficie_di_riferimento_mq` | float64 | Superficie di riferimento (m²) |
| `tipologia_bene_immobile` | str | Destinazione / tipologia |
| `epoca_costruzione` | str | Epoca di costruzione |
| `data_decorrenza` | datetime64[ns] | Data di decorrenza APE |

### Provenance APE (non è il certificato)

| Colonna | Tipo | Significato |
|---|---|---|
| `lista_file_ape` | str | Lista di filename XML di origine, es. `['2019_104873_0010.xml']` |
| `list_file_ape_filtered` | str | Lista filtrata (stesso contenuto sul file locale) |
| `list_file_ape_filtered_parsed` | str | Lista filtrata/parsed (stesso contenuto sul file locale) |

Questi campi sono **solo provenance**. I body XML non sono nel dataset.

### Energia (APE)

| Colonna | Tipo | Significato |
|---|---|---|
| `classe_energetica_ape` | str | Classe energetica (A4…G) |
| `epglnren_ape` | float64 | Energia primaria non rinnovabile (kWh/m²·anno) |
| `epglren_ape` | float64 | Energia primaria rinnovabile (kWh/m²·anno) |
| `emissioni_co2` | float64 | Emissioni CO₂ |
| `classe_target_ape` | str | Classe raggiungibile dopo interventi raccomandati |
| `ape_score_classe` | int64 | Subscore classe, 1–5 |
| `ape_score_impianto` | int64 | Subscore impianto, 1–5 |
| `ape_score_involucro` | int64 | Subscore involucro, 1–5 |
| `ape_score_rinnovabili` | int64 | Subscore rinnovabili, 1–5 |
| `ape_score_total` | int64 | Somma dei quattro subscore, **4–20** (non 0–100) |

Scala score usata in MURENA:

- classe: 5 = A1–A4, 3 = B–E, 1 = F–G
- impianto: 5 = pompa di calore / teleriscaldamento, 3 = condensazione / biomasse, 1 = tradizionale
- involucro: 5 = ottimo, 3 = medio, 1 = scarso / assente
- rinnovabili: 5 = presenti, 1 = assenti

Sui meta-edifici: classe pesata per superficie, score impianto/involucro/rinnovabili = max del gruppo, consumi = min del gruppo.

### Geografia

| Colonna | Tipo | Significato |
|---|---|---|
| `latitudine` | float64 | Latitudine WGS84 |
| `longitudine` | float64 | Longitudine WGS84 |
| `zona_omi` | str | Zona OMI |

### Prossimità (percentili 0–100)

| Colonna | Tipo | Significato |
|---|---|---|
| `sanita` | float64 | Servizi sanitari |
| `mobilita` | float64 | Trasporto pubblico |
| `verde` | float64 | Aree verdi |
| `sport` | float64 | Impianti sportivi |
| `commerciale` | float64 | Servizi commerciali |
| `educazione` | float64 | Scuole / università |

## Alias inglesi (non presenti nel parquet)

Usati da API e agenti LLM dopo `load_and_merge_data()`. Mapping da `backend/app/data/loaders.py`:

| Italiano (sul disco) | Inglese (in memoria) |
|---|---|
| `indirizzo` | `address` |
| `numero_civico` | `house_number` |
| `latitudine` | `latitude` |
| `longitudine` | `longitude` |
| `zona_omi` | `omi_zone` |
| `foglio` | `cadastral_sheet` |
| `particella` | `cadastral_parcel` |
| `subalterno` | `cadastral_subaltern` |
| `superficie_di_riferimento_mq` | `surface_area` |
| `tipologia_bene_immobile` | `property_type`, `description` |
| `epoca_costruzione` | `construction_year`, `construction_period` |
| `numero_immobili_per_catasto` | `cadastral_units_count` |
| `meta_immobile` | `is_meta`, `is_meta_estate`, `meta_building` |
| `data_decorrenza` | `effective_date` |
| `classe_energetica_ape` | `energy_class` |
| `ape_score_classe` | `energy_score_class` |
| `ape_score_impianto` | `energy_score_plant` |
| `ape_score_involucro` | `energy_score_envelope` |
| `ape_score_rinnovabili` | `energy_score_renewables` |
| `ape_score_total` | `energy_score_total` |
| `lista_file_ape` | `energy_files`, `ape_file_list` |
| `sanita` | `healthcare` |
| `mobilita` | `mobility` |
| `verde` | `green`, `greenery` |
| `commerciale` | `commercial`, `commerce` |
| `educazione` | `education` |

`epglnren_ape`, `epglren_ape`, `emissioni_co2`, `classe_target_ape` restano con lo stesso nome.

## Cosa non c’è in questo file

- XML SIPEE originali (`APE_XML_PATH` / `backend/data/xml`)
- `ape_detailed_data.parquet` (dettaglio per-certificato, assente)
- Campi XML droppati in build: tipo/anno ACS e riscaldamento, fonti rinnovabili grezze, qualità involucro estate/inverno, piano, payback, potenza nominale, certificatore, superfici involucro
- Dataset paper “raw”: questo è già l’aggregato catastale

Per rigenerare da XML servono fonti esterne non in repo e `python run_app.py --real-data-init` / `create_estate_dataset.py`.

## Trappola SQL (già vista in MURENA)

Una query tipo:

```sql
SELECT * FROM ESTATES
WHERE haversine_km(latitude, longitude, 45.0622, 7.6785) <= 3.0
```

fallisce sul parquet nativo:

```text
Referenced column "latitude" not found
Candidate bindings: "latitudine", "longitudine", ...
```

Workaround:

1. Usare i nomi italiani: `haversine_km(latitudine, longitudine, ...)`
2. Oppure caricare con `load_and_merge_data()` e registrare il DataFrame in DuckDB
3. Oppure creare una vista DuckDB con alias inglesi (come in `backend/app/services/analysis/executor.py`, commit sul branch `demo`)

## Come usarlo in un nuovo progetto

1. Copia `estates.parquet` (o scompatta `data_Turin.zip`)
2. Copia questo markdown nel nuovo workspace
3. Leggi con pandas o DuckDB
4. Se vuoi i nomi inglesi, applica la tabella alias sopra
5. Non aspettarti gli XML: `lista_file_ape` è solo un riferimento di filename

Esempio minimo di alias in pandas:

```python
ALIASES = {
    "indirizzo": "address",
    "latitudine": "latitude",
    "longitudine": "longitude",
    "superficie_di_riferimento_mq": "surface_area",
    "classe_energetica_ape": "energy_class",
    "ape_score_total": "energy_score_total",
    "sanita": "healthcare",
    "mobilita": "mobility",
}

for src, dst in ALIASES.items():
    if src in df.columns and dst not in df.columns:
        df[dst] = df[src]
```
