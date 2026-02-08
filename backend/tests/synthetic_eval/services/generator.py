
import random
import json
import shutil
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

from ..config import USE_CASE_CONFIGS, POI_TEMPLATES, ZONE_TORINO

class SyntheticDataGenerator:
    """Generatore di dataset sintetico."""
    
    def __init__(self, num_immobili: int, num_poi_per_category: int, use_case: str, seed: int = 42):
        self.num_immobili = num_immobili
        self.num_poi_per_category = num_poi_per_category
        self.use_case = use_case
        random.seed(seed)
        np.random.seed(seed)
        self.output_dir = Path("synthetic_data")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_coordinate(self, zone: Dict) -> tuple:
        """Genera coordinate casuali in una zona."""
        lat_offset = random.gauss(0, 0.0045)
        lon_offset = random.gauss(0, 0.0065)
        return (zone["lat_center"] + lat_offset, zone["lon_center"] + lon_offset)
    
    def generate_immobile(self, idx: int, config: Dict, zone: Dict) -> Dict:
        """Genera singolo immobile con colonne già rinominate per compatibilità."""
        lat, lon = self.generate_coordinate(zone)
        superficie = random.randint(*config["superficie_range"])
        prezzo_mq = random.randint(*config["prezzo_mq_range"])
        classe_energetica = random.choice(config["ape_classes"])
        
        # Genera valori APE dettagliati basati sulla classe energetica
        ape_data = self._generate_ape_data(classe_energetica)
        
        immobile = {
            "id": f"IMM{idx:03d}",
            "tipologia_bene_immobile": random.choice(config["preferred_typologies"]),
            "superficie_di_riferimento_mq": superficie,
            "prezzo": superficie * prezzo_mq,
            "prezzo_mq": prezzo_mq,
            "piano": random.randint(*config["piano_range"]),
            "numero_locali": random.randint(*config["locali_range"]),
            "latitudine": lat,
            "longitudine": lon,
            "zona_omi": zone["name"],
            "classe_energetica": classe_energetica,
            "anno_costruzione": random.randint(1970, 2023),
            "utilizzo_del_bene": random.choices(
                ["Non utilizzato", "Inutilizzabile", "In ristrutturazione/manutenzione", "Utilizzato direttamente"],
                weights=[0.5, 0.3, 0.1, 0.1],
                k=1
            )[0]
        }
        
        # Aggiungi dati APE
        immobile.update(ape_data)
        
        # Aggiungi dati POI (punteggi casuali 1-5 per le categorie principali)
        for cat in ["sanita", "mobilita", "verde", "sport", "commerciale", "educazione"]:
            immobile[cat] = round(random.uniform(1.0, 5.0), 1)
        
        return immobile
    
    def _generate_ape_data(self, classe_energetica: str) -> Dict:
        """Genera valori APE dettagliati basati sulla classe energetica."""
        # Mapping delle classi APE dettagliate
        ape_class_mapping = {
            "A": ["A1", "A2", "A3", "A4"],
            "B": ["B1", "B2", "B3"], 
            "C": ["C1", "C2"],
            "D": ["D1", "D2"],
            "E": ["E1", "E2", "E3"],
            "F": ["F1"],
            "G": ["G"]
        }
        
        # Range di punteggi per classe energetica
        score_ranges = {
            "A": (85, 100),
            "B": (70, 84),
            "C": (55, 69),
            "D": (40, 54),
            "E": (25, 39),
            "F": (10, 24),
            "G": (0, 9)
        }
        
        # Seleziona classe APE dettagliata
        if classe_energetica in ape_class_mapping:
            classe_energetica_ape = random.choice(ape_class_mapping[classe_energetica])
        else:
            classe_energetica_ape = classe_energetica
        
        # Genera punteggi APE
        ape_score_classe = random.randint(1, 5)
        ape_score_impianto = random.randint(1, 5)
        ape_score_involucro = random.randint(1, 5)
        ape_score_rinnovabili = random.randint(1, 5)
        ape_score_total = ape_score_classe + ape_score_impianto + ape_score_involucro + ape_score_rinnovabili
        
        return {
            "classe_energetica_ape": classe_energetica_ape,
            "epglnren_ape": round(random.uniform(20, 200), 2),  # kWh/m² anno
            "classe_target_ape": random.choice(["A1", "A2", "B1", "B2"]),
            "ape_score_classe": ape_score_classe,
            "ape_score_impianto": ape_score_impianto,
            "ape_score_involucro": ape_score_involucro,
            "ape_score_rinnovabili": ape_score_rinnovabili,
            "ape_score_total": ape_score_total,
        }
    
    def generate_poi(self, category: str, idx: int) -> Dict:
        """Genera singolo POI."""
        if category in POI_TEMPLATES and POI_TEMPLATES[category]:
            template = random.choice(POI_TEMPLATES[category])
            lat = template["lat"] + random.gauss(0, 0.002)
            lon = template["lon"] + random.gauss(0, 0.003)
            name = f"{template['name']} {idx}" if idx > 0 else template["name"]
        else:
            zone = random.choice(ZONE_TORINO)
            lat, lon = self.generate_coordinate(zone)
            name = f"{category.title()} {idx+1}"
        
        return {
            "id": f"POI_{category}_{idx:03d}",
            "name": name,
            "category": category,
            "latitude": lat,
            "longitude": lon
        }
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcola distanza haversine in metri."""
        R = 6371000
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
        return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    
    def generate_all(self) -> Tuple[Path, Path, Path, pd.DataFrame]:
        """Genera tutto il dataset."""
        config = USE_CASE_CONFIGS[self.use_case]
        
        # Svuota cartella synthetic_data
        print("Pulizia cartella synthetic_data...")
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Genera immobili
        print(f"Generando {self.num_immobili} immobili...")
        immobili = []
        for i in range(self.num_immobili):
            zone = random.choice(ZONE_TORINO)
            immobile = self.generate_immobile(i + 1, config, zone)
            immobili.append(immobile)
        
        df_immobili = pd.DataFrame(immobili)
        
        # Genera POI
        print(f"Generando POI...")
        pois = []
        for category in config["poi_categories"]:
            for i in range(self.num_poi_per_category):
                poi = self.generate_poi(category, i)
                pois.append(poi)
        
        # Calcola distanze
        print(f"Calcolando distanze...")
        distances = []
        for immobile in immobili:
            for poi in pois:
                dist = self.haversine_distance(
                    immobile["latitudine"], immobile["longitudine"],
                    poi["latitude"], poi["longitude"]
                )
                distances.append({
                    "id_immobile": immobile["id"],
                    "poi_id": poi["id"],
                    "poi_category": poi["category"],
                    "distance_m": round(dist, 2)
                })
        
        df_distances = pd.DataFrame(distances)
        
        # Salva
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        immobili_file = self.output_dir / f"immobili_synthetic_{self.use_case}_{timestamp}.parquet"
        df_immobili.to_parquet(immobili_file, index=False)
        
        poi_file = self.output_dir / f"poi_synthetic_{self.use_case}_{timestamp}.json"
        with open(poi_file, 'w') as f:
            json.dump(pois, f, indent=2)
        
        distances_file = self.output_dir / f"distances_synthetic_{self.use_case}_{timestamp}.csv"
        df_distances.to_csv(distances_file, index=False)
        
        print(f"✓ Dataset generato:")
        print(f"  - Immobili: {immobili_file}")
        print(f"  - POI: {poi_file}")
        print(f"  - Distanze: {distances_file}")
        
        return immobili_file, poi_file, distances_file, df_immobili
