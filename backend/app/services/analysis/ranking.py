import numpy as np
import pandas as pd
import os
from typing import Dict


# Path to the amenity scores file
AMENITY_SCORES_PATH = os.path.join(
    os.path.dirname(__file__),
    '../../../notebooks/04_scoring/immobili_amenity_scores_aggregated.parquet'
)

# Global cache for the amenity scores DataFrame
_amenity_scores_cache = None


def load_amenity_scores() -> pd.DataFrame:
    """
    Loads amenity scores from Parquet and keeps them in cache.
    
    Returns:
        DataFrame with columns: immobile_id, amenity, score, percentile
    """
    global _amenity_scores_cache
    
    if _amenity_scores_cache is None:
        if os.path.exists(AMENITY_SCORES_PATH):
            _amenity_scores_cache = pd.read_parquet(AMENITY_SCORES_PATH)
        else:
            # Fallback: empty dataset if the file does not exist
            _amenity_scores_cache = pd.DataFrame(columns=['immobile_id', 'amenity', 'score', 'percentile'])
    
    return _amenity_scores_cache


def haversine_vectorized(lat1_series, lon1_series, lat2_scalar, lon2_scalar):
    """
    Calculates Haversine distance in km in a vectorized way (Pandas Series / Numpy arrays).
    """
    R = 6371  # Earth radius in km

    # Convert to radians
    lat1 = np.radians(lat1_series)
    lon1 = np.radians(lon1_series)
    lat2 = np.radians(lat2_scalar)
    lon2 = np.radians(lon2_scalar)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c


def calculate_ranking_score(
    df: pd.DataFrame,
    poi_weights: dict = None,
    amenity_weights: Dict[str, Dict[str, float]] = None,
    user_location: tuple = None,
    search_radius_km: float = 5.0,
    ape_weight: float = 0.2,
    poi_weight_factor: float = 0.5,
    distance_weight: float = 0.3,
    normative_weight: float = 0.0,
    property_technical_weight: float = 0.0,
) -> pd.DataFrame:
    """
    Calculates a ranking score for each property based on POI, APE, and Distance.
    
    Uses granular amenity scores from the pre-calculated CSV for a 
    more precise evaluation based on specific selected amenities.

    Args:
        df: DataFrame with real estate data.
        poi_weights: Dictionary with weights for POI category (0-1). Used as fallback.
        amenity_weights: Dictionary {category: {amenity: weight}} for specific amenities.
        user_location: Optional (lat, lon) tuple for distance calculation.
        search_radius_km: Search radius in km (default 5.0).
        ape_weight: Weight of the APE score in total (0-1).
        poi_weight_factor: Total weight of POIs in total (0-1).
        distance_weight: Weight of distance in total (0-1).

    Returns:
        DataFrame with an additional 'ranking_score' column, sorted.
    """
    if df is None or df.empty:
        return df

    # Copy to avoid modifying the original in-place if not desired
    df = df.copy()

    # 1. POI Score Calculation
    if "poi_score" in df.columns:
        poi_score_norm = pd.to_numeric(df["poi_score"], errors="coerce").fillna(0) / 100
    else:
        # Fallback legacy
        poi_score_norm = _calculate_poi_score_granular(df, amenity_weights, poi_weights)

    # 2. APE Score Calculation
    if "ape_score" in df.columns:
        ape_score_norm = pd.to_numeric(df["ape_score"], errors="coerce").fillna(0) / 100
    elif "ape_score_total" in df.columns or "energy_score_total" in df.columns:
        score_col = "ape_score_total" if "ape_score_total" in df.columns else "energy_score_total"
        ape_values = pd.to_numeric(df[score_col], errors="coerce")
        max_observed = float(ape_values.max()) if not ape_values.dropna().empty else 5.0
        if max_observed > 5:
            # Historical Turin data stores the sum of four 1-5 sub-scores (4-20).
            ape_score_norm = (ape_values.fillna(4) - 4) / 16
        else:
            # Newer/demo data may store an already averaged 1-5 score.
            ape_score_norm = (ape_values.fillna(1) - 1) / 4
        ape_score_norm = ape_score_norm.clip(0, 1)
    else:
        ape_score_norm = 0.0

    # 3. Distance Score Calculation (if user_location or location_score exists)
    dist_score_norm = 0.0
    w_dist = 0.0

    if "location_score" in df.columns:
        dist_score_norm = pd.to_numeric(df["location_score"], errors="coerce").fillna(0) / 100
        w_dist = distance_weight
    elif user_location:
        user_lat, user_lon = user_location
        lat_col = "latitude" if "latitude" in df.columns else ("latitudine" if "latitudine" in df.columns else None)
        lon_col = "longitude" if "longitude" in df.columns else ("longitudine" if "longitudine" in df.columns else None)
        if lat_col and lon_col:
            lats = pd.to_numeric(df[lat_col], errors="coerce")
            lons = pd.to_numeric(df[lon_col], errors="coerce")
            dists = haversine_vectorized(lats, lons, user_lat, user_lon)
            df["distanza_km"] = dists
            max_dist = min(search_radius_km * 0.6, 10.0)
            dist_score_norm = (1 - (dists / max_dist)).clip(0, 1)
            w_dist = distance_weight
    
    # 4. Regulatory Score (if present)
    normative_score_norm = 0.0
    if "normative_score" in df.columns:
        normative_score_norm = pd.to_numeric(df["normative_score"], errors="coerce").fillna(0) / 100
    
    # 5. Property Technical Score (if present)
    property_technical_score_norm = 0.0
    if "property_technical_score" in df.columns:
        property_technical_score_norm = pd.to_numeric(df["property_technical_score"], errors="coerce").fillna(0) / 100

    # 6. Weight Normalization
    # Sum weights only if the relative score columns are populated
    active_normative_weight = normative_weight if "normative_score" in df.columns else 0
    active_property_technical_weight = property_technical_weight if "property_technical_score" in df.columns else 0
    active_ape_weight = (
        ape_weight
        if any(col in df.columns for col in ["ape_score", "ape_score_total", "energy_score_total"])
        else 0
    )
    
    tot_w = active_ape_weight + poi_weight_factor + w_dist + active_normative_weight + active_property_technical_weight
    
    if tot_w > 0:
        w_ape = active_ape_weight / tot_w
        w_poi = poi_weight_factor / tot_w
        w_dist_final = w_dist / tot_w
        w_normative = active_normative_weight / tot_w
        w_property_technical = active_property_technical_weight / tot_w
    else:
        w_ape, w_poi, w_dist_final, w_normative, w_property_technical = 0.2, 0.2, 0.2, 0.2, 0.2

    # 7. Total Score
    final_score = (
        (poi_score_norm * w_poi) + 
        (ape_score_norm * w_ape) + 
        (dist_score_norm * w_dist_final) +
        (normative_score_norm * w_normative) +
        (property_technical_score_norm * w_property_technical)
    )

    df["final_ranking_score"] = final_score * 100

    # Sort descending by score, then ascending by distance (if available)
    if "distanza_km" in df.columns:
        return df.sort_values(["final_ranking_score", "distanza_km"], ascending=[False, True])
    else:
        return df.sort_values("final_ranking_score", ascending=False)


def _calculate_poi_score_granular(
    df: pd.DataFrame,
    amenity_weights: Dict[str, Dict[str, float]] = None,
    poi_weights: dict = None
) -> pd.Series:
    """
    Calculates granular POI score using amenity scores from the CSV.
    
    Args:
        df: Properties DataFrame
        amenity_weights: Dictionary {category: {amenity: weight}}
        poi_weights: Fallback with per-category weights
    
    Returns:
        Series with normalized POI scores (0-1) for each property
    """
    # If no amenity_weights, use legacy method with aggregated columns
    if not amenity_weights or all(not v for v in amenity_weights.values()):
        return _calculate_poi_score_legacy(df, poi_weights or {})
    
    # Load amenity scores
    amenity_scores_df = load_amenity_scores()
    
    if amenity_scores_df.empty:
        # Fallback to legacy method if CSV is not available
        return _calculate_poi_score_legacy(df, poi_weights or {})
    
    # Filter only properties present in the input DataFrame
    # Ensure types are consistent for comparison (convert to string if necessary)
    immobile_ids = df['id'].astype(str).values
    relevant_scores = amenity_scores_df[amenity_scores_df['immobile_id'].astype(str).isin(immobile_ids)]
    
    if relevant_scores.empty:
        # No scores found, use legacy method
        return _calculate_poi_score_legacy(df, poi_weights or {})
    
    # Create a dictionary to accumulate scores per property
    immobile_poi_scores = {}
    
    # Total sum of weights for normalization
    total_weight = 0.0
    
    # Iterate over categories and amenities with weight > 0
    for category, amenities_dict in amenity_weights.items():
        for amenity, weight in amenities_dict.items():
            if weight > 0:
                total_weight += weight
                
                # Filtra gli score per questa amenity
                amenity_data = relevant_scores[relevant_scores['amenity'] == amenity]
                
                # Accumulate weighted scores for each property
                for _, row in amenity_data.iterrows():
                    immobile_id = str(row['immobile_id'])  # Convert to string for consistency
                    score = row['score']  # Raw score (not percentile)
                    
                    if immobile_id not in immobile_poi_scores:
                        immobile_poi_scores[immobile_id] = 0.0
                    
                    # Add weighted score
                    immobile_poi_scores[immobile_id] += score * weight
    
    # Normalize by dividing by total weight
    if total_weight > 0:
        for immobile_id in immobile_poi_scores:
            immobile_poi_scores[immobile_id] /= total_weight
    
    # Create a Series aligned with input DataFrame
    # Convert df['id'] to string to match dictionary keys
    poi_scores = df['id'].astype(str).map(immobile_poi_scores).fillna(0.0)
    
    # Normalize scores to 0-1
    # Raw scores can vary, so we use min-max normalization
    if poi_scores.max() > 0:
        poi_score_norm = (poi_scores - poi_scores.min()) / (poi_scores.max() - poi_scores.min())
    else:
        poi_score_norm = pd.Series(0.0, index=df.index)
    
    return poi_score_norm.clip(0, 1)


def _calculate_poi_score_legacy(df: pd.DataFrame, poi_weights: dict) -> pd.Series:
    """
    Calculates POI score using legacy method with aggregated columns.
    
    Args:
        df: Properties DataFrame
        poi_weights: Dictionary with weights for POI category (0-1)
    
    Returns:
        Series with normalized POI scores (0-1) for each property
    """
    poi_aliases = {
        "healthcare": ["healthcare", "sanita", "sanità"],
        "mobility": ["mobility", "mobilita", "mobilità"],
        "green": ["green", "greenery", "verde"],
        "sport": ["sport"],
        "commercial": ["commercial", "commerce", "commerciale"],
        "education": ["education", "educazione"],
    }
    available_cols = {
        category: next((col for col in aliases if col in df.columns), None)
        for category, aliases in poi_aliases.items()
    }
    available_cols = {category: col for category, col in available_cols.items() if col}

    if not available_cols:
        return pd.Series(0.0, index=df.index)
    
    # Normalize POI weights (sum = 1)
    total_poi_weight = sum(poi_weights.values())
    if total_poi_weight == 0:
        # If all weights are 0, give equal weight (or 0)
        norm_poi_weights = {k: 1 / len(poi_aliases) for k in poi_aliases}
    else:
        # Map input weights (Italian) to normalized weights (English)
        mapping = {
            "sanita": "healthcare",
            "mobilita": "mobility",
            "verde": "green",
            "sport": "sport",
            "commerciale": "commercial",
            "educazione": "education"
        }
        norm_poi_weights = {mapping.get(k, k): v / total_poi_weight for k, v in poi_weights.items()}
    
    # Calculate weighted POI sum. Historical exports use 0-100 percentiles;
    # demo/newer datasets can use a 1-5 scale.
    poi_score_series = pd.Series(0.0, index=df.index)
    
    for category, source_col in available_cols.items():
        col_values = pd.to_numeric(df[source_col], errors="coerce")
        max_observed = float(col_values.max()) if not col_values.dropna().empty else 5.0
        if max_observed > 5:
            normalized_values = col_values.fillna(0) / 100
        else:
            normalized_values = (col_values.fillna(1) - 1) / 4
        poi_score_series += normalized_values.clip(0, 1) * norm_poi_weights.get(category, 0)
    
    return poi_score_series.clip(0, 1)
