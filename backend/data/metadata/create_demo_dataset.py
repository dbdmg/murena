"""Generate a synthetic DEMO dataset for local development.

The real MURENA dataset is built by ``create_estate_dataset.py`` from ~90k raw
APE XML certificates (SIPEE, Piedmont) plus OSM extracts — sources that are
not versioned in this repository. Without them the app starts empty.

This script produces a *clearly synthetic* ``estates.parquet`` with the exact
schema the application expects (map markers, building browsing, SQL agent
filtering, ranking and energy/proximity scoring), so the full stack can be
developed and demoed on any machine.

Usage (from the repo root):

    uv run python backend/data/metadata/create_demo_dataset.py [--n 1500]

The file is written to backend/data/metadata/estates.parquet only if it does
not already exist (use --force to overwrite).
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "estates.parquet"

# Turin bounding box (roughly the urban core)
LAT_MIN, LAT_MAX = 45.030, 45.115
LON_MIN, LON_MAX = 7.615, 7.720
CENTER_LAT, CENTER_LON = 45.0705, 7.6868

STREETS = [
    "Via Roma", "Corso Vittorio Emanuele II", "Via Po", "Corso Francia",
    "Via Garibaldi", "Corso Giulio Cesare", "Via Nizza", "Corso Regina Margherita",
    "Via Madama Cristina", "Corso Duca degli Abruzzi", "Via San Donato",
    "Corso Traiano", "Via Cibrario", "Corso Belgio", "Via Sacchi",
    "Corso Racconigi", "Via Tripoli", "Corso Casale", "Via Monginevro",
    "Corso Unione Sovietica", "Via Barletta", "Via Bologna", "Corso Peschiera",
    "Via Genova", "Via Chiesa della Salute", "Corso Sebastopoli",
]

ENERGY_CLASSES = ["A4", "A3", "A2", "A1", "B", "C", "D", "E", "F", "G"]
ENERGY_CLASS_P = [0.01, 0.01, 0.02, 0.03, 0.05, 0.10, 0.16, 0.22, 0.20, 0.20]

PROPERTY_TYPES = [
    ("Residential dwelling", 0.62),
    ("Office building", 0.10),
    ("Commercial unit", 0.09),
    ("Warehouse", 0.06),
    ("School building", 0.04),
    ("Hotel", 0.03),
    ("Clinic", 0.03),
    ("Industrial shed", 0.03),
]

CONSTRUCTION_PERIODS = [
    ("Prima del 1919", 0.14),
    ("Dal 1919 al 1945", 0.12),
    ("Dal 1946 al 1960", 0.18),
    ("Dal 1961 al 1980", 0.28),
    ("Dal 1981 al 2000", 0.16),
    ("Dopo il 2000", 0.12),
]

HEATING = [
    "Standard boiler", "Condensing boiler", "District heating",
    "Heat pump", "Electric heating",
]

OMI_ZONES = [f"B{i}" for i in range(1, 10)] + [f"C{i}" for i in range(1, 8)] \
    + [f"D{i}" for i in range(1, 6)] + [f"E{i}" for i in range(1, 4)]


def _weighted(rng, options):
    values, probs = zip(*options)
    return rng.choice(values, p=np.array(probs) / sum(probs))


def generate(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    lat = rng.uniform(LAT_MIN, LAT_MAX, n)
    lon = rng.uniform(LON_MIN, LON_MAX, n)

    # Proximity pillars: higher near the centre, 0-100 percentile-like scores.
    dist = np.sqrt((lat - CENTER_LAT) ** 2 + (lon - CENTER_LON) ** 2)
    dist_norm = 1 - (dist - dist.min()) / (dist.max() - dist.min() + 1e-9)

    def pillar(spread: float) -> np.ndarray:
        raw = 100 * (0.55 * dist_norm + 0.45 * rng.random(n)) ** spread
        return np.clip(raw, 0, 100).round(1)

    energy_class = rng.choice(ENERGY_CLASSES, size=n, p=ENERGY_CLASS_P)
    class_rank = np.array([ENERGY_CLASSES.index(c) for c in energy_class])

    # EPgl,nren correlated with the class (A4 ~ 30, G ~ 400 kWh/m2y)
    epgl = (30 + class_rank * 38 + rng.normal(0, 18, n)).clip(15, 500).round(1)

    def energy_subscore(base_from_class: np.ndarray) -> np.ndarray:
        noisy = base_from_class + rng.integers(-1, 2, n)
        return np.clip(noisy, 1, 5).astype(int)

    # Class 0..9 -> score 5..1
    score_class = np.clip(5 - (class_rank / 2).astype(int), 1, 5)
    score_plant = energy_subscore(score_class)
    score_envelope = energy_subscore(score_class)
    score_renewables = rng.choice([1, 5], size=n, p=[0.72, 0.28])
    score_total = (
        (score_class + score_plant + score_envelope + score_renewables) / 4.0
    ).round(2)

    surface = rng.lognormal(mean=4.6, sigma=0.55, size=n).clip(25, 4200).round(0)

    n_meta = max(1, int(n * 0.12))
    meta_flags = np.zeros(n, dtype=bool)
    meta_flags[:n_meta] = True
    rng.shuffle(meta_flags)

    ids = np.array([f"DEMO-{i:05d}" for i in range(1, n + 1)])
    id_list = [
        str([f"{ids[i]}-U{j}" for j in range(1, int(rng.integers(2, 11)))])
        if meta_flags[i] else None
        for i in range(n)
    ]

    df = pd.DataFrame({
        "id": ids,
        "address": rng.choice(STREETS, n),
        "house_number": rng.integers(1, 220, n).astype(str),
        "latitude": lat.round(6),
        "longitude": lon.round(6),
        "omi_zone": rng.choice(OMI_ZONES, n),
        "codice_comune": "L219",
        "city": "Torino",
        "cadastral_sheet": rng.integers(1, 1500, n).astype(str),
        "cadastral_parcel": rng.integers(1, 900, n).astype(str),
        "cadastral_subaltern": rng.integers(1, 60, n).astype(str),
        "cadastral_units_count": np.where(
            meta_flags, rng.integers(2, 12, n), 1
        ),
        "surface_area": surface,
        "property_type": [(_weighted(rng, PROPERTY_TYPES)) for _ in range(n)],
        "construction_period": [
            (_weighted(rng, CONSTRUCTION_PERIODS)) for _ in range(n)
        ],
        "construction_year": rng.integers(1890, 2024, n),
        "legal_nature": rng.choice(
            ["Public property", "Private property"], n, p=[0.35, 0.65]
        ),
        "cultural_constraint": rng.choice(["No", "Yes"], n, p=[0.9, 0.1]),
        "energy_class": energy_class,
        "epglnren_ape": epgl,
        "classe_target_ape": rng.choice(ENERGY_CLASSES[:6], n),
        "energy_score_class": score_class,
        "energy_score_plant": score_plant,
        "energy_score_envelope": score_envelope,
        "energy_score_renewables": score_renewables,
        "energy_score_total": score_total,
        "heating_system": rng.choice(HEATING, n),
        "healthcare": pillar(1.0),
        "mobility": pillar(0.8),
        "green": pillar(1.2),
        "sport": pillar(1.1),
        "commercial": pillar(0.7),
        "education": pillar(1.0),
        "meta_building": meta_flags,
        "is_meta": meta_flags,
        "id_list": id_list,
        "annual_rent": (surface * rng.uniform(60, 160, n)).round(0),
        "description": "Synthetic DEMO building (generated by create_demo_dataset.py)",
    })
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1500, help="number of buildings")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="overwrite existing file")
    args = parser.parse_args()

    if OUTPUT.exists() and not args.force:
        print(f"{OUTPUT} already exists; use --force to overwrite. Nothing done.")
        return

    df = generate(args.n, args.seed)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT, index=False)
    print(f"DEMO dataset written: {OUTPUT} ({len(df)} synthetic buildings)")
    print("NOTE: this is synthetic data for local development only - replace it")
    print("with the real estates.parquet for any meaningful analysis.")


if __name__ == "__main__":
    main()
