import numpy as np
import pandas as pd


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
    poi_weights: dict,
    user_location: tuple = None,
    search_radius_km: float = 5.0,
    ape_weight: float = 0.2,
    poi_weight_factor: float = 0.5,
    distance_weight: float = 0.3,
) -> pd.DataFrame:
    """
    Calcola uno score di ranking per ogni immobile basato su POI, APE e Distanza.

    Args:
        df: DataFrame con i dati immobiliari.
        poi_weights: Dizionario con pesi per categoria POI (0-1).
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

    # 1. Calcolo Score POI (Media pesata delle categorie)
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
    poi_score_norm = poi_score_norm.clip(0, 1)

    # 2. Calcolo Score APE
    if "ape_score_total" in df.columns:
        ape_values = pd.to_numeric(df["ape_score_total"], errors="coerce").fillna(1)
        ape_score_norm = (ape_values - 1) / 4
        ape_score_norm = ape_score_norm.clip(0, 1)
    else:
        ape_score_norm = 0.0

    # 3. Calcolo Score Distanza (se user_location c'è)
    dist_score_norm = 0.0
    w_dist = 0.0

    if user_location:
        user_lat, user_lon = user_location

        # Assicuriamoci che le colonne lat/lon esistano
        if "latitudine" in df.columns and "longitudine" in df.columns:
            lats = pd.to_numeric(df["latitudine"], errors="coerce")
            lons = pd.to_numeric(df["longitudine"], errors="coerce")

            # Calcola distanze
            dists = haversine_vectorized(lats, lons, user_lat, user_lon)

            # Salva la distanza nel DF per debug/visualizzazione
            df["distanza_km"] = dists

            # Normalizzazione Distanza:
            # Adaptive max_dist based on search radius:
            # - Small search (3km) → strict scoring (max_dist = 3km)
            # - Large search (15km) → lenient scoring (max_dist = 9km)
            max_dist = min(search_radius_km * 0.6, 10.0)
            dist_score_norm = (1 - (dists / max_dist)).clip(0, 1)

            # Pesi con distanza
            tot_w = ape_weight + poi_weight_factor + distance_weight
            if tot_w > 0:
                w_ape = ape_weight / tot_w
                w_poi = poi_weight_factor / tot_w
                w_dist = distance_weight / tot_w
            else:
                w_ape, w_poi, w_dist = 0.33, 0.33, 0.33
        else:
            # Fallback se mancano coordinate nel DF
            tot_w = ape_weight + poi_weight_factor
            if tot_w > 0:
                w_ape = ape_weight / tot_w
                w_poi = poi_weight_factor / tot_w
            else:
                w_ape, w_poi = 0.5, 0.5
    else:
        # Senza distanza
        tot_w = ape_weight + poi_weight_factor
        if tot_w > 0:
            w_ape = ape_weight / tot_w
            w_poi = poi_weight_factor / tot_w
        else:
            w_ape, w_poi = 0.5, 0.5

    # 4. Score Totale
    final_score = (
        (poi_score_norm * w_poi) + (ape_score_norm * w_ape) + (dist_score_norm * w_dist)
    )

    df["ranking_score"] = final_score

    # Ordina decrescente per score, poi crescente per distanza (se disponibile)
    if "distanza_km" in df.columns:
        return df.sort_values(["ranking_score", "distanza_km"], ascending=[False, True])
    else:
        return df.sort_values("ranking_score", ascending=False)
