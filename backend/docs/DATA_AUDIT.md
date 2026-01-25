# 📊 DATA AUDIT REPORT

**Data:** 25 Gennaio 2026  
**Autore:** Data Engineering Analysis  
**Scope:** Backend Dataset Cleanup & Verification

---

## 📁 Executive Summary

Questa analisi ha verificato l'integrità e l'utilizzo dei dataset nel backend, identificando:

- ✅ **41 colonne attivamente usate** nel codice
- 🗑️ **7 colonne "fantasma"** da rimuovere
- ✅ **Punteggi APE nella scala corretta** (1-5 per singoli, 6-20 per totale)
- ⚠️ **2 file legacy** da archiviare
- ✅ **1 file APE dettagliato** correttamente in uso

---

## 1️⃣ Dataset Principale: `immobili_with_meta_and_ape_full_cleaned.parquet`

### Statistiche
| Metrica | Valore |
|---------|--------|
| Righe totali | 14,877 |
| Colonne totali | 48 |
| Colonne usate | 41 |
| Colonne da rimuovere | 7 |

### Colonne USATE (41)

#### Core Identifiers
- `id`, `codice_comune`, `foglio`, `particella`, `subalterno`

#### Location
- `latitudine`, `longitudine`, `indirizzo`, `numero_civico`, `zona_omi`

#### Property Attributes
- `superficie_di_riferimento_mq`, `natura_del_bene`, `tipologia_bene_immobile`
- `epoca_costruzione`, `vincolo_culturale_paesaggistico`, `natura_giuridica_del_bene`
- `utilizzo_del_bene`, `finalita`

#### Rental Info
- `tipo_detenzione_a_terzi`, `canone_annuale`, `data_decorrenza`

#### Meta-immobile
- `numero_immobili_per_catasto`, `id_list`, `meta_immobile`

#### APE References
- `lista_file_ape`, `list_file_ape_filtered`, `list_file_ape_filtered_parsed`

#### APE Scores (NUOVA SCALA ✅)
| Colonna | Min | Max | Media | Non-null |
|---------|-----|-----|-------|----------|
| `ape_score_classe` | 1.0 | 5.0 | 1.93 | 714 |
| `ape_score_impianto` | 2.0 | 5.0 | 2.18 | 714 |
| `ape_score_involucro` | 1.0 | 5.0 | 1.07 | 714 |
| `ape_score_rinnovabili` | 2.0 | 5.0 | 2.19 | 714 |
| `ape_score_total` | 6.0 | 17.0 | 7.37 | 714 |

#### APE Class Info
- `classe_energetica_ape`, `epglnren_ape`, `classe_target_ape`

#### POI Scores
- `sanita`, `mobilita`, `verde`, `sport`, `commerciale`, `educazione`

### Colonne da RIMUOVERE (7)

| Colonna | Motivo |
|---------|--------|
| `coordinate_ds_coerenti` | Non referenziata nel codice |
| `list_file_ape_validated` | Non referenziata nel codice |
| `fonte_coordinate_usata` | Non referenziata nel codice |
| `list_file_ape_validated_norm` | Non referenziata nel codice |
| `plot_filename` | Non referenziata nel codice |
| `id_left` | Artifact da merge pandas |
| `id_list_formatted` | Non referenziata nel codice |

---

## 2️⃣ Verifica Scala Punteggi

### Nuova Scala (Corretta)
- **Singoli assi:** 1-5 (Classe, Impianto, Involucro, Rinnovabili)
- **Totale:** 6-20 (somma dei 4 assi + 2 di baseline)

### Risultato Verifica
✅ **TUTTI I PUNTEGGI SONO NELLA SCALA CORRETTA**

```
ape_score_classe:      1.0 - 5.0  ✅
ape_score_impianto:    2.0 - 5.0  ✅
ape_score_involucro:   1.0 - 5.0  ✅
ape_score_rinnovabili: 2.0 - 5.0  ✅
ape_score_total:       6.0 - 17.0 ✅
```

---

## 3️⃣ File Legacy Analysis

### File Analizzati

| File | Righe | Colonne | Stato |
|------|-------|---------|-------|
| `immobili_with_meta_only.parquet` | 701 | 35 | ⚠️ Legacy |
| `immobili_with_ape_only.parquet` | 614 | 35 | ⚠️ Legacy |
| `ape_detailed_data.parquet` | 1,267 | 63 | ✅ Attivo |

### Decisione: File `_only.parquet`

**Stato:** Configurati in `config.py` ma **MAI usati effettivamente** dal codice applicativo.

**Riferimenti trovati:**
- `config.py`: Definiti come `DATASET_META` e `DATASET_APE`
- `real_estate_service.py`: Mappati in `dataset_paths` ma il frontend usa sempre `full`
- **Nessun endpoint API** li richiama direttamente

**Raccomandazione:** 
1. ✅ **Eliminare** i file da `FOLDER_META/`
2. ✅ **Rimuovere** le configurazioni `DATASET_META` e `DATASET_APE` da `config.py`
3. ✅ **Aggiornare** `dataset_options` per rimuovere le opzioni inutilizzate

### File `ape_detailed_data.parquet` 

**Stato:** ✅ **Attivamente utilizzato**

**Utilizzo:**
- Endpoint `/api/v1/ape/{building_id}` per dettagli APE
- `energy_score_calculator.py` per calcolo costi energetici
- Contiene 63 colonne con dati dettagliati su impianti, consumi, interventi suggeriti

---

## 4️⃣ APE Agent Context Issue

### Problema Identificato
L'APE Agent riceve solo i **nomi delle colonne** del dataset principale, non i dati dettagliati APE:

```python
# graph_agent.py line 395
return self.ape_agent.run(query, dataset_metadata.get("columns", []))
```

### Impatto
L'Agent vede:
- `ape_score_classe`, `ape_score_impianto`, etc. (nomi colonne)
- **NON vede** i 63 campi dettagliati di `ape_detailed_data.parquet`

### Raccomandazione
Arricchire il prompt dell'APE Agent con statistiche aggregate da `ape_detailed_data.parquet`:
- Distribuzione classi energetiche
- Range consumi medi (kWh/mq)
- Tipi impianto più comuni
- % immobili con fonti rinnovabili

---

## 5️⃣ Azioni Correttive

### Immediato (Script Pronto)

```bash
# Dal folder backend/
python scripts/cleanup_dataset.py --backup --force
```

Questo:
1. Crea backup con timestamp in `data/FOLDER_META/_backup/`
2. Rimuove le 7 colonne inutilizzate
3. Salva il dataset pulito

### Post-Cleanup

1. **Eliminare file legacy:**
   ```bash
   del data\FOLDER_META\immobili_with_meta_only.parquet
   del data\FOLDER_META\immobili_with_ape_only.parquet
   ```

2. **Aggiornare `config.py`:**
   - Rimuovere `DATASET_META` e `DATASET_APE`
   - Aggiornare `dataset_options` property

---

## 6️⃣ Schema Finale Raccomandato

Dopo la pulizia, il dataset avrà **41 colonne**:

```
id, codice_comune, foglio, particella, subalterno,
superficie_di_riferimento_mq, natura_del_bene, indirizzo, numero_civico,
latitudine, longitudine, tipologia_bene_immobile, epoca_costruzione,
vincolo_culturale_paesaggistico, natura_giuridica_del_bene, utilizzo_del_bene,
finalita, tipo_detenzione_a_terzi, canone_annuale, data_decorrenza,
numero_immobili_per_catasto, id_list, meta_immobile,
lista_file_ape, list_file_ape_filtered, list_file_ape_filtered_parsed,
classe_energetica_ape, epglnren_ape, classe_target_ape,
ape_score_classe, ape_score_impianto, ape_score_involucro,
ape_score_rinnovabili, ape_score_total,
zona_omi, sanita, mobilita, verde, sport, commerciale, educazione
```

---

## ✅ Checklist di Verifica

- [x] Schema dataset principale ispezionato
- [x] Colonne mappate (usate vs inutilizzate)
- [x] Punteggi verificati nella nuova scala (1-5)
- [x] File legacy identificati e analizzati
- [x] Script di pulizia creato e testato
- [x] Pulizia eseguita con backup
- [x] File `_only.parquet` eliminati
- [x] `config.py` aggiornato (rimossi DATASET_META, DATASET_APE)
- [x] `real_estate_service.py` aggiornato

---

## 📁 Struttura Finale FOLDER_META

```
backend/data/FOLDER_META/
├── _backup/
│   └── immobili_with_meta_and_ape_full_cleaned_backup_20260125_XXXXXX.parquet
├── ape_detailed_data.parquet          (1,267 righe, 63 colonne) - APE dettagliato
└── immobili_with_meta_and_ape_full_cleaned.parquet  (14,877 righe, 41 colonne) - MAIN
```
