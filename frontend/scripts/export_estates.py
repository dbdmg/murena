"""Export the configured real-estate Parquet as a compact browser inventory."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/data/metadata/estates.parquet"
DESTINATION = ROOT / "frontend/public/data/estates.json"

COLUMNS = [
    "id", "latitude", "longitude", "address", "surface_area",
    "construction_period", "energy_class", "property_type", "is_meta_estate",
    "ape_file_list_filtered", "energy_score_total", "energy_score_class",
    "energy_score_plant", "energy_score_envelope", "energy_score_renewables",
    "healthcare", "mobility", "green", "education", "commercial", "sport",
]


def main() -> None:
    frame = pd.read_parquet(SOURCE, columns=COLUMNS)
    frame = frame.astype(object).where(pd.notna(frame), None)
    rows = []
    for record in frame.to_dict(orient="records"):
        rows.append({
            "id": record["id"],
            "latitude": record["latitude"],
            "longitude": record["longitude"],
            "address": record["address"],
            "surface_area": record["surface_area"],
            "construction_period": record["construction_period"],
            "energy_class": record["energy_class"],
            "property_type": record["property_type"],
            "is_meta_estate": record["is_meta_estate"],
            "ape_file_list_filtered": record["ape_file_list_filtered"],
            "energy_scores": {
                "total": record["energy_score_total"],
                "class_score": record["energy_score_class"],
                "plant_score": record["energy_score_plant"],
                "envelope_score": record["energy_score_envelope"],
                "renewables_score": record["energy_score_renewables"],
            },
            "proximity_scores": {
                "healthcare": record["healthcare"],
                "mobility": record["mobility"],
                "greenery": record["green"],
                "education": record["education"],
                "commerce": record["commercial"],
                "sport": record["sport"],
            },
        })

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Exported {len(rows)} estates to {DESTINATION.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
