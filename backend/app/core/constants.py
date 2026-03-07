from typing import Dict, List

# Legenda Punteggi (1-5) per APE e POI
SCORE_LEGEND = """LEGENDA PUNTEGGI (tutti su scala 1-5, dove 5=ottimo):

APE (Efficienza Energetica):
- ape_score_classe: Classe energetica (5=A1-A4, 3=B-E, 1=F-G)
- ape_score_impianto: Qualità impianto termico (5=Pompa calore/Teleriscaldamento, 3=Condensazione/Biomassa, 1=Tradizionale)
- ape_score_involucro: Isolamento edificio (5=Ottimo, 3=Medio, 1=Scarso/Assente)
- ape_score_rinnovabili: Presenza fonti rinnovabili (5=Sì, 1=No)
- ape_score_total: Media complessiva dei punteggi energetici

POI (Servizi di Prossimità):
- sanita: Vicinanza a servizi sanitari (Ospedali, farmacie)
- mobilita: Accessibilità trasporti pubblici (Metro, bus, stazioni)
- verde: Presenza aree verdi (Parchi, giardini)
- sport: Vicinanza impianti sportivi (Palestre, piscine)
- commerciale: Servizi commerciali (Negozi, supermercati)
- educazione: Scuole e istruzione (Scuole, università)
"""

# Legenda specifica per APE Agent (solo APE)
APE_SCORE_LEGEND = """LEGENDA PUNTEGGI APE (scala 1-5, dove 5=ottimo):

- ape_score_classe: Classe energetica (5=A1-A4, 3=B-E, 1=F-G)
- ape_score_impianto: Qualità impianto termico (5=Pompa calore/Teleriscaldamento, 3=Condensazione/Biomassa, 1=Tradizionale)
- ape_score_involucro: Isolamento edificio (5=Ottimo, 3=Medio, 1=Scarso/Assente)
- ape_score_rinnovabili: Presenza fonti rinnovabili (5=Sì, 1=No)
- ape_score_total: Media complessiva dei punteggi energetici
"""

# Colonne specifiche per Location Agent
LOCATION_AGENT_COLUMNS: List[str] = [
    "indirizzo",
    "numero_civico",
    "latitudine",
    "longitudine",
    "zona_omi",
]

# Colonne specifiche per APE Agent
APE_AGENT_COLUMNS: List[str] = [
    "classe_energetica_ape",
    "epglnren_ape",
    "classe_target_ape",
    "ape_score_classe",
    "ape_score_impianto",
    "ape_score_involucro",
    "ape_score_rinnovabili",
    "ape_score_total",
]

# Colonne specifiche per Property Technical Agent
PROPERTY_TECHNICAL_AGENT_COLUMNS: List[str] = [
    "tipologia_bene_immobile",
    "epoca_costruzione",
    "id",
    "codice_comune",
    "foglio",
    "particella",
    "subalterno",
    "numero_immobili_per_catasto",
    "superficie_di_riferimento_mq",
]

# Colonne specifiche per Normative Agent
NORMATIVE_AGENT_COLUMNS: List[str] = [
    "superficie_di_riferimento_mq",
    "tipologia_bene_immobile",
]

# Colonne specifiche per POI Agent
POI_AGENT_COLUMNS: List[str] = [
    "sanita",
    "mobilita",
    "verde",
    "sport",
    "commerciale",
    "educazione",
]


# Unione di tutte le colonne visibili agli agenti e quindi filtrabili via SQL
ALL_AGENT_COLUMNS_SET = set(
    LOCATION_AGENT_COLUMNS +
    APE_AGENT_COLUMNS +
    PROPERTY_TECHNICAL_AGENT_COLUMNS +
    NORMATIVE_AGENT_COLUMNS +
    POI_AGENT_COLUMNS
)

SQL_FILTERABLE_COLUMNS: List[str] = sorted(list(ALL_AGENT_COLUMNS_SET))
ALL_AGENT_COLUMNS: List[str] = SQL_FILTERABLE_COLUMNS

# Categorie POI per la documentazione
POI_CATEGORIES: Dict[str, str] = {
    "sanita": "Ospedali, farmacie, ambulatori",
    "mobilita": "Metro, bus, stazioni",
    "verde": "Parchi, giardini",
    "sport": "Palestre, piscine, campi",
    "commerciale": "Negozi, supermercati",
    "educazione": "Scuole, università",
}

# Oggetto globale che conterrà i metadati aggiornati a runtime
DB_METADATA = {
    "_metadata_version": "2.0",
    "score_legends": {
        "ape_scores": APE_SCORE_LEGEND,
        "poi_scores": SCORE_LEGEND
    },
    "filterable_columns": SQL_FILTERABLE_COLUMNS,
    "fields": {}  # Qui verranno inserite le statistiche e i valori categorici
}


def update_runtime_metadata(df):
    """
    Popola DB_METADATA con le statistiche reali del dataframe caricato.
    Sostituisce la necessità di file JSON esterni.
    """
    try:
        from datetime import datetime
        import pandas as pd
        
        DB_METADATA["_last_updated"] = datetime.now().strftime("%Y-%m-%d")
        df_columns = set(df.columns)
        
        # Sincronizza colonne filtrabili
        DB_METADATA["filterable_columns"] = [c for c in SQL_FILTERABLE_COLUMNS if c in df_columns]
        
        # Liste di colonne da analizzare
        categorical = ["codice_comune", "tipologia_bene_immobile", "epoca_costruzione", "classe_energetica_ape"]
        numerical = [
            "superficie_di_riferimento_mq", "ape_score_total", 
            "sanita", "mobilita", "verde", "sport", "commerciale", "educazione"
        ]
        
        # Reset fields
        DB_METADATA["fields"] = {}
        
        for col in categorical + numerical:
            if col in df.columns:
                meta = {}
                if col in categorical:
                    # Estrai valori unici e ordina
                    unique_vals = sorted([str(v) for v in df[col].dropna().unique()])
                    meta["values"] = unique_vals
                    meta["is_truncated"] = False
                else:
                    # Calcola statistiche numeriche
                    series = pd.to_numeric(df[col], errors='coerce').dropna()
                    if not series.empty:
                        meta.update({
                            "min": round(float(series.min()), 2),
                            "max": round(float(series.max()), 2),
                            "mean": round(float(series.mean()), 2),
                            "median": round(float(series.median()), 2),
                            "percentiles": {
                                "25%": round(float(series.quantile(0.25)), 2),
                                "75%": round(float(series.quantile(0.75)), 2)
                            }
                        })
                DB_METADATA["fields"][col] = meta
                
    except Exception as e:
        from app.utils.logger import logger
        logger.error(f"Failed to update runtime metadata: {e}")
