"""
Data loading functions for datasets, GeoJSON, and static files.

This module handles:
- Loading and merging CSV datasets
- Fetching coordinates from Nominatim API
- Loading GeoJSON data for map overlays
- Loading static data (metro stations)
- Reading APE XML files safely
"""

from functools import lru_cache
import json
import os
import re
import threading

import pandas as pd
import requests

from app.utils.decorators import retry_with_backoff
from app.utils.logger import logger

# Global cache and lock
GEOCODE_CACHE_FILE = os.path.join("app", "data", "geocode_cache.json")
GEOCODE_CACHE = {}
CACHE_LOCK = threading.Lock()

# Load cache on module load
if os.path.exists(GEOCODE_CACHE_FILE):
    try:
        with open(GEOCODE_CACHE_FILE, "r", encoding="utf-8") as f:
            GEOCODE_CACHE = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load geocode cache: {e}")


def load_and_merge_data(file_path):
    """
    Load CSV or Parquet data with error handling.
    Optimized for performance.

    Args:
        file_path: Path to CSV or Parquet file

    Returns:
        pd.DataFrame: Loaded data, or None if error
    """
    try:
        if file_path.endswith(".parquet"):
            logger.info(f"Loading Parquet file: {file_path}")
            pd_data = pd.read_parquet(file_path)
            # Ensure 'id' is string if it exists
            if "id" in pd_data.columns:
                pd_data["id"] = pd_data["id"].astype(str)
        else:
            logger.info(f"Loading CSV file: {file_path}")
            # Use engine='c' for speed, low_memory=False to avoid mixed type warnings
            # Ensure 'id' is read as string to prevent issues with leading zeros or large numbers
            pd_data = pd.read_csv(
                file_path,
                sep=";",
                encoding="utf-8",
                engine="c",
                low_memory=False,
                dtype={"id": str},
            )
    except pd.errors.ParserError as e:
        logger.error(f"CSV Parsing Error: {e}")
        try:
            pd_data = pd.read_csv(
                file_path,
                sep=";",
                encoding="utf-8",
                quoting=1,
                on_bad_lines="warn",
                dtype={"id": str},
            )
        except Exception as e2:
            logger.critical(f"CRITICAL CSV Load Error: {e2}")
            return None
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Generic load error: {e}")
        return None

    # Merge with APE scores if available
    try:
        from app.core.config import settings

        APE_DETAILED_DATA_PATH = settings.APE_DETAILED_DATA_PATH

        ape_df = load_ape_detailed_data(APE_DETAILED_DATA_PATH)
        if ape_df is not None and "id" in ape_df.columns:
            # Ensure ID is string for merging
            ape_df["id"] = ape_df["id"].astype(str)

            # Select only score columns to merge
            score_cols = [
                "id",
                "ape_score",
                "ape_total_points",
                "ape_class_score",
                "ape_system_score",
                "ape_envelope_score",
                "ape_renewables_score",
            ]

            # Check if columns exist (they should if calculate_ape_score ran)
            cols_to_merge = [c for c in score_cols if c in ape_df.columns]

            if len(cols_to_merge) > 1:
                pd_data = pd.merge(pd_data, ape_df[cols_to_merge], on="id", how="left")

                # Fill NaNs for scores with 0 or 1 (default low score)
                for col in cols_to_merge:
                    if col != "id":
                        pd_data[col] = pd_data[col].fillna(0)
    except Exception as e:
        logger.warning(f"Error merging APE scores: {e}")

    return pd_data


@lru_cache(maxsize=128)
@retry_with_backoff(
    retries=3, initial_delay=1.0, exceptions=(requests.RequestException,)
)
def get_coordinates(place_name):
    """
    Fetch coordinates for a place using Nominatim API (cached).

    Args:
        place_name: Name of the place to geocode

    Returns:
        tuple: (latitude, longitude) or (None, None) if not found
    """
    # Check global cache first
    if place_name in GEOCODE_CACHE:
        return GEOCODE_CACHE[place_name]

    # Add context to query if missing
    search_query = place_name
    if "torino" not in search_query.lower() and "piemonte" not in search_query.lower():
        search_query += ", Torino, Piemonte, Italia"
    elif "italia" not in search_query.lower():
        search_query += ", Italia"

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": search_query,
        "format": "json",
        "limit": 1,
        "viewbox": "7.5,45.2,7.8,44.9",  # Bounding box for Turin area approx
        "bounded": 1,
    }
    headers = {"User-Agent": "DashApp/1.0"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])

            # Update global cache and file safely
            with CACHE_LOCK:
                GEOCODE_CACHE[place_name] = (lat, lon)
                try:
                    with open(GEOCODE_CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(GEOCODE_CACHE, f, indent=2)
                except Exception as e:
                    logger.warning(f"Failed to write geocode cache: {e}")

            return lat, lon
    except Exception as e:
        logger.warning(f"Nominatim Error for '{place_name}': {e}")
    return None, None


def load_geojson_data(path):
    """
    Carica dati GeoJSON da un file, gestendo eventuali errori.

    Args:
        path: Path to GeoJSON file

    Returns:
        dict: GeoJSON data, or None if error
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"GeoJSON file not found: {path}. Overlay unavailable.")
        return None
    except json.JSONDecodeError:
        logger.error(f"JSON Decode Error for file: {path}.")
        return None


def load_static_data():
    """
    Carica i dati che non dipendono dalla query (es. stazioni metro).

    Returns:
        pd.DataFrame: Station data
    """
    from app.core.config import settings

    try:
        stazioni_df = pd.read_csv(settings.STATIONS_CSV)
        return stazioni_df
    except FileNotFoundError:
        logger.warning("Station file not found.")
        return pd.DataFrame(columns=["Lat", "Lon", "Linea", "Nome"])


def read_xml_text_safe(full_path: str) -> str:
    """
    Read XML file with proper encoding detection and BOM handling.

    Args:
        full_path: Path to XML file

    Returns:
        str: XML content as string
    """
    with open(full_path, "rb") as f:
        raw = f.read()

    if not raw:
        return ""

    # Handle BOM (Byte Order Mark)
    if raw.startswith(b"\xef\xbb\xbf"):
        text = raw[3:].decode("utf-8", errors="ignore")
    elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw[2:].decode("utf-16", errors="ignore")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="ignore")

    # Clean any garbage before XML declaration
    text = re.sub(r"^.*?<\?xml", "<?xml", text, flags=re.DOTALL)
    return text


def load_ape_detailed_data(file_path):
    """
    Load detailed APE data from CSV or Parquet and calculate scores.

    Args:
        file_path: Path to CSV or Parquet file

    Returns:
        pd.DataFrame: Loaded data with scores, or None if error
    """
    if not os.path.exists(file_path):
        logger.warning(f"APE detailed file not found: {file_path}")
        return None

    try:
        if file_path.endswith(".parquet"):
            pd_data = pd.read_parquet(file_path)
        else:
            # Try comma first as suggested by the header format
            pd_data = pd.read_csv(
                file_path, sep=",", encoding="utf-8", engine="c", low_memory=False
            )

            # If only one column, it might be semicolon separated
            if len(pd_data.columns) <= 1:
                pd_data = pd.read_csv(
                    file_path, sep=";", encoding="utf-8", engine="c", low_memory=False
                )

        # Calculate scores
        from app.data.processors import calculate_ape_score

        pd_data = calculate_ape_score(pd_data)

        return pd_data
    except Exception as e:
        logger.error(f"Error loading APE detailed data: {e}")
        return None
