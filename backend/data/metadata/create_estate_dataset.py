import os
import re
import glob
import pandas as pd
import numpy as np
from lxml import etree
from typing import Dict, List, Optional, Any
from tqdm.auto import tqdm
import warnings
import json
from functools import lru_cache
import duckdb
import re
try:
    from sklearn.neighbors import BallTree
except ImportError:
    BallTree = None

import sys
from pathlib import Path

# Add backend and script directory to path
_script_dir = Path(__file__).resolve().parent
_backend_path = _script_dir.parent.parent
if str(_backend_path) not in sys.path:
    sys.path.append(str(_backend_path))
if str(_script_dir) not in sys.path:
    sys.path.append(str(_script_dir))

# Import amenity configurations
try:
    from amenities_config import CATEGORIES, CATEGORY_AMENITIES
except ImportError:
    print("Warning: Could not import configs from amenities_config.py from " + str(_script_dir))
    CATEGORIES = []
    CATEGORY_AMENITIES = {}

from dotenv import load_dotenv
load_dotenv(_backend_path / ".env")
from app.utils.helpers import require_env

try:
    from shapely.geometry import Point
    import geopandas as gpd
except ImportError:
    Point = None
    gpd = None

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# --- CONFIGURATION ---
# Parser imports do not require enrichment-only target/geospatial configuration.
PATH_XML = os.getenv("APE_XML_PATH", "")
TARGET_CITY = os.getenv("TARGET_CITY", "")
TARGET_PROVINCE = os.getenv("TARGET_PROVINCE", "")
TARGET_COMUNE_CODE = os.getenv("TARGET_COMUNE_CODE", "")

# --- CONSTANTS AND MAPPING ---

MAPPING_QUALITA_INVOLUCRO = {
    '0': 'Good',
    '1': 'Neutral',
    '2': 'Poor'
}

MAPPING_DPR412 = {
    '0': 'Residential (Continuous)',
    '1': 'Hospitals, retirement homes, prisons, barracks, convents',
    '2': 'Residential (Temporary/Holiday)',
    '3': 'Hotels, pensions, and similar',
    '4': 'Offices and similar',
    '5': 'Hospitals, clinics, nursing homes and similar',
    '6': 'Cinemas, theaters, congress halls and similar',
    '7': 'Exhibitions, museums, libraries, places of worship and similar',
    '8': 'Bars, restaurants, dance halls and similar',
    '9': 'Commercial activities and similar',
    '10': 'Swimming pools, saunas and similar',
    '11': 'Gyms and similar',
    '12': 'Sports support services',
    '13': 'Schools and educational activities',
    '14': 'Industrial and artisanal activities'
}

MAPPING_IMPIANTI = {
    '0': 'Standard boiler',
    '1': 'Condensing boiler',
    '2': 'Stove or fireplace',
    '3': 'Electric heating',
    '4': 'Heat pump', '5': 'Heat pump', '6': 'Heat pump', '7': 'Heat pump',
    '8': 'Heat pump', '9': 'Heat pump', '10': 'Heat pump', '11': 'Heat pump',
    '12': 'Heat pump', '13': 'Heat pump', '14': 'Heat pump', '15': 'Heat pump',
    '16': 'Solar thermal system',
    '17': 'Photovoltaic system',
    '18': 'Cogenerator',
    '19': 'District heating',
    '32': 'Gas water heater',
    '33': 'Gas water heater',
    '35': 'Heat pump water heater',
    '36': 'Electric boiler'
}

# --- LOCAL GEODATABASE (OSM) ---

class OSMGeocodingService:
    """
    Local geocoding service based on OSM PBF files.
    """
    def __init__(self, pbf_path: str):
        self.pbf_path = os.path.expanduser(pbf_path)
        if not os.path.exists(self.pbf_path):
            raise FileNotFoundError(f"OSM PBF file not found at: {self.pbf_path}")
        self.conn = duckdb.connect(database=':memory:')
        self._setup_database()

    def _setup_database(self) -> None:
        self.conn.execute("INSTALL spatial; LOAD spatial;")
        self.conn.execute(f"""
            CREATE TABLE addresses AS 
            SELECT 
                lower(tags['addr:street']) as street,
                lower(tags['addr:housenumber']) as house_number,
                lower(tags['addr:city']) as city,
                lon,
                lat
            FROM ST_ReadOSM('{self.pbf_path}')
            WHERE tags['addr:street'] IS NOT NULL
        """)
        self.conn.execute("CREATE INDEX idx_street ON addresses (street)")

    def _clean_address(self, street: str, number: Optional[str], city: Optional[str]) -> tuple:
        """
        Cleans the address aggressively to extract street name and house number.
        """
        raw = str(street).strip().upper()
        
        # 1. Remove junk prefixes (e.g. ": ", "10128 TORINO - ", "374 ")
        # Removes CAP at the beginning (5 digits)
        raw = re.sub(r'^\d{5}\s+', '', raw)
        # Removes "TORINO" or "TO" at beginning or end if present
        raw = re.sub(rf'^({TARGET_CITY}|{TARGET_PROVINCE})\s*-?\s*', '', raw, flags=re.IGNORECASE)
        raw = re.sub(rf'\s*-?\s*({TARGET_CITY}|{TARGET_PROVINCE})$', '', raw, flags=re.IGNORECASE)
        # Removes random numbers at beginning (often export junk)
        raw = re.sub(r'^\d+\s+', '', raw)
        # Removes punctuation at beginning
        raw = raw.lstrip(':-,. ')

        # 2. Normalization of common street types
        # Corso
        raw = re.sub(r'^(C\.?SO|C/S|C\s+SO|CORS|COROS)\b', 'CORSO', raw)
        # Via
        raw = re.sub(r'^(V\.?IA|V/A|V\s+IA)\b', 'VIA', raw)
        # Piazza
        raw = re.sub(r'^(P\.?ZZA|P/Z)\b', 'PIAZZA', raw)

        # 3. Extraction of house number if not provided or embedded
        final_num = str(number).strip().lower() if number and str(number).lower() != 'snc' else None
        
        # If the number is in the string (e.g. "CORSO TRAPANI, 133" or "VIA ROMA 10")
        match = re.search(r'(?:[ ,]|CIVICO|N\.?)\s*(\d+[A-Z\s/-]*)$', raw, re.IGNORECASE)
        if match:
            if not final_num:
                final_num = match.group(1).strip().lower()
            street_clean = raw[:match.start()].strip(', ')
        else:
            street_clean = raw

        # Removes any residual city from the street name
        if city:
            street_clean = re.sub(rf'\b{re.escape(city.upper())}\b', '', street_clean).strip(' ,-')

        return street_clean.lower(), final_num

    @lru_cache(maxsize=100_000)
    def geocode(self, street: str, number: Optional[str] = None, city: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Converts a dirty address into lat/lon coordinates.
        """
        if not street: return None
        
        street_clean, final_number = self._clean_address(street, number, city)
        city_clean = city.strip().lower() if city else TARGET_CITY.lower()

        if len(street_clean) < 3: # Too short to be a valid street
            return None

        # 2. Candidate query on DuckDB
        # We search both with LIKE (slower but flexible) and equality
        query = "SELECT lat, lon, street, house_number, city FROM addresses WHERE street LIKE ?"
        params = [f"%{street_clean}%"]
        
        if city_clean:
            query += " AND city LIKE ?"
            params.append(f"%{city_clean}%")
        
        query += " LIMIT 60"
        
        candidates = self.conn.execute(query, params).fetchall()
        if not candidates:
            # Retry without street type (e.g. from "CORSO TRAPANI" to "TRAPANI")
            parts = street_clean.split(' ', 1)
            if len(parts) > 1:
                query = "SELECT lat, lon, street, house_number, city FROM addresses WHERE street LIKE ?"
                params = [f"%{parts[1]}%"]
                if city_clean:
                    query += " AND city LIKE ?"
                    params.append(f"%{city_clean}%")
                query += " LIMIT 40"
                candidates = self.conn.execute(query, params).fetchall()

        if not candidates: return None
            
        results = []
        for c in candidates:
            res = {"lat": c[0], "lon": c[1], "street": c[2], "house_number": c[3], "city": c[4], "score": 0,
                   "street_exact": False, "house_number_exact": False}
            
            # SCORING
            # City (100)
            if city_clean == res['city']: res['score'] += 100
            
            # Street (Max 150)
            target_street = res['street'] or ""
            if street_clean == target_street:
                res['score'] += 150
                res['street_exact'] = True
            elif street_clean in target_street or target_street in street_clean: res['score'] += 50
            
            # House Number (Max 300)
            if final_number:
                target_num = (res['house_number'] or "").lower()
                input_num = final_number.lower().replace(' ', '')
                if input_num == target_num.replace(' ', ''):
                    res['score'] += 300
                    res['house_number_exact'] = True
                elif target_num and re.match(rf"^{re.escape(input_num)}(\D|$)", target_num):
                    res['score'] += 150
                elif target_num:
                    res['score'] -= 100 
            
            results.append(res)
            
        best = max(results, key=lambda x: x['score'])
        if not best['street_exact'] or (final_number and not best['house_number_exact']):
            return None
        best['confidence'] = 'high' if best['house_number_exact'] else 'medium'
        best['provenance'] = 'osm_address'
        return best

# --- SCORING FUNCTIONS ---

def map_impianto_score(impianto_desc):
    if not isinstance(impianto_desc, str):
        return 1
    desc = impianto_desc.lower()
    if "heat pump" in desc or "district heating" in desc:
        return 5
    if "condensing" in desc or "biomass" in desc:
        return 3
    return 1

def map_involucro_score(qualita):
    if not isinstance(qualita, str):
        return 1
    q = qualita.lower()
    if "good" in q:
        return 5
    if "neutral" in q:
        return 3
    if "poor" in q:
        return 1
    return 1

def map_rinnovabili_score(rinnovabile_val):
    if rinnovabile_val in [True, "Yes", "Sì", "Si", "true", 1]:
        return 5
    return 1

def map_classe_score(classe_val):
    if not isinstance(classe_val, str):
        return 1
    c = classe_val.upper().strip()
    if c.startswith("A"):
        return 5
    if c in ["B", "C", "D", "E"]:
        return 3
    return 1

VETTORI_XPATHS = {
    'Electricity from grid': '//ape:prestazioneImpianti/ape:energiaElettricaRete/ape:consumoAnnuo',
    'Natural gas': '//ape:prestazioneImpianti/ape:gasNaturale/ape:consumoAnnuo',
    'LPG': '//ape:prestazioneImpianti/ape:gpl/ape:consumoAnnuo',
    'Coal': '//ape:prestazioneImpianti/ape:carbone/ape:consumoAnnuo',
    'Diesel': '//ape:prestazioneImpianti/ape:gasolio/ape:consumoAnnuo',
    'Fuel oil': '//ape:prestazioneImpianti/ape:olioCombustibile/ape:consumoAnnuo',
    'Solid biomass': '//ape:prestazioneImpianti/ape:biomasseSolide/ape:consumoAnnuo',
    'Liquid biomass': '//ape:prestazioneImpianti/ape:biomasseLiquide/ape:consumoAnnuo',
    'Gaseous biomass': '//ape:prestazioneImpianti/ape:biomasseGassose/ape:consumoAnnuo',
    'Solar photovoltaic': '//ape:prestazioneImpianti/ape:solareFotovoltaico/ape:consumoAnnuo',
    'Solar thermal': '//ape:prestazioneImpianti/ape:solareTermico/ape:consumoAnnuo',
    'Wind': '//ape:prestazioneImpianti/ape:eolico/ape:consumoAnnuo',
    'District heating': '//ape:prestazioneImpianti/ape:teleriscaldamento/ape:consumoAnnuo',
    'District cooling': '//ape:prestazioneImpianti/ape:teleraffrescamento/ape:consumoAnnuo'
}

VETTORI_PCI = {
    'Natural gas': 9.94,
    'LPG': 12.778,
    'Coal': 7.917,
    'Diesel': 11.87,
    'Fuel oil': 11.75,
    'Solid biomass': 4.67,
    'Liquid biomass': 7.5,
    'Gaseous biomass': 6.4
}

# --- AMENITY CONFIGURATION ---
EARTH_RADIUS_KM = 6371.0
MAX_DISTANCE_M = 5000
SERVICE_BASE = {'breve': 0.340, 'medio': 0.680, 'lungo': 1.360}
URBAN_MULTIPLIER = {'B': 1.0, 'C': 1.5, 'D': 2.5, 'E': 4.0}
DEFAULT_ZONE = 'C'

# Mapping Amenity -> Threshold Class (Short/Medium/Long)
BREVE = ["pharmacy", "defibrillator", "bus_stop", "tram_stop", "bicycle_parking", "taxi", "subway_entrance", "charging_station", "playground", "garden", "grass", "park", "fitness_centre", "pitch", "supermarket", "bakery", "greengrocer", "newsagent", "kiosk", "convenience", "tobacco", "laundry", "hairdresser", "butcher", "pastry", "ice_cream", "deli", "stationery", "grocery", "vending_machine", "kindergarten", "school", "community_centre"]
MEDIO = ["doctor", "dentist", "clinic", "physiotherapist", "veterinary", "optometrist", "psychotherapist", "physiotherapist-osteopathy", "alternative", "parking", "bicycle_rental", "car_sharing", "recreation_ground", "scrub", "swimming_pool", "sports_centre", "bowling_alley", "clothes", "shoes", "florist", "hardware", "chemist", "pet", "books", "gift", "optician", "beauty", "mobile_phone", "jewelry", "toys", "electronics", "bicycle", "travel_agency", "dry_cleaning", "photo", "video", "confectionery", "alcohol", "wine", "cheese", "dairy", "seafood", "pasta", "spices", "tea", "coffee", "coffee_roasting", "herbalist", "tattoo", "massage", "spa", "copyshop", "shoe_repair", "tailor", "sewing", "fabric", "bag", "fashion_accessories", "cosmetics", "variety_store", "second_hand", "video_games", "sports", "nutrition_supplements", "perfumery", "watches", "baby_goods", "houseware", "repair", "mobile_phone_accessories", "party", "religion", "locksmith", "art", "frame", "ticket", "food", "general", "pet_grooming", "library", "music_school", "driving_school"]

AMENITY_TO_CLASS = {a: 'breve' for a in BREVE}
AMENITY_TO_CLASS.update({a: 'medio' for a in MEDIO})

# Globals for OMI
POOL_OMI_GDF = None

def init_omi_globals():
    """Initializes globals for OMI zone lookup."""
    global POOL_OMI_GDF
    if POOL_OMI_GDF is not None or gpd is None: return
    
    omi_path = os.path.join(os.path.dirname(__file__), "..", "static_data", "omi_zones.geojson")
    try:
        if os.path.exists(omi_path):
            POOL_OMI_GDF = gpd.read_file(omi_path)
            # Assicuriamoci che il CRS sia quello geografico corretto
            if POOL_OMI_GDF.crs is None:
                POOL_OMI_GDF.set_crs(epsg=4326, inplace=True)
            elif POOL_OMI_GDF.crs.to_epsg() != 4326:
                POOL_OMI_GDF = POOL_OMI_GDF.to_crs(epsg=4326)
    except Exception as e:
        print(f"Error loading OMI GeoJSON: {e}")

def get_omi_zone(lat, lon):
    """Finds the OMI zone (CODZONA) for a given lat, lon point."""
    if POOL_OMI_GDF is None or lat is None or lon is None or Point is None:
        return None
    
    try:
        p = Point(lon, lat)
        # Fast spatial filtering using sindex if present, otherwise iteration
        # Since zones are few (approx 50-100), iteration is very fast
        for _, row in POOL_OMI_GDF.iterrows():
            if row.geometry.contains(p):
                return row.get('CODZONA')
    except Exception:
        pass
    return None

# Globals for Amenity (Initialized in main or worker)
POOL_POI_TREE = None
POOL_POI_META = None # Lista di (category_idx, amenity_idx, threshold_S)
POOL_CATEGORIES = [] # Lista di nomi categorie ['commerciale', ...]
POOL_CAT_AMENITIES = [] # Liste di amenity names per categoria
POOL_GEOCODER = None

def init_geocoder_globals():
    global POOL_GEOCODER
    if POOL_GEOCODER is not None: return
    pbf_path = os.getenv("OSM_PBF_PATH")
    if not pbf_path:
        return
    if not os.path.isabs(pbf_path):
        pbf_path = str((_backend_path / pbf_path).resolve())
    if os.path.exists(pbf_path):
        try:
            POOL_GEOCODER = OSMGeocodingService(pbf_path)
        except Exception as e:
            print(f"Unable to initialize OSM geocoder: {type(e).__name__}: {e}")

def init_amenity_globals():
    global POOL_POI_TREE, POOL_POI_META, POOL_CATEGORIES, POOL_CAT_AMENITIES
    if POOL_POI_TREE is not None: return
    
    # Fix: Resolve POI_PATH reliably
    poi_path_str = require_env("POI_PATH")
    poi_path = Path(poi_path_str)
    
    if not poi_path.is_absolute():
        if poi_path_str.startswith("backend/"):
            poi_path = _backend_path.parent / poi_path
        else:
            poi_path = _backend_path / poi_path
    
    if not poi_path.exists():
        print(f"Warning: POI file not found at {poi_path} (Resolved from: {poi_path_str})")
        return

    try:
        with open(poi_path, 'r', encoding='utf-8') as f:
            pois_by_cat = json.load(f)
        
        all_poi_coords = []
        all_poi_meta = []
        
        # Normalizza nomi categorie per uniformità con il resto dell'app
        cat_map = {
            'sanità': 'healthcare',
            'sanita': 'healthcare',
            'healthcare': 'healthcare',
            'mobilità': 'mobility',
            'mobilita': 'mobility',
            'mobility': 'mobility',
            'verde': 'green',
            'green': 'green',
            'sport': 'sport',
            'commerciale': 'commercial',
            'commercial': 'commercial',
            'educazione': 'education',
            'education': 'education'
        }
        
        POOL_CATEGORIES = sorted([cat_map.get(k, k) for k in pois_by_cat.keys()])
        cat_to_idx = {c: i for i, c in enumerate(POOL_CATEGORIES)}
        
        # Per ogni categoria, identifichiamo tutte le sue possibili amenità
        POOL_CAT_AMENITIES = [[] for _ in range(len(POOL_CATEGORIES))]
        
        for raw_cat, amenities in pois_by_cat.items():
            cat = cat_map.get(raw_cat, raw_cat)
            c_idx = cat_to_idx[cat]
            for amenity, points in amenities.items():
                POOL_CAT_AMENITIES[c_idx].append(amenity)
                a_idx = len(POOL_CAT_AMENITIES[c_idx]) - 1
                threshold = AMENITY_TO_CLASS.get(amenity, 'lungo')
                S = SERVICE_BASE[threshold]
                
                for p in points:
                    all_poi_coords.append([np.radians(p['lat']), np.radians(p['lon'])])
                    all_poi_meta.append((c_idx, a_idx, S))
        
        if all_poi_coords and BallTree:
            POOL_POI_TREE = BallTree(np.array(all_poi_coords), metric='haversine')
            POOL_POI_META = all_poi_meta
    except Exception as e:
        print(f"Error initializing amenity globals: {e}")

def get_amenity_scores(lat, lon):
    """Calculates scores for the 6 categories for a given lat/lon point."""
    if POOL_POI_TREE is None or lat is None or lon is None:
        return {cat: 0.0 for cat in ['commercial', 'education', 'mobility', 'healthcare', 'sport', 'green']}
    
    U = URBAN_MULTIPLIER[DEFAULT_ZONE]
    max_dist_rad = MAX_DISTANCE_M / 1000 / EARTH_RADIUS_KM
    
    query_point = np.array([[np.radians(lat), np.radians(lon)]])
    indices, distances = POOL_POI_TREE.query_radius(query_point, r=max_dist_rad, return_distance=True)
    
    # Initialize accumulator: [category_idx][amenity_idx] = sum_scores
    cat_amenity_scores = [[0.0 for _ in a_list] for a_list in POOL_CAT_AMENITIES]
    
    if len(indices[0]) > 0:
        dist_km = distances[0] * EARTH_RADIUS_KM
        for i, poi_idx in enumerate(indices[0]):
            c_idx, a_idx, S = POOL_POI_META[poi_idx]
            x = dist_km[i]
            # Formula: f(x) = e^(-(x / (S * U))^3)
            score = np.exp(-((x / (S * U)) ** 3))
            cat_amenity_scores[c_idx][a_idx] += score
    
    # Average per category
    final_scores = {}
    for i, cat_name in enumerate(POOL_CATEGORIES):
        scores = cat_amenity_scores[i]
        if not scores: # If the category has no amenities (unlikely)
            final_scores[cat_name] = 0.0
        else:
            final_scores[cat_name] = sum(scores) / len(scores)
            
    return final_scores

# --- INTERNAL HELPER FUNCTIONS ---

def _load_bytes(filename: str) -> bytes:
    full_path = os.path.join(PATH_XML, filename)
    if not os.path.exists(full_path):
        return b""
    with open(full_path, "rb") as f:
        return f.read()

def _to_float(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).strip().replace(",", ".")
    try:
        return float(s)
    except:
        return None

def _parse_date(s):
    if not s:
        return pd.NaT
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce")
    return dt


def select_coordinates(xml_lat, xml_lon, geocode_result=None):
    """Keep valid source coordinates; use address-level OSM only to fill gaps."""
    valid_xml = (
        xml_lat is not None and xml_lon is not None
        and -90 <= xml_lat <= 90 and -180 <= xml_lon <= 180
    )
    if valid_xml:
        return xml_lat, xml_lon, "xml", None
    if geocode_result and geocode_result.get("score", 0) >= 150:
        lat, lon = geocode_result.get("lat"), geocode_result.get("lon")
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon, geocode_result.get("provenance", "osm_address"), geocode_result.get("confidence")
    return xml_lat, xml_lon, None, None


def enrich_spatial_attributes(df: pd.DataFrame) -> pd.DataFrame:
    """Attach OMI and POI data after parsing/geocoding, in the parent process."""
    if df.empty:
        return df
    init_omi_globals()
    init_amenity_globals()
    score_rows = df.apply(lambda row: get_amenity_scores(row.get('latitude'), row.get('longitude')), axis=1)
    if len(score_rows):
        score_frame = pd.DataFrame(score_rows.tolist(), index=df.index)
        for column in score_frame:
            df[column] = score_frame[column]
    df['omi_zone'] = [get_omi_zone(lat, lon) for lat, lon in zip(df['latitude'], df['longitude'])]
    return df


def apply_application_scoring(df: pd.DataFrame) -> pd.DataFrame:
    """Compute MURENA's deterministic application scores after enrichment."""
    if df.empty:
        return df
    for col in ['commercial', 'education', 'mobility', 'healthcare', 'sport', 'green']:
        if col in df.columns:
            df[col] = (df[col].rank(pct=True) * 100).round(2)
    scoring_inputs = (
        ('energy_class', 'energy_score_class', map_classe_score),
        ('heating_system_type', 'energy_score_plant', map_impianto_score),
        ('envelope_winter_quality', 'energy_score_envelope', map_involucro_score),
        ('renewable_sources', 'energy_score_renewables', map_rinnovabili_score),
    )
    for source, target, scorer in scoring_inputs:
        if source in df.columns:
            df[target] = df[source].map(scorer)
        elif target not in df.columns:
            df[target] = 1
    df['energy_score_total'] = df[['energy_score_class', 'energy_score_plant', 'energy_score_envelope', 'energy_score_renewables']].sum(axis=1)
    return df


def validate_application_records(df: pd.DataFrame) -> dict[str, int]:
    """Count suspicious values without dropping or rewriting source records."""
    report = {'records': len(df), 'missing_cadastral_key': 0, 'invalid_coordinates': 0}
    cadastral = ['comune_code', 'cadastral_sheet', 'cadastral_parcel', 'cadastral_subaltern']
    if set(cadastral).issubset(df.columns):
        report['missing_cadastral_key'] = int(df[cadastral].isna().any(axis=1).sum())
    if {'latitude', 'longitude'}.issubset(df.columns):
        valid = df['latitude'].between(-90, 90) & df['longitude'].between(-180, 180)
        report['invalid_coordinates'] = int((~valid).sum())
    return report


def deduplicate_cadastral_units(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the newest certificate only for complete, municipality-qualified keys."""
    keys = ['comune_code', 'cadastral_sheet', 'cadastral_parcel', 'cadastral_subaltern']
    if df.empty or not set(keys).issubset(df.columns):
        return df
    complete = df[keys].notna().all(axis=1)
    identified, unidentified = df.loc[complete].copy(), df.loc[~complete].copy()
    if identified.empty:
        return df.copy()
    if 'address' in identified.columns:
        first_address = identified.groupby(keys, dropna=False)['address'].transform('first')
        identified = identified[identified['address'] == first_address]
    order = keys + (['effective_date'] if 'effective_date' in identified.columns else [])
    ascending = [True] * len(keys) + ([False] if 'effective_date' in identified.columns else [])
    identified = identified.sort_values(order, ascending=ascending)
    identified = identified.groupby(keys, dropna=False).head(1)
    return pd.concat([identified, unidentified], ignore_index=True)


def _normalized_address(value: Any) -> str:
    if value is None or pd.isna(value):
        return ''
    return re.sub(r'[^a-z0-9]+', '', str(value).lower())


def is_single_physical_building_group(group: pd.DataFrame, max_spread_m: float = 50.0) -> bool:
    """Require one address and close, complete coordinates before parcel aggregation."""
    if group.empty or not {'address', 'latitude', 'longitude'}.issubset(group.columns):
        return False
    addresses = {_normalized_address(v) for v in group['address']}
    addresses.discard('')
    if len(addresses) != 1 or group['address'].isna().any():
        return False
    lat = pd.to_numeric(group['latitude'], errors='coerce').to_numpy(dtype=float, na_value=np.nan)
    lon = pd.to_numeric(group['longitude'], errors='coerce').to_numpy(dtype=float, na_value=np.nan)
    if np.isnan(lat).any() or np.isnan(lon).any():
        return False
    if (np.abs(lat) > 90).any() or (np.abs(lon) > 180).any():
        return False
    lat0, lon0 = np.radians(lat.mean()), np.radians(lon.mean())
    dlat, dlon = np.radians(lat) - lat0, np.radians(lon) - lon0
    a = np.sin(dlat / 2) ** 2 + np.cos(lat0) * np.cos(np.radians(lat)) * np.sin(dlon / 2) ** 2
    distances = 2 * 6_371_000 * np.arcsin(np.sqrt(a))
    return bool(distances.max(initial=0) <= max_spread_m)


def generate_metaestates(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate eligible cadastral units while recording every reduction method."""
    if df.empty:
        return df
    group_cols = ['comune_code', 'cadastral_sheet', 'cadastral_parcel']
    rows: list[dict[str, Any]] = []
    for key, group in df.groupby(group_cols, dropna=False):
        if len(group) < 2 or pd.isna(key[1]) or pd.isna(key[2]):
            continue
        if not is_single_physical_building_group(group):
            continue
        weights = pd.to_numeric(group['surface_area'], errors='coerce')
        valid_weights = weights.notna() & (weights > 0)

        def weighted_mean(column: str):
            if column not in group or not valid_weights.any():
                return None
            values = pd.to_numeric(group[column], errors='coerce')
            mask = valid_weights & values.notna()
            if not mask.any():
                return None
            return float(np.average(values[mask], weights=weights[mask]))

        def weighted_mode(column: str):
            if column not in group:
                return None
            weighted = pd.DataFrame({'value': group[column], 'weight': weights})
            weighted = weighted.dropna(subset=['value', 'weight'])
            weighted = weighted[weighted['weight'] > 0].groupby('value', dropna=False)['weight'].sum()
            if not weighted.empty:
                return weighted.idxmax()
            mode = group[column].mode()
            return mode.iloc[0] if not mode.empty else None

        import ast
        file_names: set[str] = set()
        for value in group['ape_file_list'].dropna():
            try:
                file_names.update(ast.literal_eval(value) if isinstance(value, str) else value)
            except (ValueError, SyntaxError, TypeError):
                continue
        constituent_ids = group['id'].astype(str).tolist()
        weighted_property = valid_weights.any() and group.loc[valid_weights, 'property_type'].notna().any()
        weighted_class = valid_weights.any() and group.loc[valid_weights, 'energy_class'].notna().any()
        methods: dict[str, str] = {
            'constituent_ids': 'id_list_preserved',
            'surface_area': 'sum_of_constituent_unit_areas',
            'property_type': 'surface_weighted_mode_estimate' if weighted_property else 'mode_estimate_no_surface_weights',
            'construction_period': 'mode_estimate',
            'energy_class': 'surface_weighted_mode_estimate_not_certified' if weighted_class else 'mode_estimate_not_certified_no_surface_weights',
            'id': 'generated_metaestate_identifier',
            'is_meta_estate': 'constant_true',
            'energy_class_is_estimate': 'constant_true',
            'cadastral_units_count': 'constituent_count',
            'id_list': 'constituent_ids_preserved',
            'ape_file_list': 'sorted_union',
            'ape_file_list_filtered': 'sorted_union',
            'ape_file_list_filtered_parsed': 'sorted_union',
        }
        for column in df.columns:
            methods.setdefault(column, 'mode_estimate')
        row = {column: weighted_mode(column) for column in df.columns}
        row.update({
            'comune_code': key[0], 'cadastral_sheet': key[1], 'cadastral_parcel': key[2],
            'cadastral_subaltern': 0, 'surface_area': group['surface_area'].sum(min_count=1),
            'property_type': weighted_mode('property_type'),
            'construction_period': weighted_mode('construction_period'),
            'energy_class': weighted_mode('energy_class'),
            'id': f"M{len(rows) + 1:05d}", 'is_meta_estate': True,
            'energy_class_is_estimate': True, 'cadastral_units_count': len(group),
            'id_list': str(constituent_ids), 'ape_file_list': str(sorted(file_names)),
            'ape_file_list_filtered': str(sorted(file_names)),
            'ape_file_list_filtered_parsed': str(sorted(file_names)),
        })
        for column in ('epglnren', 'epglren', 'co2_emissions', 'commercial', 'education', 'mobility', 'healthcare', 'sport', 'green',
                       'energy_score_plant', 'energy_score_envelope', 'energy_score_renewables'):
            if column in df.columns:
                row[column] = weighted_mean(column)
                methods[column] = 'surface_weighted_mean_estimate' if row[column] is not None else 'null_no_valid_surface_weights'
        row['latitude'] = weighted_mean('latitude')
        row['longitude'] = weighted_mean('longitude')
        row['energy_score_class'] = map_classe_score(row['energy_class'])
        row['energy_score_total'] = sum(row.get(c) or 0 for c in (
            'energy_score_class', 'energy_score_plant', 'energy_score_envelope', 'energy_score_renewables'
        ))
        methods['energy_score_class'] = 'derived_from_estimated_energy_class'
        methods['energy_score_total'] = 'sum_of_aggregated_component_scores'
        methods['latitude'] = methods['longitude'] = 'mean_of_coordinates_within_50m_estimate'
        methods['omi_zone'] = 'mode'
        row['aggregation_methods'] = json.dumps(methods, sort_keys=True)
        rows.append(row)
    if not rows:
        return df
    return pd.concat([df, pd.DataFrame(rows)], ignore_index=True)

# --- PARSER CORE ---

def parse_ape_xml(xml_text: str | bytes) -> dict:
    ns = {'ape': 'http://www.csi.it/sicee/siceeweb/xml/xmlapecompleto2015/data'}
    data = {}
    try:
        root = etree.fromstring(xml_text if isinstance(xml_text, bytes) else xml_text.encode('utf-8'))

        def sxp(x):
            val = root.xpath(f'string({x})', namespaces=ns)
            return val.strip() if isinstance(val, str) and val.strip() else None

        def xs(paths):
            for p in paths:
                v = sxp(p)
                if v: return v
            return None

        tolower = "translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"

        # General data
        data['epc_id'] = sxp('//ape:datiAttestato/ape:codiceIdentificativo')
        data['address'] = xs(['//ape:datiCalcolo/ape:datiGenerali/ape:indirizzo','//ape:datiGenerali/ape:indirizzo'])
        data['house_number'] = xs([
            '//ape:datiGenerali/ape:datiIdentificativi/ape:numeroCivico',
            '//ape:datiGenerali/ape:datiIdentificativi/ape:civico',
            '//ape:datiCalcolo/ape:datiGenerali/ape:civico',
            '//ape:civico'
        ])
        data['city'] = xs(['//ape:datiCalcolo/ape:datiGenerali/ape:comune','//ape:datiGenerali/ape:datiExtra/ape:comune'])
        data['municipality'] = data['city']
        data['istat_code'] = sxp('//ape:datiCalcolo/ape:datiGenerali/ape:codiceISTAT')
        data['climate_zone'] = xs(['//ape:datiCalcolo/ape:datiGenerali/ape:zonaClimatica','//ape:datiGenerali/ape:zonaClimatica'])
        data['construction_period'] = xs(['//ape:datiGenerali/ape:datiIdentificativi/ape:annoCostruzione','//ape:annoCostruzione'])
        data['latitude'] = xs([
            '//ape:datiCalcolo/ape:datiGenerali/ape:latitudineGIS',
            '//ape:datiGenerali/ape:datiIdentificativi/ape:LatitudineGIS',
            '//ape:latitudineGIS'
        ])
        data['longitude'] = xs([
            '//ape:datiCalcolo/ape:datiGenerali/ape:longitudineGIS',
            '//ape:datiGenerali/ape:datiIdentificativi/ape:LongitudineGIS',
            '//ape:longitudineGIS'
        ])
        data['surface'] = sxp('//ape:datiGenerali/ape:datiIdentificativi/ape:superficieUtileRiscaldata')
        data['issue_date'] = sxp('//ape:dataEmissione')
        data['expiration_date'] = sxp('//ape:datiAttestato/ape:dataScadenza')
        data['use_destination_code'] = sxp('//ape:datiGenerali/ape:destinazioneUso')
        data['dpr412_class_code'] = sxp('//ape:datiGenerali/ape:classificazioneDPR412')
        data['property_type'] = MAPPING_DPR412.get(data['dpr412_class_code'])
        data['attestation_object_code'] = sxp('//ape:datiGenerali/ape:oggettoAttestato')
        data['building_typology_code'] = xs(['//ape:datiGenerali/ape:datiExtra/ape:tipologiaEdilizia','//ape:datiExtra/ape:tipologiaEdilizia'])
        data['floor'] = xs(['//ape:datiGenerali/ape:datiIdentificativi/ape:piano','//ape:datiFabbricato//ape:piano'])

        # Performance
        data['energy_class'] = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:classeEnergetica')
        data['epglnren'] = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:epglnren')
        data['epglren'] = sxp('//ape:prestazioneImpianti/ape:epglren')
        data['co2_emissions'] = sxp('//ape:prestazioneImpianti/ape:emissioniCO2')

        # Services present
        services = []
        if sxp('//ape:datiImpianti/ape:climatizzazioneInvernale/ape:impiantoSimulato') is None:
            if (sxp('//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:climatizzazioneInvernale') or '').lower() in ('true', '1'):
                services.append('Heating')
        if sxp('//ape:datiImpianti/ape:produzioneACS/ape:impiantoSimulato') is None:
            if (sxp('//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:produzioneAcquaCaldaSanitaria') or '').lower() in ('true', '1'):
                services.append('DHW')

        for tag, label in [('climatizzazioneEstiva', 'Cooling'),('ventilazioneMeccanica', 'Ventilation'),('illuminazione', 'Lighting'),('trasportoPersoneCose', 'Elevators/Transport')]:
            v = sxp(f'//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:{tag}')
            if v and v.lower() in ('true', '1'): services.append(label)
        data['services_present'] = services
        
        # Energy Carrier
        consumptions_kwh = {}
        for name, path_xp in VETTORI_XPATHS.items():
            c_str = sxp(path_xp)
            if c_str:
                try:
                    c_val = float(c_str.replace(',', '.'))
                    if name in VETTORI_PCI: c_val *= VETTORI_PCI[name]
                    consumptions_kwh[name] = c_val
                except: continue
        data['main_energy_carrier'] = sorted(consumptions_kwh.items(), key=lambda x: x[1], reverse=True)[0][0] if consumptions_kwh else None

        # Cadastral data
        cad_data = {'comune_code': None, 'cadastral_sheet': None, 'cadastral_parcel': None, 'cadastral_subaltern': None}
        node = root.xpath('.//ape:datiCatastali', namespaces=ns)
        if node:
            n = node[0]
            cad_data['comune_code'] = n.xpath('string(ape:codiceCatastale)', namespaces=ns).strip() or None
            cad_data['cadastral_sheet'] = n.xpath('string(ape:foglio)', namespaces=ns).strip() or None
            cad_data['cadastral_parcel'] = n.xpath('string(ape:particella)', namespaces=ns).strip() or None
            
            # Complex subaltern extraction (subDA, subA)
            def _clr_sub(s):
                s = s.strip()
                if not s: return ""
                return s.lstrip('0') or '0'
            
            subDA = _clr_sub(n.xpath('string(.//ape:subalterni/ape:subDA)', namespaces=ns))
            subA = _clr_sub(n.xpath('string(.//ape:subalterni/ape:subA)', namespaces=ns))
            
            if subDA and subA:
                if subDA == subA:
                    cad_data['cadastral_subaltern'] = subDA
                else:
                    cad_data['cadastral_subaltern'] = f"{subDA},{subA}"
            elif subDA:
                cad_data['cadastral_subaltern'] = subDA
            elif subA:
                cad_data['cadastral_subaltern'] = subA
        data.update(cad_data)

        # Building envelope quality
        data['envelope_winter_quality'] = MAPPING_QUALITA_INVOLUCRO.get(sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:inverno'))
        data['envelope_summer_quality'] = MAPPING_QUALITA_INVOLUCRO.get(sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:estate'))
        
        # Plants/Systems
        def get_inf(paths):
            f_node = None
            for p in paths:
                nodes = root.xpath(p, namespaces=ns)
                if nodes: f_node = nodes[0]; break
            if f_node is None: return {'tecnologia': None, 'anno': None}
            t_cod = f_node.xpath('string(.//ape:impianto[1]/ape:tipoImpianto)', namespaces=ns).strip()
            return {
                'tecnologia': MAPPING_IMPIANTI.get(t_cod, f_node.xpath('string(.//ape:impianto[1]/ape:descrizioneImpianto)', namespaces=ns).strip()),
                'anno': f_node.xpath(f"string(.//*[contains({tolower},'install') and contains({tolower},'anno')][1])", namespaces=ns).strip() or None
            }
        data['impianti'] = {
            'Heating': get_inf(['//ape:datiImpianti//ape:climatizzazioneInvernale','//ape:impianti//ape:impiantoClimatizzazioneInvernale']),
            'DHW': get_inf(['//ape:datiImpianti//ape:produzioneACS','//ape:impianti//ape:impiantoAcquaCaldaSanitaria'])
        }

        # Renewable Sources
        val_fv = float(sxp(VETTORI_XPATHS['Solar photovoltaic']) or 0)
        val_st = float(sxp(VETTORI_XPATHS['Solar thermal']) or 0)
        data['fonti_rinnovabili'] = 'Yes' if (val_fv > 0 or val_st > 0) else 'No'

        # Improvements
        data['classe_target'] = xs(['//ape:raccomandazioni/ape:classificazione/ape:classeEnergetica','//ape:raccomandazioni/ape:interventoRaccomandato[1]/ape:classificazioneRaggiungibile/ape:classeEnergetica'])
        data['tempo_ritorno'] = sxp('//ape:raccomandazioni//ape:tempoRitornoInvestimento')
        data['renewable_sources'] = data['fonti_rinnovabili']
        data['target_energy_class'] = data['classe_target']
        data['payback_period'] = data['tempo_ritorno']
        data['lat'], data['lon'] = data['latitude'], data['longitude']
        data['indirizzo'], data['civico'] = data['address'], data['house_number']

        # Technical building system data (Nominal Power)
        data["heating_nominal_power"] = sxp("//ape:datiImpianti/ape:climatizzazioneInvernale/ape:impianto/ape:potenzaNominale")
        data["dhw_nominal_power"] = sxp("//ape:datiImpianti/ape:produzioneACS/ape:impianto/ape:potenzaNominale")

        # Building envelope areas
        data["opaque_envelope_area"] = sxp("//ape:fabbricato/ape:altriDatiSintetici/ape:superficieOpacaTotale")
        data["transparent_envelope_area"] = sxp("//ape:fabbricato/ape:altriDatiSintetici/ape:superficieVetrataTotale")

        # Energy needs and limits
        data["heating_energy_need"] = sxp("//ape:datiFabbricato/ape:ephnd")
        data["cooling_energy_need"] = sxp("//ape:datiFabbricato/ape:epcnd")
        data["heating_limit"] = sxp("//ape:datiExtra/ape:ephndLim")
        data["primary_energy_limit"] = sxp("//ape:datiExtra/ape:EPglnrenRifStandard")

        # Assessor information
        data["assessor_name"] = sxp("//ape:soggettoCertificatore/ape:nome")
        data["assessor_surname"] = sxp("//ape:soggettoCertificatore/ape:cognome")

    except Exception as e:
        raise ValueError(f"APE XML parsing failed: {e}") from e
    return data

# --- PARALLELIZATION WORKER ---

def process_single_xml(fname: str) -> dict:
    """Parse/map one XML to an application row; enrichment runs after workers finish."""
    
    try:
        xml_bytes = _load_bytes(fname)
        if not xml_bytes:
            return None
        p = parse_ape_xml(xml_bytes)
        
        unita = p.get("subalterno") or os.path.splitext(os.path.basename(fname))[0]
        
        # Use address components from already parsed dict 'p'
        address = p.get("address")
        civic = p.get("house_number")
        
        lat_xml, lon_xml = _to_float(p.get("latitude")), _to_float(p.get("longitude"))
        res_lat, res_lon, coordinate_provenance, geocoding_confidence = select_coordinates(lat_xml, lon_xml)
        
        res = {
            "ape_file_list": os.path.basename(fname),
            "comune_code": p.get("comune_code"),
            "cadastral_sheet": p.get("cadastral_sheet"),
            "cadastral_parcel": p.get("cadastral_parcel"),
            "cadastral_subaltern": p.get("cadastral_subaltern"),
            "surface_area": _to_float(p.get("surface")),
            "address": address,
            "house_number": civic,
            "latitude": res_lat,
            "longitude": res_lon,
            "xml_latitude": lat_xml,
            "xml_longitude": lon_xml,
            "coordinate_provenance": coordinate_provenance,
            "geocoding_confidence": geocoding_confidence,
            "omi_zone": None,
            "property_type": p.get("property_type"),
            "construction_period": p.get("construction_period"),
            "effective_date": _parse_date(p.get("issue_date")),
            "energy_class": p.get("energy_class"),
            "epglnren": _to_float(p.get("epglnren")),
            "epglren": _to_float(p.get("epglren")),
            "co2_emissions": _to_float(p.get("co2_emissions")),
            "has_heating": "Heating" in (p.get("services_present") or []),
            "has_dhw": "DHW" in (p.get("services_present") or []),
            "floor": p.get("floor"),
            "envelope_winter_quality": p.get("envelope_winter_quality"),
            "envelope_summer_quality": p.get("envelope_summer_quality"),
            "renewable_sources": p.get("renewable_sources"),
            "heating_system_year": p.get('impianti', {}).get('Heating', {}).get('anno'),
            "heating_system_type": p.get('impianti', {}).get('Heating', {}).get('tecnologia'),
            "dhw_system_year": p.get('impianti', {}).get('DHW', {}).get('anno'),
            "dhw_system_type": p.get('impianti', {}).get('DHW', {}).get('tecnologia'),
            "target_energy_class": p.get("target_energy_class"),
            "payback_period": _to_float(p.get("payback_period")),
            "epc_id": p.get("epc_id"),
            "heating_nominal_power": _to_float(p.get("heating_nominal_power")),
            "dhw_nominal_power": _to_float(p.get("dhw_nominal_power")),
            "opaque_envelope_area": _to_float(p.get("opaque_envelope_area")),
            "transparent_envelope_area": _to_float(p.get("transparent_envelope_area")),
            "heating_energy_need": _to_float(p.get("heating_energy_need")),
            "cooling_energy_need": _to_float(p.get("cooling_energy_need")),
            "heating_limit": _to_float(p.get("heating_limit")),
            "primary_energy_limit": _to_float(p.get("primary_energy_limit")),
            "assessor_name": p.get("assessor_name"),
            "assessor_surname": p.get("assessor_surname"),
            "_unita": str(unita)
        }
        
        # Unique ID based on cadastral reference
        res["id"] = f"{res['comune_code']}_{res['cadastral_sheet']}_{res['cadastral_parcel']}_{res['cadastral_subaltern'] or res['_unita']}"
        res["is_meta_estate"] = False
        res["cadastral_units_count"] = 1
        res["id_list"] = res["id"]
        
        return res
    except Exception as e:
        print(f"Error parsing {fname}: {type(e).__name__}: {e}")
        return None

# --- DATA LOADING ---

from concurrent.futures import ProcessPoolExecutor

def _load_ape_df(file_list: List[str]) -> pd.DataFrame:
    """Loads XML data, filters by TARGET_COMUNE_CODE and returns a DataFrame."""
    all_rows = []

    with ProcessPoolExecutor() as executor:
        # Use generator to process results as they arrive
        results_gen = tqdm(
            executor.map(process_single_xml, file_list),
            total=len(file_list),
            desc="Processing XML files (Parallel)",
            mininterval=1.0
        )
        
        for res in results_gen:
            if res is not None:
                # Apply the filter immediately to minimize memory usage
                if res.get('comune_code') == TARGET_COMUNE_CODE:
                    all_rows.append(res)

    return pd.DataFrame(all_rows)

def improve_df_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Improves DataFrame coordinates via local OSM geocoding."""
    if df.empty or 'address' not in df.columns:
        return df
    
    init_geocoder_globals()
    if not POOL_GEOCODER:
        print("Skipping geocoding: OSM file not found.")
        return df

    # Identify unique addresses to reduce load
    unique_addr = df[['address', 'house_number']].drop_duplicates()
    
    # Serial geocoding for stability
    def _geo_worker(row):
        addr = row['address']
        num = row['house_number']
        if not addr: return None
        res = POOL_GEOCODER.geocode(street=addr, number=num, city=TARGET_CITY)
        if res:
    # Geocoding is done once in the parent process; POI and OMI enrichment follows.
            new_lat, new_lon = res['lat'], res['lon']
            return {
                'address': addr, 'house_number': num, 
                'lat_osm': new_lat, 'lon_osm': new_lon, 'score': res['score'],
            }
        return None

    print(f"Geocoding {len(unique_addr)} unique addresses...")
    geo_results = []
    for _, row in tqdm(unique_addr.iterrows(), total=len(unique_addr), desc="Geocoding"):
        geo_results.append(_geo_worker(row))
    
    # Result mapping
    geo_map = {}
    for r in geo_results:
        if r:
            geo_map[(r['address'], r['house_number'])] = r
    
    # Update DataFrame with stats
    stats = {"updated": 0, "missing_filled": 0}

    def _update_row(row):
        key = (row['address'], row['house_number'])
        lat_xml = row.get('latitude')
        lon_xml = row.get('longitude')
        
        match = geo_map.get(key)
        if match:
            try:
                is_missing = (
                    pd.isna(lat_xml) or pd.isna(lon_xml)
                    or not (-90 <= float(lat_xml) <= 90)
                    or not (-180 <= float(lon_xml) <= 180)
                )
            except (TypeError, ValueError):
                is_missing = True
            
            # Update if match is high quality or if XML coords are missing
            if is_missing and match['score'] >= 150:
                row['latitude'] = match['lat_osm']
                row['longitude'] = match['lon_osm']
                row['omi_zone'] = match['omi_zone']
                row['coordinate_provenance'] = 'osm_address'
                row['geocoding_confidence'] = 'high' if match['score'] >= 400 else 'medium'
                
                stats["updated"] += 1
                stats["missing_filled"] += 1
        return row

    # Apply the update
    print("Applying new coordinates to DataFrame...")
    df = df.apply(_update_row, axis=1)

    print(f"\n--- GEOCODING STATISTICS ---")
    print(f"Rows processed: {len(df)}")
    print(f"Rows updated (OSM): {stats['updated']} ({stats['updated']/len(df)*100:.1f}%)")
    print(f"Missing coordinates recovered: {stats['missing_filled']}")
    print(f"-----------------------------\n")
    
    return df

if __name__ == "__main__":
    # Use environment variable for output path
    output_file_str = os.getenv("DATASET_FULL", "data/metadata/estates.parquet")
    output_file = Path(output_file_str)
    
    # Resolve relative path against backend root
    if not output_file.is_absolute():
        if output_file_str.startswith("backend/"):
            output_file = _backend_path.parent / output_file
        else:
            output_file = _backend_path / output_file
            
    # Ensure directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file = str(output_file)
    
    # If the file already exists, load it directly without re-processing XMLs
    if os.path.exists(output_file):
        print(f"File {output_file} found. Loading...")
        df = pd.read_parquet(output_file)
    else:
        # Pre-install DuckDB spatial extension to avoid race conditions in workers
        try:
            duckdb.connect().execute("INSTALL spatial;")
        except Exception:
            pass
            
        files = [os.path.basename(f) for f in glob.glob(os.path.join(PATH_XML, "*.xml"))]
        if files:
            df = _load_ape_df(files)
            print(f"\nProcessed {len(files)} XML files.")
        else:
            print("No XML files found.")
            df = pd.DataFrame()

    # Independent application pipeline stages: address enrichment, spatial
    # enrichment, validation/scoring, unit deduplication, metaestate aggregation.
    if not df.empty:
        df = improve_df_coordinates(df)
        df = enrich_spatial_attributes(df)
        validation_report = validate_application_records(df)
        print(f"Application record validation: {json.dumps(validation_report, sort_keys=True)}")
        df = apply_application_scoring(df)

    if not df.empty:
        # Final global sorting (filter already applied during parsing)
        print("Final sorting and cleaning...")
        if 'effective_date' in df.columns:
            df = df.dropna(subset=['effective_date'])
            df['effective_date'] = pd.to_datetime(df['effective_date'])
            
        sort_cols = []
        sort_asc = []
        if '_unita' in df.columns: 
            sort_cols.append('_unita'); sort_asc.append(True)
        if 'effective_date' in df.columns: 
            sort_cols.append('effective_date'); sort_asc.append(False)
        
        if sort_cols:
            df = df.sort_values(sort_cols, ascending=sort_asc).reset_index(drop=True)
        
        # Nullable identifiers stay null; zero is not a cadastral identifier.
        for col in ['cadastral_sheet', 'cadastral_parcel', 'cadastral_subaltern']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')

        # 1. Removal of rows without OMI zone
        if 'omi_zone' in df.columns:
            df = df.dropna(subset=['omi_zone'])
            df = df[df['omi_zone'] != ""]

        print("Deduplicating complete cadastral unit keys...")
        df = deduplicate_cadastral_units(df)

        if '_unita' in df.columns:
            df = df.drop(columns=['_unita'])

        # Removal of technical/intermediate columns
        cols_to_drop = [
            'dhw_system_type', 'dhw_system_year', 'heating_system_type', 'heating_system_year', 
            'renewable_sources', 'envelope_summer_quality', 'envelope_winter_quality', 
            'floor', 'has_dhw', 'has_heating', 'payback_period'
        ]
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
            
        # Initialize extra columns and IDs for normal rows (necessary before metaimmobili generation)
        df = df.reset_index(drop=True)
        df['id'] = (df.index + 1).astype(str)
        df['is_meta_estate'] = False
        df['energy_class_is_estimate'] = False
        df['aggregation_methods'] = None
        df['cadastral_units_count'] = 1
        df['id_list'] = None
        
        # Handle XML file columns (list as string format for compatibility)
        df['ape_file_list'] = df['ape_file_list'].apply(lambda x: str([x]) if isinstance(x, str) else "[]")
        df['ape_file_list_filtered'] = df['ape_file_list']
        df['ape_file_list_filtered_parsed'] = df['ape_file_list']

        print("Generating validated metaestates...")
        df = generate_metaestates(df)

        # Reorder columns: id, is_meta_estate, cadastral_units_count, id_list and file list first
        first_cols = [
            'id', 'is_meta_estate', 'cadastral_units_count', 'id_list',
            'ape_file_list', 'ape_file_list_filtered', 'ape_file_list_filtered_parsed'
        ]
        cols = first_cols + [c for c in df.columns if c not in first_cols]
        df = df[cols]
            
        # Final save with sorted data in Parquet format
        df.to_parquet(output_file, index=False)
        print(f"DataFrame saved to {output_file}. Final row count: {len(df)}")
