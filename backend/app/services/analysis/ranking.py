import numpy as np
import pandas as pd
import os
from typing import Dict


# Path al file degli amenity scores
AMENITY_SCORES_PATH = os.path.join(
    os.path.dirname(__file__),
    '../../../notebooks/04_scoring/immobili_amenity_scores_aggregated.parquet'
)

# Cache globale per il DataFrame degli amenity scores
_amenity_scores_cache = None


def load_amenity_scores() -> pd.DataFrame:
    """
    Carica gli amenity scores dal Parquet e li tiene in cache.
    
    Returns:
        DataFrame con colonne: immobile_id, amenity, score, percentile
    """
    global _amenity_scores_cache
    
    if _amenity_scores_cache is None:
        if os.path.exists(AMENITY_SCORES_PATH):
            _amenity_scores_cache = pd.read_parquet(AMENITY_SCORES_PATH)
        else:
            # Fallback: dataset vuoto se il file non esiste
            _amenity_scores_cache = pd.DataFrame(columns=['immobile_id', 'amenity', 'score', 'percentile'])
    
    return _amenity_scores_cache


def haversine_vectorized(lat1_series, lon1_series, lat2_scalar, lon2_scalar):
    """
    Calcola la distanza Haversine in km in modo vettoriale (Pandas Series / Numpy arrays).
    """
    R = 6371  # Raggio Terra in km

    # Converti in radianti
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
    typology_weight: float = 0.0,
) -> pd.DataFrame:
    """
    Calcola uno score di ranking per ogni immobile basato su POI, APE e Distanza.
    
    Utilizza gli amenity scores granulari dal file CSV pre-calcolato per una 
    valutazione più precisa basata sulle amenity specifiche selezionate.

    Args:
        df: DataFrame con i dati immobiliari.
        poi_weights: Dizionario con pesi per categoria POI (0-1). Usato come fallback.
        amenity_weights: Dizionario {categoria: {amenity: peso}} per amenity specifiche.
        user_location: Tuple (lat, lon) opzionale per calcolo distanza.
        search_radius_km: Raggio di ricerca in km (default 5.0).
        ape_weight: Peso dello score APE nel totale (0-1).
        poi_weight_factor: Peso complessivo dei POI nel totale (0-1).
        distance_weight: Peso della distanza nel totale (0-1).

    Returns:
        DataFrame con colonna aggiuntiva 'ranking_score' ordinato.
    """
    if df is None or df.empty:
        return df

    # Copia per non modificare l'originale in place se non voluto
    df = df.copy()

    # 1. Calcolo Score POI
    if "poi_score" in df.columns:
        poi_score_norm = pd.to_numeric(df["poi_score"], errors="coerce").fillna(0) / 100
    else:
        # Fallback legacy
        poi_score_norm = _calculate_poi_score_granular(df, amenity_weights, poi_weights)

    # 2. Calcolo Score APE
    if "energy_score" in df.columns:
        ape_score_norm = pd.to_numeric(df["energy_score"], errors="coerce").fillna(0) / 100
    elif "ape_score_total" in df.columns:
        ape_values = pd.to_numeric(df["ape_score_total"], errors="coerce").fillna(1)
        ape_score_norm = (ape_values - 1) / 4
        ape_score_norm = ape_score_norm.clip(0, 1)
    else:
        ape_score_norm = 0.0

    # 3. Calcolo Score Distanza (se user_location o location_score c'è)
    dist_score_norm = 0.0
    w_dist = 0.0

    if "location_score" in df.columns:
        dist_score_norm = pd.to_numeric(df["location_score"], errors="coerce").fillna(0) / 100
        w_dist = distance_weight
    elif user_location:
        user_lat, user_lon = user_location
        # Assicuriamoci che le colonne lat/lon esistano
        if "latitudine" in df.columns and "longitudine" in df.columns:
            lats = pd.to_numeric(df["latitudine"], errors="coerce")
            lons = pd.to_numeric(df["longitudine"], errors="coerce")
            dists = haversine_vectorized(lats, lons, user_lat, user_lon)
            df["distanza_km"] = dists
            max_dist = min(search_radius_km * 0.6, 10.0)
            dist_score_norm = (1 - (dists / max_dist)).clip(0, 1)
            w_dist = distance_weight
    
    # 4. Score Normativo (se presente)
    normative_score_norm = 0.0
    if "normative_score" in df.columns:
        normative_score_norm = pd.to_numeric(df["normative_score"], errors="coerce").fillna(0) / 100
    
    # 5. Score Tipologia (se presente)
    typology_score_norm = 0.0
    if "typology_score" in df.columns:
        typology_score_norm = pd.to_numeric(df["typology_score"], errors="coerce").fillna(0) / 100

    # 6. Normalizzazione pesi
    # Sommiamo i pesi solo se le relative colonne di score sono state popolate
    active_normative_weight = normative_weight if "normative_score" in df.columns else 0
    active_typology_weight = typology_weight if "typology_score" in df.columns else 0
    
    tot_w = ape_weight + poi_weight_factor + w_dist + active_normative_weight + active_typology_weight
    
    if tot_w > 0:
        w_ape = ape_weight / tot_w
        w_poi = poi_weight_factor / tot_w
        w_dist_final = w_dist / tot_w
        w_normative = active_normative_weight / tot_w
        w_typology = active_typology_weight / tot_w
    else:
        w_ape, w_poi, w_dist_final, w_normative, w_typology = 0.2, 0.2, 0.2, 0.2, 0.2

    # 7. Score Totale
    final_score = (
        (poi_score_norm * w_poi) + 
        (ape_score_norm * w_ape) + 
        (dist_score_norm * w_dist_final) +
        (normative_score_norm * w_normative) +
        (typology_score_norm * w_typology)
    )

    df["ranking_score"] = final_score

    # Ordina decrescente per score, poi crescente per distanza (se disponibile)
    if "distanza_km" in df.columns:
        return df.sort_values(["ranking_score", "distanza_km"], ascending=[False, True])
    else:
        return df.sort_values("ranking_score", ascending=False)


def _calculate_poi_score_granular(
    df: pd.DataFrame,
    amenity_weights: Dict[str, Dict[str, float]] = None,
    poi_weights: dict = None
) -> pd.Series:
    """
    Calcola lo score POI granulare usando gli amenity scores dal CSV.
    
    Args:
        df: DataFrame degli immobili
        amenity_weights: Dizionario {categoria: {amenity: peso}}
        poi_weights: Fallback con pesi per categoria
    
    Returns:
        Series con score POI normalizzati (0-1) per ogni immobile
    """
    # Se non ci sono amenity_weights, usa il metodo legacy con le colonne aggregate
    if not amenity_weights or all(not v for v in amenity_weights.values()):
        return _calculate_poi_score_legacy(df, poi_weights or {})
    
    # Carica gli amenity scores
    amenity_scores_df = load_amenity_scores()
    
    if amenity_scores_df.empty:
        # Fallback al metodo legacy se il CSV non è disponibile
        return _calculate_poi_score_legacy(df, poi_weights or {})
    
    # Filtra solo gli immobili presenti nel DataFrame di input
    # Assicurati che i tipi siano coerenti per il confronto (converti a stringa se necessario)
    immobile_ids = df['id'].astype(str).values
    relevant_scores = amenity_scores_df[amenity_scores_df['immobile_id'].astype(str).isin(immobile_ids)]
    
    if relevant_scores.empty:
        # Nessuno score trovato, usa metodo legacy
        return _calculate_poi_score_legacy(df, poi_weights or {})
    
    # Crea un dizionario per accumulare gli score per immobile
    immobile_poi_scores = {}
    
    # Somma totale dei pesi per normalizzazione
    total_weight = 0.0
    
    # Itera sulle categorie e amenity con peso > 0
    for category, amenities_dict in amenity_weights.items():
        for amenity, weight in amenities_dict.items():
            if weight > 0:
                total_weight += weight
                
                # Filtra gli score per questa amenity
                amenity_data = relevant_scores[relevant_scores['amenity'] == amenity]
                
                # Accumula gli score pesati per ogni immobile
                for _, row in amenity_data.iterrows():
                    immobile_id = str(row['immobile_id'])  # Converti a stringa per coerenza
                    score = row['score']  # Score raw (non percentile)
                    
                    if immobile_id not in immobile_poi_scores:
                        immobile_poi_scores[immobile_id] = 0.0
                    
                    # Aggiungi lo score pesato
                    immobile_poi_scores[immobile_id] += score * weight
    
    # Normalizza dividendo per il peso totale
    if total_weight > 0:
        for immobile_id in immobile_poi_scores:
            immobile_poi_scores[immobile_id] /= total_weight
    
    # Crea una Series allineata con il DataFrame di input
    # Converti df['id'] a stringa per matchare con le chiavi del dizionario
    poi_scores = df['id'].astype(str).map(immobile_poi_scores).fillna(0.0)
    
    # Normalizza gli score a 0-1
    # Gli score raw possono variare, quindi usiamo una normalizzazione min-max
    if poi_scores.max() > 0:
        poi_score_norm = (poi_scores - poi_scores.min()) / (poi_scores.max() - poi_scores.min())
    else:
        poi_score_norm = pd.Series(0.0, index=df.index)
    
    return poi_score_norm.clip(0, 1)


def _calculate_poi_score_legacy(df: pd.DataFrame, poi_weights: dict) -> pd.Series:
    """
    Calcola lo score POI usando il metodo legacy con le colonne aggregate.
    
    Args:
        df: DataFrame degli immobili
        poi_weights: Dizionario con pesi per categoria POI (0-1)
    
    Returns:
        Series con score POI normalizzati (0-1) per ogni immobile
    """
    poi_cols = ["sanita", "mobilita", "verde", "sport", "commerciale", "educazione"]
    
    # Normalizza pesi POI (somma = 1)
    total_poi_weight = sum(poi_weights.values())
    if total_poi_weight == 0:
        # Se tutti i pesi sono 0, diamo peso uguale (o 0)
        norm_poi_weights = {k: 1 / 6 for k in poi_cols}
    else:
        norm_poi_weights = {k: v / total_poi_weight for k, v in poi_weights.items()}
    
    # Calcola weighted sum dei POI (scala 1-5)
    poi_score_series = pd.Series(0.0, index=df.index)
    
    for col in poi_cols:
        if col in df.columns:
            # Converte in numerico, gestisce NaN mettendo 1 (punteggio minimo)
            col_values = pd.to_numeric(df[col], errors="coerce").fillna(1)
            poi_score_series += col_values * norm_poi_weights.get(col, 0)
    
    # Normalizza POI score a 0-1 (da 1-5) -> (val - 1) / 4
    poi_score_norm = (poi_score_series - 1) / 4
    
    return poi_score_norm.clip(0, 1)
