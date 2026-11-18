"""Copy the categorized offline POI catalog into the demo's public assets."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/data/metadata/pois_by_category.json"
DESTINATION = ROOT / "frontend/public/data/pois_by_category.json"


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Exported categorized POIs to {DESTINATION.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
