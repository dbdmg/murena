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
import duckdb
import re
try:
    from sklearn.neighbors import BallTree
except ImportError:
    BallTree = None

try:
    from shapely.geometry import Point
    import geopandas as gpd
except ImportError:
    Point = None
    gpd = None

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# --- CONFIGURATION ---
# Use environment variable for data path or a generic placeholder
PATH_XML = os.environ.get("APE_XML_PATH", "./merged_xml_data")
TARGET_CITY = os.environ.get("TARGET_CITY", "Torino")
TARGET_PROVINCE = os.environ.get("TARGET_PROVINCE", "TO")
TARGET_COMUNE_CODE = os.environ.get("TARGET_COMUNE_CODE", "L219")

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
            res = {"lat": c[0], "lon": c[1], "street": c[2], "house_number": c[3], "city": c[4], "score": 0}
            
            # SCORING
            # City (100)
            if city_clean == res['city']: res['score'] += 100
            
            # Street (Max 150)
            target_street = res['street'] or ""
            if street_clean == target_street: res['score'] += 150
            elif street_clean in target_street or target_street in street_clean: res['score'] += 50
            
            # House Number (Max 300)
            if final_number:
                target_num = (res['house_number'] or "").lower()
                input_num = final_number.lower().replace(' ', '')
                if input_num == target_num.replace(' ', ''):
                    res['score'] += 300
                elif target_num and re.match(rf"^{re.escape(input_num)}(\D|$)", target_num):
                    res['score'] += 150
                elif target_num:
                    res['score'] -= 100 
            
            results.append(res)
            
        return max(results, key=lambda x: x['score'])

# --- SCORING FUNCTIONS ---

def map_impianto_score(impianto_desc):
    if not isinstance(impianto_desc, str):
        return 1
    desc = impianto_desc.lower()
    if "pompa di calore" in desc or "teleriscaldamento" in desc:
        return 5
    if "condensazione" in desc or "biomassa" in desc:
        return 3
    return 1

def map_involucro_score(qualita):
    if not isinstance(qualita, str):
        return 1
    q = qualita.lower()
    if "sorridente" in q:
        return 5
    if "basita" in q:
        return 3
    if "triste" in q:
        return 1
    return 1

def map_rinnovabili_score(rinnovabile_val):
    if rinnovabile_val in [True, "Sì", "Si", "true", 1]:
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
    'Energia elettrica da rete': '//ape:prestazioneImpianti/ape:energiaElettricaRete/ape:consumoAnnuo',
    'Gas naturale': '//ape:prestazioneImpianti/ape:gasNaturale/ape:consumoAnnuo',
    'GPL': '//ape:prestazioneImpianti/ape:gpl/ape:consumoAnnuo',
    'Carbone': '//ape:prestazioneImpianti/ape:carbone/ape:consumoAnnuo',
    'Gasolio': '//ape:prestazioneImpianti/ape:gasolio/ape:consumoAnnuo',
    'Olio combustibile': '//ape:prestazioneImpianti/ape:olioCombustibile/ape:consumoAnnuo',
    'Biomasse solide': '//ape:prestazioneImpianti/ape:biomasseSolide/ape:consumoAnnuo',
    'Biomasse liquide': '//ape:prestazioneImpianti/ape:biomasseLiquide/ape:consumoAnnuo',
    'Biomasse gassose': '//ape:prestazioneImpianti/ape:biomasseGassose/ape:consumoAnnuo',
    'Solare fotovoltaico': '//ape:prestazioneImpianti/ape:solareFotovoltaico/ape:consumoAnnuo',
    'Solare termico': '//ape:prestazioneImpianti/ape:solareTermico/ape:consumoAnnuo',
    'Eolico': '//ape:prestazioneImpianti/ape:eolico/ape:consumoAnnuo',
    'Teleriscaldamento': '//ape:prestazioneImpianti/ape:teleriscaldamento/ape:consumoAnnuo',
    'Teleraffrescamento': '//ape:prestazioneImpianti/ape:teleraffrescamento/ape:consumoAnnuo'
}

VETTORI_PCI = {
    'Gas naturale': 9.94,
    'GPL': 12.778,
    'Carbone': 7.917,
    'Gasolio': 11.87,
    'Olio combustibile': 11.75,
    'Biomasse solide': 4.67,
    'Biomasse liquide': 7.5,
    'Biomasse gassose': 6.4
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
    # Path del file OSM (aggiornare se necessario)
    pbf_path = "/home/mdeluca/nord-ovest-latest.osm.pbf"
    if os.path.exists(pbf_path):
        try:
            POOL_GEOCODER = OSMGeocodingService(pbf_path)
        except Exception as e:
            # Silenzioso nei worker, ma logghiamo l'errore se critico
            pass

def init_amenity_globals():
    global POOL_POI_TREE, POOL_POI_META, POOL_CATEGORIES, POOL_CAT_AMENITIES
    if POOL_POI_TREE is not None: return
    
    poi_path = "/home/mdeluca/real-estate-ai/backend/notebooks/01_pois/pois_by_category.json"
    if not os.path.exists(poi_path):
        print(f"Warning: POI file not found at {poi_path}")
        return

    try:
        with open(poi_path, 'r', encoding='utf-8') as f:
            pois_by_cat = json.load(f)
        
        all_poi_coords = []
        all_poi_meta = []
        
        # Normalizza nomi categorie per uniformità con il resto dell'app
        cat_map = {
            'sanità': 'sanita',
            'mobilità': 'mobilita',
            'verde': 'verde',
            'sport': 'sport',
            'commerciale': 'commerciale',
            'educazione': 'educazione'
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

cache_bytes: Dict[str, bytes] = {}

def _load_bytes(filename: str) -> bytes:
    if filename not in cache_bytes:
        full_path = os.path.join(PATH_XML, filename)
        if not os.path.exists(full_path):
            return b""
        with open(full_path, "rb") as f:
            cache_bytes[filename] = f.read()
    return cache_bytes[filename]

def _decode_xml(raw: bytes) -> str:
    if not raw:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        text = raw[3:].decode("utf-8", errors='ignore')
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw[2:].decode("utf-16", errors='ignore')
    else:
        try:
            text = raw.decode("utf-8", errors='ignore')
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors='ignore')
    
    # Clean up any "junk" before the XML declaration
    text = re.sub(r'^.*?<\?xml', '<?xml', text, flags=re.DOTALL)
    
    # Remove invalid XML characters (like #x65535/0xFFFF)
    # Valid XML 1.0 ranges: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    text = re.sub(u'[^\u0009\u000a\u000d\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]', '', text)
    
    return text.strip()

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

# --- PARSER CORE ---

def parse_ape_xml(xml_text: str) -> dict:
    ns = {'ape': 'http://www.csi.it/sicee/siceeweb/xml/xmlapecompleto2015/data'}
    data = {}
    try:
        root = etree.fromstring(xml_text.encode('utf-8'))

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
        data['indirizzo'] = xs(['//ape:datiGenerali/ape:indirizzo','//ape:datiCalcolo/ape:datiGenerali/ape:indirizzo'])
        data['civico'] = xs([
            '//ape:datiGenerali/ape:datiIdentificativi/ape:numeroCivico',
            '//ape:datiGenerali/ape:datiIdentificativi/ape:civico',
            '//ape:datiCalcolo/ape:datiGenerali/ape:civico',
            '//ape:civico'
        ])
        data['comune'] = xs(['//ape:datiGenerali/ape:datiExtra/ape:comune','//ape:datiCalcolo/ape:datiGenerali/ape:comune'])
        data['zona_climatica'] = xs(['//ape:datiGenerali/ape:zonaClimatica','//ape:datiCalcolo/ape:datiGenerali/ape:zonaClimatica'])
        data['anno_costruzione'] = xs(['//ape:datiGenerali/ape:annoCostruzione','//ape:datiGenerali/ape:datiIdentificativi/ape:annoCostruzione'])
        data['lat'] = xs([
            '//ape:datiGenerali/ape:LatitudineGIS',
            '//ape:datiCalcolo/ape:datiGenerali/ape:latitudineGIS',
            '//ape:latitudineGIS'
        ])
        data['lon'] = xs([
            '//ape:datiGenerali/ape:LongitudineGIS',
            '//ape:datiCalcolo/ape:datiGenerali/ape:longitudineGIS',
            '//ape:longitudineGIS'
        ])
        data['superficie'] = sxp('//ape:datiGenerali/ape:datiIdentificativi/ape:superficieUtileRiscaldata')
        data['data_emissione'] = sxp('//ape:dataEmissione')
        data['destinazione_uso_cod'] = sxp('//ape:datiGenerali/ape:destinazioneUso')
        data['classificazione_dpr412_cod'] = sxp('//ape:datiGenerali/ape:classificazioneDPR412')
        data['tipologia_bene_immobile'] = MAPPING_DPR412.get(data['classificazione_dpr412_cod'])
        data['oggetto_attestato_cod'] = sxp('//ape:datiGenerali/ape:oggettoAttestato')
        data['tipologia_edilizia_cod'] = sxp('//ape:datiExtra/ape:tipologiaEdilizia')
        data['piano'] = xs(['//ape:datiGenerali/ape:piano','//ape:datiFabbricato//ape:piano'])

        # Performance
        data['classe_energetica'] = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:classeEnergetica')
        data['epglnren'] = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:epglnren')
        data['epglren'] = sxp('//ape:prestazioneImpianti/ape:epglren')
        data['emissioni_co2'] = sxp('//ape:prestazioneImpianti/ape:emissioniCO2')

        # Services present
        servizi = []
        if sxp('//ape:datiImpianti/ape:climatizzazioneInvernale/ape:impiantoSimulato') is None:
            if sxp('//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:climatizzazioneInvernale') == 'true':
                servizi.append('Heating')
        if sxp('//ape:datiImpianti/ape:produzioneACS/ape:impiantoSimulato') is None:
            if sxp('//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:produzioneAcquaCaldaSanitaria') == 'true':
                servizi.append('DHW')

        for tag, label in [('climatizzazioneEstiva', 'Cooling'),('ventilazioneMeccanica', 'Ventilation'),('illuminazione', 'Lighting'),('trasportoPersoneCose', 'Elevators/Transport')]:
            v = sxp(f'//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:{tag}')
            if v and v.lower() == 'true': servizi.append(label)
        data['servizi_presenti'] = servizi
        
        # Energy Carrier
        consumi_kwh = {}
        for nome, path_xp in VETTORI_XPATHS.items():
            c_str = sxp(path_xp)
            if c_str:
                try:
                    c_val = float(c_str.replace(',', '.'))
                    if nome in VETTORI_PCI: c_val *= VETTORI_PCI[nome]
                    consumi_kwh[nome] = c_val
                except: continue
        data['vettore_energetico_principale'] = sorted(consumi_kwh.items(), key=lambda x: x[1], reverse=True)[0][0] if consumi_kwh else None

        # Catasto
        cat = {'codice_catastale': None, 'foglio': None, 'particella': None, 'subalterno': None}
        node = root.xpath('.//ape:datiCatastali', namespaces=ns)
        if node:
            n = node[0]
            cat['codice_catastale'] = n.xpath('string(ape:codiceCatastale)', namespaces=ns).strip() or None
            cat['foglio'] = n.xpath('string(ape:foglio)', namespaces=ns).strip() or None
            cat['particella'] = n.xpath('string(ape:particella)', namespaces=ns).strip() or None
            
            # Complex subaltern extraction (subDA, subA)
            def _clr_sub(s):
                s = s.strip()
                if not s: return ""
                return s.lstrip('0') or '0'
            
            subDA = _clr_sub(n.xpath('string(.//ape:subalterni/ape:subDA)', namespaces=ns))
            subA = _clr_sub(n.xpath('string(.//ape:subalterni/ape:subA)', namespaces=ns))
            
            if subDA and subA:
                if subDA == subA:
                    cat['subalterno'] = subDA
                else:
                    cat['subalterno'] = f"{subDA},{subA}"
            elif subDA:
                cat['subalterno'] = subDA
            elif subA:
                cat['subalterno'] = subA
        data.update(cat)

        # Building envelope quality
        data['qualita_invernale'] = MAPPING_QUALITA_INVOLUCRO.get(sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:inverno'))
        data['qualita_estiva'] = MAPPING_QUALITA_INVOLUCRO.get(sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:estate'))
        
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
        val_fv = float(sxp(VETTORI_XPATHS['Solare fotovoltaico']) or 0)
        val_st = float(sxp(VETTORI_XPATHS['Solare termico']) or 0)
        data['fonti_rinnovabili'] = 'Yes' if (val_fv > 0 or val_st > 0) else 'No'

        # Improvements
        data['classe_target'] = xs(['//ape:raccomandazioni//ape:classificazioneRaggiungibile/ape:classeEnergetica','//ape:prestazioneGlobale//ape:classeEnergeticaRaggiungibile'])
        data['tempo_ritorno'] = sxp('//ape:raccomandazioni//ape:tempoRitornoInvestimento')

    except Exception as e:
        print(f"Parser Error: {e}")
    return data

# --- PARALLELIZATION WORKER ---

def process_single_xml(fname: str) -> dict:
    """Worker function for parsing a single XML file."""
    # Ensure POI, OMI, and Geocoder globals are initialized in the worker process
    init_amenity_globals()
    init_omi_globals()
    init_geocoder_globals()
    
    try:
        xml_text = _decode_xml(_load_bytes(fname))
        if not xml_text:
            return None
        p = parse_ape_xml(xml_text)
        
        # Original coordinates from XML
        lat_xml = _to_float(p.get("lat"))
        lon_xml = _to_float(p.get("lon"))
        
        res_lat, res_lon = lat_xml, lon_xml
        
        # Coordinate improvement via OSM Geocoder
        if POOL_GEOCODER:
            indirizzo = p.get("indirizzo")
            civico = p.get("civico")
            # Try to geocode if we have an address
            if indirizzo:
                geo_res = POOL_GEOCODER.geocode(street=indirizzo, number=civico, city=TARGET_CITY)
                # If we find a high-quality match or if XML has no coordinates, use OSM
                if geo_res and (geo_res['score'] >= 450 or lat_xml is None or lat_xml == 0):
                    res_lat = geo_res['lat']
                    res_lon = geo_res['lon']

        unita = p.get("subalterno") or os.path.splitext(os.path.basename(fname))[0]
        res = {
            "lista_file_ape": os.path.basename(fname),
            "codice_comune": p.get("codice_catastale"),
            "foglio": p.get("foglio"),
            "particella": p.get("particella"),
            "subalterno": p.get("subalterno"),
            "superficie_di_riferimento_mq": _to_float(p.get("superficie")),
            "indirizzo": p.get("indirizzo"),
            "numero_civico": p.get("civico"),
            "latitudine": res_lat,
            "longitudine": res_lon,
            "zona_omi": get_omi_zone(res_lat, res_lon),
            "tipologia_bene_immobile": p.get("tipologia_bene_immobile"),
            "epoca_costruzione": p.get("anno_costruzione"),
            "data_decorrenza": _parse_date(p.get("data_emissione")),
            "classe_energetica_ape": p.get("classe_energetica"),
            "epglnren_ape": _to_float(p.get("epglnren")),
            "epglren_ape": _to_float(p.get("epglren")),
            "emissioni_co2": _to_float(p.get("emissioni_co2")),
            "serv_risc": "Heating" in (p.get("servizi_presenti") or []),
            "serv_acs": "DHW" in (p.get("servizi_presenti") or []),
            "piano": p.get("piano"),
            "qualita_invernale": p.get("qualita_invernale"),
            "qualita_estiva": p.get("qualita_estiva"),
            "fonti_rinnovabili": p.get("fonti_rinnovabili"),
            "imp_risc_anno": p.get('impianti', {}).get('Heating', {}).get('anno'),
            "imp_risc_tipo": p.get('impianti', {}).get('Heating', {}).get('tecnologia'),
            "imp_acs_anno": p.get('impianti', {}).get('DHW', {}).get('anno'),
            "imp_acs_tipo": p.get('impianti', {}).get('DHW', {}).get('tecnologia'),
            "classe_target_ape": p.get("classe_target"),
            "intervento_payback": _to_float(p.get("tempo_ritorno")),
            # internal helper for stability
            "_unita": str(unita)
        }
        
        # Aggiunta Score Amenity
        scores = get_amenity_scores(res.get("latitudine"), res.get("longitudine"))
        res.update(scores)

        # Add Energy Scores
        res["ape_score_classe"] = map_classe_score(res["classe_energetica_ape"])
        res["ape_score_impianto"] = map_impianto_score(res["imp_risc_tipo"])
        res["ape_score_involucro"] = map_involucro_score(res["qualita_invernale"])
        res["ape_score_rinnovabili"] = map_rinnovabili_score(res["fonti_rinnovabili"])
        res["ape_score_total"] = (res["ape_score_classe"] + res["ape_score_impianto"] + 
                                  res["ape_score_involucro"] + res["ape_score_rinnovabili"])
        
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
                if res.get('codice_comune') == TARGET_COMUNE_CODE:
                    all_rows.append(res)

    return pd.DataFrame(all_rows)

def improve_df_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Improves DataFrame coordinates via local OSM geocoding."""
    if df.empty or 'indirizzo' not in df.columns:
        return df
    
    print("Starting coordinate improvement (post-processing)...")
    init_geocoder_globals()
    if not POOL_GEOCODER:
        print("Skipping geocoding: OSM file not found.")
        return df

    # Identify unique addresses to reduce load
    unique_addr = df[['indirizzo', 'numero_civico']].drop_duplicates()
    
    # Serial geocoding for stability
    def _geo_worker(row):
        ind = row['indirizzo']
        civ = row['numero_civico']
        if not ind: return None
        res = POOL_GEOCODER.geocode(street=ind, number=civ, city=TARGET_CITY)
        if res:
            # Pre-calculate OMI and Amenity for unique address (optimization)
            new_lat, new_lon = res['lat'], res['lon']
            return {
                'indirizzo': ind, 'numero_civico': civ, 
                'lat_osm': new_lat, 'lon_osm': new_lon, 'score': res['score'],
                'zona_omi': get_omi_zone(new_lat, new_lon),
                'amenities': get_amenity_scores(new_lat, new_lon)
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
            geo_map[(r['indirizzo'], r['numero_civico'])] = r
    
    # Update DataFrame with stats
    stats = {"updated": 0, "missing_filled": 0}

    def _update_row(row):
        key = (row['indirizzo'], row['numero_civico'])
        lat_xml = row.get('latitudine')
        lon_xml = row.get('longitudine')
        
        if key in geo_map:
            match = geo_map[key]
            is_missing = lat_xml is None or lat_xml == 0 or (isinstance(lat_xml, float) and np.isnan(lat_xml))
            
            if match['score'] >= 450 or is_missing:
                if is_missing or (abs(lat_xml - match['lat_osm']) > 1e-6 or abs(lon_xml - match['lon_osm']) > 1e-6):
                    row['latitudine'] = match['lat_osm']
                    row['longitudine'] = match['lon_osm']
                    row['zona_omi'] = match['zona_omi']
                    row.update(match['amenities'])
                    
                    stats["updated"] += 1
                    if is_missing:
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
    output_file = "backend/data/FOLDER_META/immobili_with_meta_and_ape_full_cleaned.parquet"
    
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

    # Coordinate improvement step (post-processing required)
    if not df.empty:
        df = improve_df_coordinates(df)

    if not df.empty:
        # Final global sorting (filter already applied during parsing)
        print("Final sorting and cleaning...")
        if 'data_decorrenza' in df.columns:
            df = df.dropna(subset=['data_decorrenza'])
            df['data_decorrenza'] = pd.to_datetime(df['data_decorrenza'])
            
        sort_cols = []
        sort_asc = []
        if '_unita' in df.columns: 
            sort_cols.append('_unita'); sort_asc.append(True)
        if 'data_decorrenza' in df.columns: 
            sort_cols.append('data_decorrenza'); sort_asc.append(False)
        
        if sort_cols:
            df = df.sort_values(sort_cols, ascending=sort_asc).reset_index(drop=True)
        
        # Amenity Score Normalization (0-100 percentile)
        amenity_cols = ['commercial', 'education', 'mobility', 'healthcare', 'sport', 'green']
        print("Normalizing amenity scores (0-100 percentile)...")
        for col in amenity_cols:
            if col in df.columns:
                # Transform raw score to 0-100 percentile
                df[col] = df[col].rank(pct=True) * 100
                df[col] = df[col].round(2)


        
        # Convert cadastral columns to int
        for col in ['foglio', 'particella', 'subalterno']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        # 1. Removal of rows without OMI zone
        if 'zona_omi' in df.columns:
            df = df.dropna(subset=['zona_omi'])
            df = df[df['zona_omi'] != ""]

        # 2. Filtering for unique cadastral unit (Deduplication)
        # For each unit (foglio/part/sub), we only take the most recent APE
        # Since the df is already sorted by descending date, we keep the first row of each group.
        catasto_cols = ['foglio', 'particella', 'subalterno']
        if all(c in df.columns for c in catasto_cols):
            print("Deduplicating cadastral units (keeping most recent APE and main address)...")
            # Filter first by address consistent with the most recent (as previously requested)
            if 'indirizzo' in df.columns:
                df_first_addr = df.groupby(catasto_cols)['indirizzo'].transform('first')
                df = df[df['indirizzo'] == df_first_addr]
            
            # Filter by most recent date (taking the head of each group)
            df = df.sort_values(catasto_cols + ['data_decorrenza'], ascending=[True, True, True, False])
            df = df.groupby(catasto_cols).head(1).reset_index(drop=True)

        if '_unita' in df.columns:
            df = df.drop(columns=['_unita'])

        # Removal of technical/intermediate columns as requested
        cols_to_drop = [
            'imp_acs_tipo', 'imp_acs_anno', 'imp_risc_tipo', 'imp_risc_anno', 
            'fonti_rinnovabili', 'qualita_estiva', 'qualita_invernale', 
            'piano', 'serv_acs', 'serv_risc', 'intervento_payback'
        ]
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
            
        # Initialize extra columns and IDs for normal rows (necessary before metaimmobili generation)
        df = df.reset_index(drop=True)
        df['id'] = (df.index + 1).astype(str)
        df['meta_immobile'] = False
        df['numero_immobili_per_catasto'] = 1
        df['id_list'] = None
        
        # Handle XML file columns (list as string format for compatibility)
        df['lista_file_ape'] = df['lista_file_ape'].apply(lambda x: str([x]) if isinstance(x, str) else "[]")
        df['list_file_ape_filtered'] = df['lista_file_ape']
        df['list_file_ape_filtered_parsed'] = df['lista_file_ape']

        # Metaimmobili generation (aggregation by foglio/particella)
        print("Generating metaimmobili (aggregating by foglio/particella)...")
        meta_rows = []
        for (foglio, particella), group in df.groupby(['foglio', 'particella']):
            if len(group) > 1:
                # 1. Sum surfaces
                total_surf = group['superficie_di_riferimento_mq'].sum()
                
                # 2. Most represented typology by sum of surfaces
                surf_by_tipo = group.groupby('tipologia_bene_immobile')['superficie_di_riferimento_mq'].sum()
                if not surf_by_tipo.empty:
                    chosen_tipo = surf_by_tipo.idxmax()
                    
                    # Extraction and conversion of original IDs for id_list
                    orig_ids = group['id'].astype(int).tolist()
                    
                    # XML file aggregation (union of all group lists)
                    import ast
                    all_xml_files = []
                    for xml_str in group['lista_file_ape']:
                        try:
                            # Converts list string to real list
                            all_xml_files.extend(ast.literal_eval(xml_str))
                        except:
                            continue
                    all_xml_files = sorted(list(set(all_xml_files)))
                    

                    meta_row = {
                        'foglio': foglio,
                        'particella': particella,
                        'subalterno': 0, # Conventional value for metaimmobile
                        'superficie_di_riferimento_mq': total_surf,
                        'tipologia_bene_immobile': chosen_tipo,
                        'id': f"M{len(meta_rows) + 1:05d}",
                        'meta_immobile': True,
                        'numero_immobili_per_catasto': len(group),
                        'id_list': str(orig_ids),
                        'lista_file_ape': str(all_xml_files),
                        'list_file_ape_filtered': str(all_xml_files),
                        'list_file_ape_filtered_parsed': str(all_xml_files)
                    }

                    # Specific aggregations independent of typology/surface
                    # 1. Building epoch: most frequent in group
                    m_epoca = group['epoca_costruzione'].mode()
                    meta_row['epoca_costruzione'] = m_epoca.iloc[0] if not m_epoca.empty else None

                    # 2. Energy class most represented by sum of surfaces
                    surf_by_classe = group.groupby('classe_energetica_ape')['superficie_di_riferimento_mq'].sum()
                    if not surf_by_classe.empty:
                        meta_row['classe_energetica_ape'] = surf_by_classe.idxmax()
                    else:
                        meta_row['classe_energetica_ape'] = None

                    # 3. Energy scores: group maximums (excluding total and class which we recalculate)
                    score_cols = [c for c in group.columns if 'score' in c and c not in ['ape_score_total', 'ape_score_classe']]
                    for col in score_cols:
                        meta_row[col] = group[col].max()
                    
                    # Class score recalculation based on chosen class
                    meta_row['ape_score_classe'] = map_classe_score(meta_row['classe_energetica_ape'])
                    
                    # Recalculate total as sum of individual scores
                    meta_row['ape_score_total'] = (
                        (meta_row.get('ape_score_classe') or 0) + 
                        (meta_row.get('ape_score_impianto') or 0) + 
                        (meta_row.get('ape_score_involucro') or 0) + 
                        (meta_row.get('ape_score_rinnovabili') or 0)
                    )

                    # 4. Consumptions: group minimums
                    consumo_cols = ['epglnren_ape', 'epglren_ape', 'emissioni_co2']
                    for col in consumo_cols:
                        if col in group.columns:
                            meta_row[col] = group[col].min()

                    # 5. Other properties: group mode (no longer from type-filtered sub_group)
                    for col in df.columns:
                        if col not in meta_row:
                            m = group[col].mode()
                            meta_row[col] = m.iloc[0] if not m.empty else None
                    
                    meta_rows.append(meta_row)

        # Add metaimmobili at the end of the file
        if meta_rows:
            df = pd.concat([df, pd.DataFrame(meta_rows)], ignore_index=True)

        # Reorder columns: id, meta_immobile, numero_immobili_per_catasto, id_list and file list first
        first_cols = [
            'id', 'meta_immobile', 'numero_immobili_per_catasto', 'id_list',
            'lista_file_ape', 'list_file_ape_filtered', 'list_file_ape_filtered_parsed'
        ]
        cols = first_cols + [c for c in df.columns if c not in first_cols]
        df = df[cols]
            
        # Final save with sorted data in Parquet format
        df.to_parquet(output_file, index=False)
        print(f"DataFrame saved to {output_file}. Final row count: {len(df)}")