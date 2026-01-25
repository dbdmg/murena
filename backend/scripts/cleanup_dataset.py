#!/usr/bin/env python
"""
Dataset Cleanup Script
======================
This script cleans the main dataset by:
1. Removing unused/ghost columns
2. Verifying score columns are in the new scale (1-5)
3. Generating a backup before modifications

Run from backend folder:
    python scripts/cleanup_dataset.py [--dry-run] [--backup]
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# ==============================================================================
# CONFIGURATION
# ==============================================================================

DATASET_PATH = "data/FOLDER_META/immobili_with_meta_and_ape_full_cleaned.parquet"
BACKUP_DIR = "data/FOLDER_META/_backup"

# Columns actively used by the backend (from grep analysis)
COLUMNS_USED = {
    # Core identifiers
    "id",
    "codice_comune",
    "foglio",
    "particella",
    "subalterno",
    # Location
    "latitudine",
    "longitudine",
    "indirizzo",
    "numero_civico",
    "zona_omi",
    # Property attributes
    "superficie_di_riferimento_mq",
    "natura_del_bene",
    "tipologia_bene_immobile",
    "epoca_costruzione",
    "vincolo_culturale_paesaggistico",
    "natura_giuridica_del_bene",
    "utilizzo_del_bene",
    "finalita",
    # Rental info
    "tipo_detenzione_a_terzi",
    "canone_annuale",
    "data_decorrenza",
    # Meta-immobile handling
    "numero_immobili_per_catasto",
    "id_list",
    "meta_immobile",
    # APE file references
    "lista_file_ape",
    "list_file_ape_filtered",
    "list_file_ape_filtered_parsed",
    # APE scores (NEW SCALE 1-5)
    "ape_score_classe",
    "ape_score_impianto",
    "ape_score_involucro",
    "ape_score_rinnovabili",
    "ape_score_total",
    # APE class info
    "classe_energetica_ape",
    "epglnren_ape",
    "classe_target_ape",
    # POI scores
    "sanita",
    "mobilita",
    "verde",
    "sport",
    "commerciale",
    "educazione",
}

# Columns that exist but are NOT used (candidates for removal)
COLUMNS_UNUSED = {
    "coordinate_ds_coerenti",  # Not referenced in code
    "list_file_ape_validated",  # Not referenced in code
    "fonte_coordinate_usata",  # Not referenced in code
    "list_file_ape_validated_norm",  # Not referenced in code
    "plot_filename",  # Not referenced in code
    "id_left",  # Artifact from merge operation
    "id_list_formatted",  # Not referenced in code
}


def analyze_dataset(df: pd.DataFrame) -> dict:
    """Analyze dataset and return statistics."""
    stats = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": list(df.columns),
        "used_columns": [],
        "unused_columns": [],
        "unknown_columns": [],
        "score_analysis": {},
    }

    for col in df.columns:
        if col in COLUMNS_USED:
            stats["used_columns"].append(col)
        elif col in COLUMNS_UNUSED:
            stats["unused_columns"].append(col)
        else:
            stats["unknown_columns"].append(col)

    # Analyze score columns
    score_cols = [c for c in df.columns if "score" in c.lower()]
    for col in score_cols:
        non_null = df[col].notna().sum()
        stats["score_analysis"][col] = {
            "min": float(df[col].min()) if non_null > 0 else None,
            "max": float(df[col].max()) if non_null > 0 else None,
            "mean": float(df[col].mean()) if non_null > 0 else None,
            "non_null_count": int(non_null),
            "scale_valid": True,  # Will verify
        }
        # Verify scale
        if col == "ape_score_total":
            # Total should be 6-20 (sum of 4 scores 1-5 + 2 baseline)
            if stats["score_analysis"][col]["max"] is not None:
                stats["score_analysis"][col]["scale_valid"] = (
                    stats["score_analysis"][col]["max"] <= 20
                )
        elif "ape_score" in col:
            # Individual scores should be 1-5
            if stats["score_analysis"][col]["max"] is not None:
                stats["score_analysis"][col]["scale_valid"] = (
                    stats["score_analysis"][col]["max"] <= 5
                )

    return stats


def create_backup(source_path: str, backup_dir: str) -> str:
    """Create a timestamped backup of the dataset."""
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = Path(source_path).stem
    backup_path = os.path.join(backup_dir, f"{filename}_backup_{timestamp}.parquet")
    shutil.copy2(source_path, backup_path)
    return backup_path


def cleanup_dataset(df: pd.DataFrame, columns_to_drop: list) -> pd.DataFrame:
    """Remove unused columns from dataset."""
    existing_to_drop = [c for c in columns_to_drop if c in df.columns]
    if existing_to_drop:
        df = df.drop(columns=existing_to_drop)
    return df


def print_report(stats: dict):
    """Print analysis report."""
    print("\n" + "=" * 80)
    print("DATASET ANALYSIS REPORT")
    print("=" * 80)

    print(f"\n📊 Overview:")
    print(f"   Total Rows: {stats['total_rows']:,}")
    print(f"   Total Columns: {stats['total_columns']}")

    print(f"\n✅ USED Columns ({len(stats['used_columns'])}):")
    for col in sorted(stats["used_columns"]):
        print(f"   - {col}")

    print(
        f"\n🗑️  UNUSED Columns (candidates for removal) ({len(stats['unused_columns'])}):"
    )
    for col in sorted(stats["unused_columns"]):
        print(f"   - {col}")

    if stats["unknown_columns"]:
        print(
            f"\n⚠️  UNKNOWN Columns (not in either list) ({len(stats['unknown_columns'])}):"
        )
        for col in sorted(stats["unknown_columns"]):
            print(f"   - {col}")

    print(f"\n📈 Score Columns Analysis:")
    for col, info in stats["score_analysis"].items():
        status = "✅" if info["scale_valid"] else "❌"
        print(f"   {status} {col}:")
        print(f"      Range: {info['min']} - {info['max']}")
        print(f"      Mean: {info['mean']:.2f}" if info["mean"] else "      Mean: N/A")
        print(f"      Non-null: {info['non_null_count']:,} / {stats['total_rows']:,}")


def main():
    parser = argparse.ArgumentParser(description="Clean up the main dataset")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only, don't modify files",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup before modifications",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    if not os.path.exists(DATASET_PATH):
        print(f"❌ Dataset not found: {DATASET_PATH}")
        sys.exit(1)

    print(f"📂 Loading dataset: {DATASET_PATH}")
    df = pd.read_parquet(DATASET_PATH)

    # Analyze
    stats = analyze_dataset(df)
    print_report(stats)

    if args.dry_run:
        print("\n🔍 DRY RUN - No changes made")
        return

    # Columns to remove
    columns_to_drop = list(COLUMNS_UNUSED)
    if not columns_to_drop:
        print("\n✅ No columns to remove")
        return

    print(f"\n🗑️  Will remove {len(columns_to_drop)} columns:")
    for col in columns_to_drop:
        print(f"   - {col}")

    if not args.force:
        response = input("\nProceed? [y/N]: ")
        if response.lower() != "y":
            print("Aborted")
            return

    # Backup
    if args.backup:
        backup_path = create_backup(DATASET_PATH, BACKUP_DIR)
        print(f"\n💾 Backup created: {backup_path}")

    # Clean
    df_clean = cleanup_dataset(df, columns_to_drop)

    # Save
    df_clean.to_parquet(DATASET_PATH, index=False)
    print(f"\n✅ Dataset cleaned and saved: {DATASET_PATH}")
    print(f"   Columns removed: {len(columns_to_drop)}")
    print(f"   Final column count: {len(df_clean.columns)}")


if __name__ == "__main__":
    main()
