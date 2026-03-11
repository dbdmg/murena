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

# --- CONFIGURAZIONE ---
PATH_XML = "/home/mdeluca/merged"

# --- COSTANTI E MAPPING ---

MAPPING_QUALITA_INVOLUCRO = {
    '0': 'Sorridente',
    '1': 'Basita/o',
    '2': 'Triste'
}

MAPPING_DPR412 = {
    '0': 'Abitazioni adibite a residenza con carattere continuativo',
    '1': 'Collegi, luoghi di ricovero, case di pena, caserme, conventi',
    '2': 'Abitazioni adibite a residenza con occupazione saltuaria',
    '3': 'Edifici adibiti ad albergo, pensione ed attività similari',
    '4': 'Uffici e assimilabili',
    '5': 'Ospedali, cliniche, case di cura e assimilabili',
    '6': 'Cinema e teatri, sale di riunione per congressi e assimilabili',
    '7': 'Mostre, musei e biblioteche, luoghi di culto e assimilabili',
    '8': 'Bar, ristoranti, sale da ballo e assimilabili',
    '9': 'Attività commerciali e assimilabili',
    '10': 'Piscine, saune e assimilabili',
    '11': 'Palestre e assimilabili',
    '12': 'Servizi di supporto alle attività sportive',
    '13': 'Attività scolastiche',
    '14': 'Attività industriali, artigianali e assimilabili'
}

MAPPING_IMPIANTI = {
    '0': 'Caldaia standard',
    '1': 'Caldaia a condensazione',
    '2': 'Stufa o caminetto',
    '3': 'Riscaldamento elettrico',
    '4': 'Pompa di calore', '5': 'Pompa di calore', '6': 'Pompa di calore', '7': 'Pompa di calore',
    '8': 'Pompa di calore', '9': 'Pompa di calore', '10': 'Pompa di calore', '11': 'Pompa di calore',
    '12': 'Pompa di calore', '13': 'Pompa di calore', '14': 'Pompa di calore', '15': 'Pompa di calore',
    '16': 'Impianto solare termico',
    '17': 'Impianto fotovoltaico',
    '18': 'Cogeneratore',
    '19': 'Teleriscaldamento',
    '32': 'Scalda-acqua a gas',
    '33': 'Scalda-acqua a gas',
    '34': 'Scalda-acqua a pompa di calore',
    '35': 'Scalda-acqua a pompa di calore',
    '36': 'Boiler elettrico'
}

# --- GEODATABASE LOCALE (OSM) ---

class OSMGeocodingService:
    """
    Servizio di geocodifica locale basato su file OSM PBF.
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
        Pulisce l'indirizzo in modo aggressivo per estrarre via e civico.
        """
        raw = str(street).strip().upper()
        
        # 1. Rimuove prefissi spazzatura (es. ": ", "10128 TORINO - ", "374 ")
        # Rimuove CAP a inizio stringa (5 cifre)
        raw = re.sub(r'^\d{5}\s+', '', raw)
        # Rimuove "TORINO" o "TO" all'inizio o fine se presenti
        raw = re.sub(r'^(TORINO|TO)\s*-?\s*', '', raw)
        raw = re.sub(r'\s*-?\s*(TORINO|TO)$', '', raw)
        # Rimuove numeri casuali a inizio stringa (spesso spazzatura da export)
        raw = re.sub(r'^\d+\s+', '', raw)
        # Rimuove punteggiatura all'inizio
        raw = raw.lstrip(':-,. ')

        # 2. Normalizzazione tipi di via comuni
        # Corso
        raw = re.sub(r'^(C\.?SO|C/S|C\s+SO|CORS|COROS)\b', 'CORSO', raw)
        # Via
        raw = re.sub(r'^(V\.?IA|V/A|V\s+IA)\b', 'VIA', raw)
        # Piazza
        raw = re.sub(r'^(P\.?ZZA|P/Z)\b', 'PIAZZA', raw)

        # 3. Estrazione civico se non fornito o se incorporato
        final_num = str(number).strip().lower() if number and str(number).lower() != 'snc' else None
        
        # Se il civico è nella stringa (es. "CORSO TRAPANI, 133" o "VIA ROMA 10")
        match = re.search(r'(?:[ ,]|CIVICO|N\.?)\s*(\d+[A-Z\s/-]*)$', raw, re.IGNORECASE)
        if match:
            if not final_num:
                final_num = match.group(1).strip().lower()
            street_clean = raw[:match.start()].strip(', ')
        else:
            street_clean = raw

        # Rimuove eventuali città residue dalla via
        if city:
            street_clean = re.sub(rf'\b{re.escape(city.upper())}\b', '', street_clean).strip(' ,-')

        return street_clean.lower(), final_num

    def geocode(self, street: str, number: Optional[str] = None, city: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Converte un indirizzo sporco in coordinate lat/lon.
        """
        if not street: return None
        
        street_clean, final_number = self._clean_address(street, number, city)
        city_clean = city.strip().lower() if city else "torino"

        if len(street_clean) < 3: # Troppo corto per essere una via valida
            return None

        # 2. Query candidati su DuckDB
        # Cerchiamo sia con LIKE (più lento ma flessibile) che con uguaglianza
        query = "SELECT lat, lon, street, house_number, city FROM addresses WHERE street LIKE ?"
        params = [f"%{street_clean}%"]
        
        if city_clean:
            query += " AND city LIKE ?"
            params.append(f"%{city_clean}%")
        
        query += " LIMIT 60"
        
        candidates = self.conn.execute(query, params).fetchall()
        if not candidates:
            # Riprova senza tipo di via (es. da "CORSO TRAPANI" a "TRAPANI")
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
            # Città (100)
            if city_clean == res['city']: res['score'] += 100
            
            # Via (Max 150)
            target_street = res['street'] or ""
            if street_clean == target_street: res['score'] += 150
            elif street_clean in target_street or target_street in street_clean: res['score'] += 50
            
            # Civico (Max 300)
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

# --- FUNZIONI DI SCORING ---

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

# --- CONFIGURAZIONE AMENITY ---
EARTH_RADIUS_KM = 6371.0
MAX_DISTANCE_M = 5000
SERVICE_BASE = {'breve': 0.340, 'medio': 0.680, 'lungo': 1.360}
URBAN_MULTIPLIER = {'B': 1.0, 'C': 1.5, 'D': 2.5, 'E': 4.0}
DEFAULT_ZONE = 'C'

# Mapping Amenity -> Threshold Class (Breve/Medio/Lungo)
BREVE = ["pharmacy", "defibrillator", "bus_stop", "tram_stop", "bicycle_parking", "taxi", "subway_entrance", "charging_station", "playground", "garden", "grass", "park", "fitness_centre", "pitch", "supermarket", "bakery", "greengrocer", "newsagent", "kiosk", "convenience", "tobacco", "laundry", "hairdresser", "butcher", "pastry", "ice_cream", "deli", "stationery", "grocery", "vending_machine", "kindergarten", "school", "community_centre"]
MEDIO = ["doctor", "dentist", "clinic", "physiotherapist", "veterinary", "optometrist", "psychotherapist", "physiotherapist-osteopathy", "alternative", "parking", "bicycle_rental", "car_sharing", "recreation_ground", "scrub", "swimming_pool", "sports_centre", "bowling_alley", "clothes", "shoes", "florist", "hardware", "chemist", "pet", "books", "gift", "optician", "beauty", "mobile_phone", "jewelry", "toys", "electronics", "bicycle", "travel_agency", "dry_cleaning", "photo", "video", "confectionery", "alcohol", "wine", "cheese", "dairy", "seafood", "pasta", "spices", "tea", "coffee", "coffee_roasting", "herbalist", "tattoo", "massage", "spa", "copyshop", "shoe_repair", "tailor", "sewing", "fabric", "bag", "fashion_accessories", "cosmetics", "variety_store", "second_hand", "video_games", "sports", "nutrition_supplements", "perfumery", "watches", "baby_goods", "houseware", "repair", "mobile_phone_accessories", "party", "religion", "locksmith", "art", "frame", "ticket", "food", "general", "pet_grooming", "library", "music_school", "driving_school"]

AMENITY_TO_CLASS = {a: 'breve' for a in BREVE}
AMENITY_TO_CLASS.update({a: 'medio' for a in MEDIO})

# Globali per OMI
POOL_OMI_GDF = None

def init_omi_globals():
    global POOL_OMI_GDF
    if POOL_OMI_GDF is not None or gpd is None: return
    
    omi_path = "/home/mdeluca/real-estate-ai/backend/data/FOLDER_STATIC_ROME/Zone_omi_torino.geojson"
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
    """Trova la zona OMI (CODZONA) per il punto lat, lon."""
    if POOL_OMI_GDF is None or lat is None or lon is None or Point is None:
        return None
    
    try:
        p = Point(lon, lat)
        # Filtro spaziale rapido usando sindex se presente, altrimenti iterazione
        # Dato che le zone sono poche (circa 50-100), iterate è molto veloce
        for _, row in POOL_OMI_GDF.iterrows():
            if row.geometry.contains(p):
                return row.get('CODZONA')
    except Exception:
        pass
    return None

# Globali per Amenity (Inizializzati nel main o nel worker)
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
    """Calcola gli score per le 6 categorie per un punto lat/lon."""
    if POOL_POI_TREE is None or lat is None or lon is None:
        return {cat: 0.0 for cat in ['commerciale', 'educazione', 'mobilita', 'sanita', 'sport', 'verde']}
    
    U = URBAN_MULTIPLIER[DEFAULT_ZONE]
    max_dist_rad = MAX_DISTANCE_M / 1000 / EARTH_RADIUS_KM
    
    query_point = np.array([[np.radians(lat), np.radians(lon)]])
    indices, distances = POOL_POI_TREE.query_radius(query_point, r=max_dist_rad, return_distance=True)
    
    # Inizializza accumulatore: [category_idx][amenity_idx] = sum_scores
    cat_amenity_scores = [[0.0 for _ in a_list] for a_list in POOL_CAT_AMENITIES]
    
    if len(indices[0]) > 0:
        dist_km = distances[0] * EARTH_RADIUS_KM
        for i, poi_idx in enumerate(indices[0]):
            c_idx, a_idx, S = POOL_POI_META[poi_idx]
            x = dist_km[i]
            # Formula: f(x) = e^(-(x / (S * U))^3)
            score = np.exp(-((x / (S * U)) ** 3))
            cat_amenity_scores[c_idx][a_idx] += score
    
    # Media per categoria
    final_scores = {}
    for i, cat_name in enumerate(POOL_CATEGORIES):
        scores = cat_amenity_scores[i]
        if not scores: # Se la categoria non ha amenità (strano)
            final_scores[cat_name] = 0.0
        else:
            final_scores[cat_name] = sum(scores) / len(scores)
            
    return final_scores

# --- FUNZIONI HELPER INTERNE ---

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
    
    # Ripulisci eventuale "spazzatura" prima della dichiarazione XML
    text = re.sub(r'^.*?<\?xml', '<?xml', text, flags=re.DOTALL)
    
    # Rimuovi caratteri XML non validi (come #x65535/0xFFFF)
    # Range validi XML 1.0: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
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

        # Dati generali
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

        # Prestazioni
        data['classe_energetica'] = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:classeEnergetica')
        data['epglnren'] = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:epglnren')
        data['epglren'] = sxp('//ape:prestazioneImpianti/ape:epglren')
        data['emissioni_co2'] = sxp('//ape:prestazioneImpianti/ape:emissioniCO2')

        # Servizi presenti
        servizi = []
        if sxp('//ape:datiImpianti/ape:climatizzazioneInvernale/ape:impiantoSimulato') is None:
            if sxp('//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:climatizzazioneInvernale') == 'true':
                servizi.append('Riscaldamento')
        if sxp('//ape:datiImpianti/ape:produzioneACS/ape:impiantoSimulato') is None:
            if sxp('//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:produzioneAcquaCaldaSanitaria') == 'true':
                servizi.append('ACS')

        for tag, label in [('climatizzazioneEstiva', 'Raffrescamento'),('ventilazioneMeccanica', 'Ventilazione'),('illuminazione', 'Illuminazione'),('trasportoPersoneCose', 'Ascensori/Trasporto')]:
            v = sxp(f'//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:{tag}')
            if v and v.lower() == 'true': servizi.append(label)
        data['servizi_presenti'] = servizi
        
        # Vettore Energetico
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
            
            # Estrazione subalterno complessa (subDA, subA)
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

        # Qualità involucro
        data['qualita_invernale'] = MAPPING_QUALITA_INVOLUCRO.get(sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:inverno'))
        data['qualita_estiva'] = MAPPING_QUALITA_INVOLUCRO.get(sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:estate'))
        
        # Impianti
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
            'Riscaldamento': get_inf(['//ape:datiImpianti//ape:climatizzazioneInvernale','//ape:impianti//ape:impiantoClimatizzazioneInvernale']),
            'ACS': get_inf(['//ape:datiImpianti//ape:produzioneACS','//ape:impianti//ape:impiantoAcquaCaldaSanitaria'])
        }

        # Fonti Rinnovabili
        val_fv = float(sxp(VETTORI_XPATHS['Solare fotovoltaico']) or 0)
        val_st = float(sxp(VETTORI_XPATHS['Solare termico']) or 0)
        data['fonti_rinnovabili'] = 'Sì' if (val_fv > 0 or val_st > 0) else 'No'

        # Miglioramenti
        data['classe_target'] = xs(['//ape:raccomandazioni//ape:classificazioneRaggiungibile/ape:classeEnergetica','//ape:prestazioneGlobale//ape:classeEnergeticaRaggiungibile'])
        data['tempo_ritorno'] = sxp('//ape:raccomandazioni//ape:tempoRitornoInvestimento')

    except Exception as e:
        print(f"Parser Error: {e}")
    return data

# --- WORKER PER PARALLELIZZAZIONE ---

def process_single_xml(fname: str) -> dict:
    """Funzione worker per il parsing di un singolo file XML."""
    # Assicura caricamento POI, OMI e Geocoder nel processo worker
    init_amenity_globals()
    init_omi_globals()
    init_geocoder_globals()
    
    try:
        xml_text = _decode_xml(_load_bytes(fname))
        if not xml_text:
            return None
        p = parse_ape_xml(xml_text)
        
        # Coordinate originali dall'XML
        lat_xml = _to_float(p.get("lat"))
        lon_xml = _to_float(p.get("lon"))
        
        res_lat, res_lon = lat_xml, lon_xml
        
        # Miglioramento coordinate tramite OSM Geocoder
        if POOL_GEOCODER:
            indirizzo = p.get("indirizzo")
            civico = p.get("civico")
            # Cerchiamo di geocodificare se abbiamo un indirizzo
            if indirizzo:
                geo_res = POOL_GEOCODER.geocode(street=indirizzo, number=civico, city="Torino")
                # Se troviamo un match di alta qualità o se l'XML non ha coordinate, usiamo OSM
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
            "serv_risc": "Riscaldamento" in (p.get("servizi_presenti") or []),
            "serv_acs": "ACS" in (p.get("servizi_presenti") or []),
            "piano": p.get("piano"),
            "qualita_invernale": p.get("qualita_invernale"),
            "qualita_estiva": p.get("qualita_estiva"),
            "fonti_rinnovabili": p.get("fonti_rinnovabili"),
            "imp_risc_anno": p.get('impianti', {}).get('Riscaldamento', {}).get('anno'),
            "imp_risc_tipo": p.get('impianti', {}).get('Riscaldamento', {}).get('tecnologia'),
            "imp_acs_anno": p.get('impianti', {}).get('ACS', {}).get('anno'),
            "imp_acs_tipo": p.get('impianti', {}).get('ACS', {}).get('tecnologia'),
            "classe_target_ape": p.get("classe_target"),
            "intervento_payback": _to_float(p.get("tempo_ritorno")),
            # internal helper for stability
            "_unita": str(unita)
        }
        
        # Aggiunta Score Amenity
        scores = get_amenity_scores(res.get("latitudine"), res.get("longitudine"))
        res.update(scores)

        # Aggiunta Score Energetici
        res["ape_score_classe"] = map_classe_score(res["classe_energetica_ape"])
        res["ape_score_impianto"] = map_impianto_score(res["imp_risc_tipo"])
        res["ape_score_involucro"] = map_involucro_score(res["qualita_invernale"])
        res["ape_score_rinnovabili"] = map_rinnovabili_score(res["fonti_rinnovabili"])
        res["ape_score_total"] = (res["ape_score_classe"] + res["ape_score_impianto"] + 
                                  res["ape_score_involucro"] + res["ape_score_rinnovabili"])
        
        return res
    except Exception as e:
        print(f"Errore parsing {fname}: {type(e).__name__}: {e}")
        return None

# --- DATA LOADING ---

from concurrent.futures import ProcessPoolExecutor

def _load_ape_df(file_list: List[str]) -> pd.DataFrame:
    """Carica i dati XML, li filtra per L219 e restituisce il DataFrame."""
    all_rows = []

    with ProcessPoolExecutor() as executor:
        # Usiamo generator per processare i risultati man mano che arrivano
        results_gen = tqdm(
            executor.map(process_single_xml, file_list),
            total=len(file_list),
            desc="Processing XML files (Parallel)",
            mininterval=1.0
        )
        
        for res in results_gen:
            if res is not None:
                # Applichiamo il filtro L219 immediatamente per minimizzare la memoria occupata
                if res.get('codice_comune') == 'L219':
                    all_rows.append(res)

    return pd.DataFrame(all_rows)

def improve_df_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Migliora le coordinate del DataFrame tramite geocoding locale OSM."""
    if df.empty or 'indirizzo' not in df.columns:
        return df
    
    print("Avvio miglioramento coordinate (post-processing)...")
    init_geocoder_globals()
    if not POOL_GEOCODER:
        print("Salto geocoding: file OSM non trovato.")
        return df

    # Identifica indirizzi unici per ridurre il carico
    unique_addr = df[['indirizzo', 'numero_civico']].drop_duplicates()
    
    # Geocodifica seriale per stabilità
    def _geo_worker(row):
        ind = row['indirizzo']
        civ = row['numero_civico']
        if not ind: return None
        res = POOL_GEOCODER.geocode(street=ind, number=civ, city="Torino")
        if res:
            # Pre-calcoliamo OMI e Amenity per l'indirizzo unico (ottimizzazione)
            new_lat, new_lon = res['lat'], res['lon']
            return {
                'indirizzo': ind, 'numero_civico': civ, 
                'lat_osm': new_lat, 'lon_osm': new_lon, 'score': res['score'],
                'zona_omi': get_omi_zone(new_lat, new_lon),
                'amenities': get_amenity_scores(new_lat, new_lon)
            }
        return None

    print(f"Geocodifica di {len(unique_addr)} indirizzi unici...")
    geo_results = []
    for _, row in tqdm(unique_addr.iterrows(), total=len(unique_addr), desc="Geocoding"):
        geo_results.append(_geo_worker(row))
    
    # Mappatura risultati
    geo_map = {}
    for r in geo_results:
        if r:
            geo_map[(r['indirizzo'], r['numero_civico'])] = r
    
    # Aggiornamento DataFrame con statistiche
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

    # Applica l'aggiornamento
    print("Applicazione nuove coordinate al DataFrame...")
    df = df.apply(_update_row, axis=1)

    print(f"\n--- STATISTICHE GEOCODING ---")
    print(f"Righe processate: {len(df)}")
    print(f"Righe aggiornate (OSM): {stats['updated']} ({stats['updated']/len(df)*100:.1f}%)")
    print(f"Coordinate mancanti recuperate: {stats['missing_filled']}")
    print(f"-----------------------------\n")
    
    return df

if __name__ == "__main__":
    output_file = "backend/data/FOLDER_META/immobili_with_meta_and_ape_full_cleaned.parquet"
    
    # Se il file esiste già, lo carichiamo direttamente senza riprocessare gli XML
    if os.path.exists(output_file):
        print(f"File {output_file} trovato. Caricamento in corso...")
        df = pd.read_parquet(output_file)
    else:
        # Pre-installazione estensione spatial di DuckDB per evitare race condition nei worker
        try:
            duckdb.connect().execute("INSTALL spatial;")
        except Exception:
            pass
            
        files = [os.path.basename(f) for f in glob.glob(os.path.join(PATH_XML, "*.xml"))]
        if files:
            df = _load_ape_df(files)
            print(f"\nProcessati {len(files)} file XML.")
        else:
            print("Nessun file XML trovato.")
            df = pd.DataFrame()

    # Step di miglioramento coordinate (post-processing richiesto)
    if not df.empty:
        df = improve_df_coordinates(df)

    if not df.empty:
        # Ordinamento globale finale (il filtro L219 è già stato applicato nel parsing)
        print("Ordinamento finale e pulizia...")
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
        
        # Normalizzazione Amenity Score (0-100 percentile)
        amenity_cols = ['commerciale', 'educazione', 'mobilita', 'sanita', 'sport', 'verde']
        print("Normalizzazione amenity scores (0-100 percentile)...")
        for col in amenity_cols:
            if col in df.columns:
                # Trasforma lo score grezzo in percentile 0-100
                df[col] = df[col].rank(pct=True) * 100
                df[col] = df[col].round(2)


        
        # Conversione colonne catastali in int
        for col in ['foglio', 'particella', 'subalterno']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        # 1. Rimozione righe senza zona OMI
        if 'zona_omi' in df.columns:
            df = df.dropna(subset=['zona_omi'])
            df = df[df['zona_omi'] != ""]

        # 2. Filtraggio per unità catastale univoca (Deduplicazione)
        # Per ogni unità (foglio/part/sub), prendiamo solo l'APE più recente
        # Poiché il df è già ordinato per data decrescente, manteniamo la prima riga di ogni gruppo.
        catasto_cols = ['foglio', 'particella', 'subalterno']
        if all(c in df.columns for c in catasto_cols):
            print("Deduplicazione unità catastali (mantengo APE più recente e indirizzo principale)...")
            # Filtriamo prima per indirizzo coerente con il più recente (come richiesto prima)
            if 'indirizzo' in df.columns:
                df_first_addr = df.groupby(catasto_cols)['indirizzo'].transform('first')
                df = df[df['indirizzo'] == df_first_addr]
            
            # Filtriamo per data più recente (prendiamo la testa di ogni gruppo)
            df = df.sort_values(catasto_cols + ['data_decorrenza'], ascending=[True, True, True, False])
            df = df.groupby(catasto_cols).head(1).reset_index(drop=True)

        if '_unita' in df.columns:
            df = df.drop(columns=['_unita'])

        # Rimozione colonne tecniche/intermedie come richiesto
        cols_to_drop = [
            'imp_acs_tipo', 'imp_acs_anno', 'imp_risc_tipo', 'imp_risc_anno', 
            'fonti_rinnovabili', 'qualita_estiva', 'qualita_invernale', 
            'piano', 'serv_acs', 'serv_risc', 'intervento_payback'
        ]
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
            
        # Inizializza colonne extra e ID per righe normali (necessario prima della generazione metaimmobili)
        df = df.reset_index(drop=True)
        df['id'] = (df.index + 1).astype(str)
        df['meta_immobile'] = False
        df['numero_immobili_per_catasto'] = 1
        df['id_list'] = None
        
        # Gestione colonne file XML (formato lista come stringa per compatibilità)
        df['lista_file_ape'] = df['lista_file_ape'].apply(lambda x: str([x]) if isinstance(x, str) else "[]")
        df['list_file_ape_filtered'] = df['lista_file_ape']
        df['list_file_ape_filtered_parsed'] = df['lista_file_ape']

        # Generazione metaimmobili (aggregazione per foglio/particella)
        print("Generazione metaimmobili (aggregazione per foglio/particella)...")
        meta_rows = []
        for (foglio, particella), group in df.groupby(['foglio', 'particella']):
            if len(group) > 1:
                # 1. Somma superfici
                total_surf = group['superficie_di_riferimento_mq'].sum()
                
                # 2. Tipologia più rappresentata per somma superfici
                surf_by_tipo = group.groupby('tipologia_bene_immobile')['superficie_di_riferimento_mq'].sum()
                if not surf_by_tipo.empty:
                    chosen_tipo = surf_by_tipo.idxmax()
                    
                    # Estrazione e conversione ID originali per id_list
                    orig_ids = group['id'].astype(int).tolist()
                    
                    # Aggregazione file XML (unione di tutte le liste del gruppo)
                    import ast
                    all_xml_files = []
                    for xml_str in group['lista_file_ape']:
                        try:
                            # Converte la stringa della lista in lista reale
                            all_xml_files.extend(ast.literal_eval(xml_str))
                        except:
                            continue
                    all_xml_files = sorted(list(set(all_xml_files)))
                    

                    meta_row = {
                        'foglio': foglio,
                        'particella': particella,
                        'subalterno': 0, # Valore convenzionale per metaimmobile
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

                    # Definizione aggregazioni specifiche indipendenti da tipologia/superficie
                    # 1. Epoca: la più frequente nel gruppo
                    m_epoca = group['epoca_costruzione'].mode()
                    meta_row['epoca_costruzione'] = m_epoca.iloc[0] if not m_epoca.empty else None

                    # 2. Classe energetica più rappresentata per somma superfici
                    surf_by_classe = group.groupby('classe_energetica_ape')['superficie_di_riferimento_mq'].sum()
                    if not surf_by_classe.empty:
                        meta_row['classe_energetica_ape'] = surf_by_classe.idxmax()
                    else:
                        meta_row['classe_energetica_ape'] = None

                    # 3. Score energetici: i massimi nel gruppo (escluso il totale e la classe che ricalcoliamo)
                    score_cols = [c for c in group.columns if 'score' in c and c not in ['ape_score_total', 'ape_score_classe']]
                    for col in score_cols:
                        meta_row[col] = group[col].max()
                    
                    # Ricalcolo score classe basato sulla classe scelta
                    meta_row['ape_score_classe'] = map_classe_score(meta_row['classe_energetica_ape'])
                    
                    # Recalculate total as sum of individual scores
                    meta_row['ape_score_total'] = (
                        (meta_row.get('ape_score_classe') or 0) + 
                        (meta_row.get('ape_score_impianto') or 0) + 
                        (meta_row.get('ape_score_involucro') or 0) + 
                        (meta_row.get('ape_score_rinnovabili') or 0)
                    )

                    # 4. Consumi: i minimi nel gruppo
                    consumo_cols = ['epglnren_ape', 'epglren_ape', 'emissioni_co2']
                    for col in consumo_cols:
                        if col in group.columns:
                            meta_row[col] = group[col].min()

                    # 5. Altre proprietà: moda del gruppo (non più del sub_group filtrato per tipo)
                    for col in df.columns:
                        if col not in meta_row:
                            m = group[col].mode()
                            meta_row[col] = m.iloc[0] if not m.empty else None
                    
                    meta_rows.append(meta_row)

        # Aggiunta metaimmobili alla fine del file
        if meta_rows:
            df = pd.concat([df, pd.DataFrame(meta_rows)], ignore_index=True)

        # Riordino colonne: id, meta_immobile, numero_immobili_per_catasto, id_list e file list per primi
        first_cols = [
            'id', 'meta_immobile', 'numero_immobili_per_catasto', 'id_list',
            'lista_file_ape', 'list_file_ape_filtered', 'list_file_ape_filtered_parsed'
        ]
        cols = first_cols + [c for c in df.columns if c not in first_cols]
        df = df[cols]
            
        # Salvataggio definitivo con dati ordinati in formato Parquet
        df.to_parquet(output_file, index=False)
        print(f"DataFrame salvato in {output_file}. Numero righe finali: {len(df)}")