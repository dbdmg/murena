"""Export the configured real-estate Parquet as a compact browser inventory."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/data/metadata/estates.parquet"
DESTINATION = ROOT / "frontend/public/data/estates.json"
BENCHMARK_SOURCE = ROOT / "frontend/public/data/benchmark_runs.json"
BENCHMARK_DESTINATION = ROOT / "frontend/public/data/benchmark_estates.json"
MAP_INVENTORY_LIMIT = 5000

COLUMNS = [
    "id", "latitude", "longitude", "address", "house_number", "surface_area",
    "construction_period", "energy_class", "property_type", "is_meta_estate",
    "omi_zone", "cadastral_sheet", "cadastral_parcel", "cadastral_subaltern",
    "cadastral_units_count", "id_list", "effective_date",
    "ape_file_list_filtered", "energy_score_total", "energy_score_class",
    "energy_score_plant", "energy_score_envelope", "energy_score_renewables",
    "healthcare", "mobility", "green", "education", "commercial", "sport",
]


def records_for(frame: pd.DataFrame) -> list[dict]:
    frame = frame.astype(object).where(pd.notna(frame), None)
    rows = []
    for record in frame.to_dict(orient="records"):
        rows.append({
            "id": record["id"],
            "latitude": record["latitude"],
            "longitude": record["longitude"],
            "address": record["address"],
            "house_number": record["house_number"],
            "surface_area": record["surface_area"],
            "construction_period": record["construction_period"],
            "energy_class": record["energy_class"],
            "property_type": record["property_type"],
            "is_meta_estate": record["is_meta_estate"],
            "omi_zone": record["omi_zone"],
            "cadastral_sheet": record["cadastral_sheet"],
            "cadastral_parcel": record["cadastral_parcel"],
            "cadastral_subaltern": record["cadastral_subaltern"],
            "cadastral_units_count": record["cadastral_units_count"],
            "id_list": record["id_list"],
            "effective_date": (
                record["effective_date"].isoformat()
                if hasattr(record["effective_date"], "isoformat")
                else record["effective_date"]
            ),
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

    return rows


def main() -> None:
    frame = pd.read_parquet(SOURCE, columns=COLUMNS)
    map_frame = frame.sample(n=min(MAP_INVENTORY_LIMIT, len(frame)), random_state=42)
    rows = records_for(map_frame)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    benchmark_ids: set[str] = set()
    if BENCHMARK_SOURCE.is_file():
        benchmark_runs = json.loads(BENCHMARK_SOURCE.read_text(encoding="utf-8"))
        benchmark_ids = {
            str(item["id"])
            for run in benchmark_runs.values()
            for item in run.get("top", [])
            if isinstance(item, dict) and item.get("id") is not None
        }
    result_frame = frame[frame["id"].astype(str).isin(benchmark_ids)]
    result_rows = records_for(result_frame)
    BENCHMARK_DESTINATION.write_text(
        json.dumps(result_rows, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"Exported {len(rows)} map estates and {len(result_rows)} benchmark estates "
        f"to {DESTINATION.parent.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
