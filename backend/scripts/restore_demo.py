
import json
import csv
import os
from pathlib import Path

# Config
EXPORT_FILE = r'C:\Users\tcaci\Documents\GitHub\real-estate-ai\backend\run_exports\20260125_223914_run_1769.json'
DEMO_DIR = r'C:\Users\tcaci\Documents\GitHub\real-estate-ai\backend\data\runs\admin\demo_investitore_estero'

# Ensure demo dir exists
os.makedirs(DEMO_DIR, exist_ok=True)

# Load Export
print(f"Loading export from {EXPORT_FILE}...")
with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 1. gemini_responses.json
print("Creating gemini_responses.json...")
agent_outputs = data.get('agent_outputs', {})
# Add a flag to indicate it's a demo
agent_outputs['_demo'] = {"source": "demo_investitore_estero"}

with open(os.path.join(DEMO_DIR, 'gemini_responses.json'), 'w', encoding='utf-8') as f:
    json.dump(agent_outputs, f, indent=2, ensure_ascii=False)

# 2. metadata.json
print("Creating metadata.json...")
# Extract location data from agent_outputs if available
location_data = []
if 'location_extraction' in agent_outputs and 'places' in agent_outputs['location_extraction']:
    places = agent_outputs['location_extraction']['places']
    # Format: [[name, lat, lon], ...] - adapting to what's expected if possible, or keeping raw if backend handles it
    # Backend expects: location_data (List[List[Any]]) -> [[name, lat, lon], ...]
    # The export might have it in a different format.
    # checking export content from view_file:
    # "places": [{"name": "Torino", "city": "Torino", "lat": null, "lon": null}, ...]
    # we'll map it to list of lists
    for p in places:
        name = p.get('name')
        if p.get('city'):
            name = f"{name}, {p.get('city')}"
        lat = p.get('lat') or 45.0703 # Default to Torino center if null
        lon = p.get('lon') or 7.6869
        location_data.append([name, lat, lon])

metadata = {
    "query": data.get('query', ''),
    "timestamp": data.get('timestamp', ''),
    "results_count": data.get('metrics', {}).get('total_buildings', 0), # fallback
    "location_data": location_data,
    "status_message": "Analysis completed successfully."
}

# If buildings exist in results, update count
# Path in export: full_results -> buildings
buildings = data.get('full_results', {}).get('buildings', [])

if not buildings and 'results' in data: 
    # Fallback to old structure if exists
    buildings = data['results'].get('buildings', [])


metadata['results_count'] = len(buildings)

with open(os.path.join(DEMO_DIR, 'metadata.json'), 'w', encoding='utf-8') as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

# 3. results.csv
print(f"Creating results.csv for {len(buildings)} buildings...")

# Define CSV columns mapping to JSON keys
# CSV Column -> JSON Key (or path)
column_mapping = {
    'id': 'id',
    'latitudine': 'latitudine',
    'longitudine': 'longitudine',
    'indirizzo': 'indirizzo',
    'numero_civico': 'numero_civico',
    'superficie_di_riferimento_mq': 'superficie_di_riferimento_mq',
    'epoca_costruzione': 'epoca_costruzione',
    'classe_energetica_ape': 'classe_energetica_ape',
    'score': 'score',
    'ranking_score': 'ranking_score',
    'tipologia_bene_immobile': 'tipologia_bene_immobile',
    'natura_giuridica_del_bene': 'natura_giuridica_del_bene',
    'vincolo_culturale_paesaggistico': 'vincolo_culturale_paesaggistico',
    'finalita': 'finalita',
    'zona_omi': 'zona_omi',
    'canone_annuale': 'canone_annuale',
    'is_evaluated': 'is_evaluated',
    'meta_immobile': 'meta_immobile',
    'motivazione': 'motivazione',
    # APE Scores (Flat in export)
    'ape_score_total': 'ape_score_total',
    'ape_score_classe': 'ape_score_classe',
    'ape_score_impianto': 'ape_score_impianto',
    'ape_score_involucro': 'ape_score_involucro',
    'ape_score_rinnovabili': 'ape_score_rinnovabili',
    # POI Scores (Flat check)
    'sanita': 'sanita',
    'mobilita': 'mobilita',
    'verde': 'verde',
    'educazione': 'educazione',
    'commerciale': 'commerciale',
    'sport': 'sport',
    # Other
    'lista_file_ape': 'lista_file_ape',
    'list_file_ape_filtered': 'list_file_ape_filtered', 
    'id_list': 'id_list',
    'data_decorrenza': 'data_decorrenza',
    'numero_immobili_per_catasto': 'numero_immobili_per_catasto',
    'tipo_detenzione_a_terzi': 'tipo_detenzione_a_terzi',
    'foglio': 'foglio',
    'particella': 'particella',
    'distanza_km': 'distanza_km'
}

# Helper to get value
def get_val(obj, path):
    # Try flat first (if path is string)
    if isinstance(path, str):
        if path in obj:
            return obj[path]
            
        # Fallback for some specific known aliases if needed, but strict for now
        # Check if maybe it IS nested but we mapped it flat? No, we mapped flat.
        
        # Try some fallbacks for specific fields if missing at root but present in common variations
        if path == 'score' and 'ranking_score' in obj: return obj['ranking_score']
        if path == 'motivazione' and 'description' in obj: return obj['description']
        
        return None

    # Nested path
    if isinstance(path, list):
        cur = obj
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return None
        return cur
    return obj.get(path)

csv_columns = list(column_mapping.keys())

with open(os.path.join(DEMO_DIR, 'results.csv'), 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=csv_columns, delimiter=';', quotechar='"')
    writer.writeheader()
    
    for b in buildings:
        row = {}
        for col, key in column_mapping.items():
            val = get_val(b, key)
            
            # Handle list conversion for CSV
            if isinstance(val, list):
                val = str(val)
            
            # Handle boolean
            if isinstance(val, bool):
                val = str(val).lower()
                
            row[col] = val if val is not None else ''
            
        writer.writerow(row)

print("Done!")
