from typing import Dict, List

# Score legend (1-5) for energy and proximity
SCORE_LEGEND = """SCORE LEGEND (all on 1-5 scale, where 5=excellent):

Energy (energy efficiency):
- energy_score_class: Energy class (5=A1-A4, 3=B-E, 1=F-G)
- energy_score_plant: Thermal plant quality (5=Heat pump/District heating, 3=Condensation/Biomass, 1=Traditional)
- energy_score_envelope: Building insulation (5=Excellent, 3=Medium, 1=Poor/None)
- energy_score_renewables: Renewable energy sources present (5=Yes, 1=No)
- energy_score_total: Overall average of energy scores

Proximity (proximity services):
- healthcare: Proximity to healthcare services (Hospitals, pharmacies)
- mobility: Public transport accessibility (Metro, bus, stations)
- green: Presence of green areas (Parks, gardens)
- sport: Proximity to sports facilities (Gyms, pools)
- commercial: Commercial services (Shops, supermarkets)
- education: Schools and education (Schools, universities)
"""

# Specific legend for Energy agent
ENERGY_SCORE_LEGEND = """ENERGY SCORE LEGEND (1-5 scale, where 5=excellent):

- energy_score_class: Energy class (5=A1-A4, 3=B-E, 1=F-G)
- energy_score_plant: Thermal plant quality (5=Heat pump/District heating, 3=Condensation/Biomass, 1=Traditional)
- energy_score_envelope: Building insulation (5=Excellent, 3=Medium, 1=Poor/None)
- energy_score_renewables: Renewable energy sources present (5=Yes, 1=No)
- energy_score_total: Overall average of energy scores
"""

# Columns for Location agent
LOCATION_AGENT_COLUMNS: List[str] = [
    "address",
    "house_number",
    "latitude",
    "longitude",
    "omi_zone",
]

# Columns for Energy agent
ENERGY_AGENT_COLUMNS: List[str] = [
    "energy_class",
    "epglnren_ape",
    "classe_target_ape",
    "energy_score_class",
    "energy_score_plant",
    "energy_score_envelope",
    "energy_score_renewables",
    "energy_score_total",
]

# Columns for Building agent
BUILDING_AGENT_COLUMNS: List[str] = [
    "property_type",
    "construction_period",
    "id",
    "codice_comune",
    "foglio",
    "particella",
    "subalterno",
    "numero_immobili_per_catasto",
    "surface_area",
]

# Columns for Regulatory agent
REGULATORY_AGENT_COLUMNS: List[str] = [
    "surface_area",
    "property_type",
]

# Columns for Proximity agent
PROXIMITY_AGENT_COLUMNS: List[str] = [
    "healthcare",
    "mobility",
    "green",
    "sport",
    "commercial",
    "education",
]


# Union of all columns visible to agents and thus filterable via SQL
ALL_AGENT_COLUMNS_SET = set(
    LOCATION_AGENT_COLUMNS +
    ENERGY_AGENT_COLUMNS +
    BUILDING_AGENT_COLUMNS +
    REGULATORY_AGENT_COLUMNS +
    PROXIMITY_AGENT_COLUMNS
)

SQL_FILTERABLE_COLUMNS: List[str] = sorted(list(ALL_AGENT_COLUMNS_SET))
ALL_AGENT_COLUMNS: List[str] = SQL_FILTERABLE_COLUMNS

# Proximity categories for documentation
PROXIMITY_CATEGORIES: Dict[str, str] = {
    "healthcare": "Hospitals, pharmacies, clinics",
    "mobility": "Metro, bus, stations",
    "green": "Parks, gardens",
    "sport": "Gyms, pools, courts",
    "commercial": "Shops, supermarkets",
    "education": "Schools, universities",
}

# Column mapping from database (Italian) to MURENA (English)
COLUMN_MAPPING: Dict[str, str] = {
    # Proximity pillars
    "sanita": "healthcare",
    "mobilita": "mobility",
    "verde": "green",
    "sport": "sport",
    "commerciale": "commercial",
    "educazione": "education",
    # Energy scores
    "ape_score_classe": "energy_score_class",
    "ape_score_impianto": "energy_score_plant",
    "ape_score_involucro": "energy_score_envelope",
    "ape_score_rinnovabili": "energy_score_renewables",
    "ape_score_total": "energy_score_total",
    "ape_score": "energy_score",
    # General attributes
    "indirizzo": "address",
    "numero_civico": "house_number",
    "zona_omi": "omi_zone",
    "superficie_di_riferimento_mq": "surface_area",
    "tipologia_bene_immobile": "property_type",
    "epoca_costruzione": "construction_period",
    "finalita": "purpose",
    "classe_energetica_ape": "energy_class",
    "latitudine": "latitude",
    "longitudine": "longitude"
}

# Global object containing updated runtime metadata
DB_METADATA = {
    "_metadata_version": "2.0",
    "score_legends": {
        "energy_scores": ENERGY_SCORE_LEGEND,
        "proximity_scores": SCORE_LEGEND
    },
    "filterable_columns": SQL_FILTERABLE_COLUMNS,
    "fields": {}  # Populated with statistics and categorical values at runtime
}


def update_runtime_metadata(df):
    """
    Populates DB_METADATA with real statistics from the loaded dataframe.
    Replaces the need for external JSON files.
    """
    try:
        from datetime import datetime
        import pandas as pd
        
        DB_METADATA["_last_updated"] = datetime.now().strftime("%Y-%m-%d")
        df_columns = set(df.columns)
        
        # Synchronize filterable columns
        DB_METADATA["filterable_columns"] = [c for c in SQL_FILTERABLE_COLUMNS if c in df_columns]
        
        # Lists of columns to analyze
        categorical = ["codice_comune", "tipologia_bene_immobile", "epoca_costruzione", "classe_energetica_ape"]
        numerical = [
            "superficie_di_riferimento_mq", "energy_score_total", 
            "healthcare", "mobility", "green", "sport", "commercial", "education"
        ]
        
        # Reset fields
        DB_METADATA["fields"] = {}
        
        for col in categorical + numerical:
            if col in df.columns:
                meta = {}
                if col in categorical:
                    # Extract unique values and sort
                    unique_vals = sorted([str(v) for v in df[col].dropna().unique()])
                    meta["values"] = unique_vals
                    meta["is_truncated"] = False
                else:
                    # Calculate numerical statistics
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
