from typing import Dict, List

# Score legend for energy and proximity
SCORE_LEGEND = """SCORE LEGEND:

Energy (energy efficiency):
- energy_score_class: Energy class (5=A1-A4, 3=B-E, 1=F-G)
- energy_score_plant: Thermal plant quality (5=Heat pump/District heating, 3=Condensation/Biomass, 1=Traditional)
- energy_score_envelope: Building insulation (5=Excellent, 3=Medium, 1=Poor/None)
- energy_score_renewables: Renewable energy sources present (5=Yes, 1=No)
- energy_score_total: Sum of the four energy sub-scores (4-20)

Proximity (proximity services):
- healthcare: Proximity to healthcare services (0-100 percentile)
- mobility: Public transport accessibility (0-100 percentile)
- green: Presence of green areas (0-100 percentile)
- sport: Proximity to sports facilities (0-100 percentile)
- commercial: Commercial services (0-100 percentile)
- education: Schools and education (0-100 percentile)
"""

# Specific legend for Energy agent
ENERGY_SCORE_LEGEND = """ENERGY SCORE LEGEND:

- energy_score_class: Energy class (5=A1-A4, 3=B-E, 1=F-G)
- energy_score_plant: Thermal plant quality (5=Heat pump/District heating, 3=Condensation/Biomass, 1=Traditional)
- energy_score_envelope: Building insulation (5=Excellent, 3=Medium, 1=Poor/None)
- energy_score_renewables: Renewable energy sources present (5=Yes, 1=No)
- energy_score_total: Sum of the four sub-scores (4-20)
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
    "cadastral_sheet",
    "cadastral_parcel",
    "cadastral_subaltern",
    "cadastral_units_count",
    "surface_area",
]

# Columns for Regulatory agent
REGULATORY_AGENT_COLUMNS: List[str] = [
    "surface_area",
    "property_type",
    "legal_nature",
    "cultural_constraint",
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

# Column mapping from database to English nomenclature
COLUMN_MAPPING: Dict[str, str] = {
    # Proximity pillars
    "healthcare": "healthcare",
    "mobility": "mobility",
    "green": "green",
    "sport": "sport",
    "commercial": "commercial",
    "education": "education",
    # Energy scores
    "energy_score_class": "energy_score_class",
    "energy_score_plant": "energy_score_plant",
    "energy_score_envelope": "energy_score_envelope",
    "energy_score_renewables": "energy_score_renewables",
    "energy_score_total": "energy_score_total",
    "energy_score": "energy_score",
    # General attributes
    "address": "address",
    "house_number": "house_number",
    "omi_zone": "omi_zone",
    "surface_area": "surface_area",
    "property_type": "property_type",
    "construction_period": "construction_period",
    "purpose": "purpose",
    "energy_class": "energy_class",
    "latitude": "latitude",
    "longitude": "longitude",
    "legal_nature": "legal_nature",
    "cultural_constraint": "cultural_constraint",
    "ape_file_list": "ape_file_list",
    "cadastral_units_count": "cadastral_units_count",
    "distance_km": "distance_km",
    "description": "description",
    "third_party_tenure_type": "third_party_tenure_type",
    "effective_date": "effective_date",
    "annual_rent": "annual_rent",
    "cadastral_sheet": "cadastral_sheet",
    "cadastral_parcel": "cadastral_parcel",
    "cadastral_subaltern": "cadastral_subaltern",
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
        categorical = ["codice_comune", "property_type", "construction_period", "energy_class"]
        numerical = [
            "surface_area", "energy_score_total", 
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
