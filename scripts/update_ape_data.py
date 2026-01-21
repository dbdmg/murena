#!/usr/bin/env python
"""
APE Parquet Updater Script

This script processes APE XML files and updates the ape_detailed_data.parquet file.
It also recalculates energy scores after updating the data.

Usage:
    python update_ape_data.py                    # Process all XMLs and update parquet
    python update_ape_data.py --only-scores      # Only recalculate energy scores
    python update_ape_data.py --xml-folder PATH  # Specify custom XML folder
"""

import sys
import argparse
from pathlib import Path

# Add backend to path
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd
from typing import Optional

# Default paths
DEFAULT_XML_FOLDER = BACKEND_DIR / "data" / "FOLDER_APE_MATCH"
DEFAULT_PARQUET_PATH = (
    BACKEND_DIR / "data" / "FOLDER_META" / "ape_detailed_data.parquet"
)


def parse_all_ape_xmls(xml_folder: Path) -> pd.DataFrame:
    """
    Parse all APE XML files in the given folder.

    Args:
        xml_folder: Path to folder containing APE XML files

    Returns:
        DataFrame with parsed APE data
    """
    from app.data.processors import parse_ape_xml

    xml_files = list(xml_folder.glob("*.xml"))
    print(f"Found {len(xml_files)} XML files in {xml_folder}")

    records = []
    errors = []

    for i, xml_file in enumerate(xml_files, 1):
        if i % 100 == 0:
            print(f"  Processing {i}/{len(xml_files)}...")

        try:
            xml_text = xml_file.read_text(encoding="utf-8")
            data = parse_ape_xml(xml_text)
            data["file"] = xml_file.name
            records.append(data)
        except Exception as e:
            errors.append((xml_file.name, str(e)))

    if errors:
        print(f"\nWarnings: {len(errors)} files had errors:")
        for fname, err in errors[:5]:
            print(f"  - {fname}: {err}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")

    df = pd.DataFrame(records)
    print(f"\nParsed {len(df)} APE records with {len(df.columns)} columns")

    return df


def calculate_energy_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate energy scores for all records.

    Args:
        df: DataFrame with APE data

    Returns:
        DataFrame with energy scores added
    """
    from scipy import stats

    print("\nCalculating energy scores...")

    # Convert numeric columns
    df = df.copy()
    for col in ["consumo_kwh_tot", "superficie", "destinazione_uso_cod"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calculate kWh per square meter
    if "consumo_kwh_tot" in df.columns and "superficie" in df.columns:
        df["kwh_per_sqm"] = df["consumo_kwh_tot"] / df["superficie"]

        # Remove invalid values
        valid_mask = (
            df["kwh_per_sqm"].notna()
            & (df["kwh_per_sqm"] > 0)
            & (df["kwh_per_sqm"] < 1000)
        )

        # Build distributions per usage type
        distributions = {}
        for usage_type in df.loc[valid_mask, "destinazione_uso_cod"].dropna().unique():
            subset = df.loc[
                valid_mask & (df["destinazione_uso_cod"] == usage_type), "kwh_per_sqm"
            ]
            if len(subset) >= 10:
                distributions[usage_type] = {"mean": subset.mean(), "std": subset.std()}
                print(
                    f"  Usage type {usage_type}: mean={subset.mean():.1f} kWh/m², std={subset.std():.1f}, n={len(subset)}"
                )

        # Global distribution as fallback
        all_valid = df.loc[valid_mask, "kwh_per_sqm"]
        global_dist = {"mean": all_valid.mean(), "std": all_valid.std()}
        print(
            f"  Global: mean={global_dist['mean']:.1f} kWh/m², std={global_dist['std']:.1f}, n={len(all_valid)}"
        )

        # Calculate scores
        def calc_score(row):
            kwh = row.get("kwh_per_sqm")
            usage = row.get("destinazione_uso_cod")

            if pd.isna(kwh) or kwh <= 0:
                return None

            dist = distributions.get(usage, global_dist)
            if dist["std"] == 0:
                return 50

            z_score = (kwh - dist["mean"]) / dist["std"]
            percentile = 1 - stats.norm.cdf(z_score)
            return int(max(0, min(100, percentile * 100)))

        df["energy_score"] = df.apply(calc_score, axis=1)
        df["estimated_cost_year"] = df["consumo_kwh_tot"] * 0.25  # €/kWh
        df["cost_per_sqm_year"] = df["kwh_per_sqm"] * 0.25

        scores_count = df["energy_score"].notna().sum()
        print(f"\nCalculated energy scores for {scores_count} records")
    else:
        print(
            "Warning: Missing consumo_kwh_tot or superficie columns, skipping energy scores"
        )

    return df


def update_ape_data(
    xml_folder: Optional[Path] = None,
    output_path: Optional[Path] = None,
    only_scores: bool = False,
) -> Path:
    """
    Main function to update APE parquet data.

    Args:
        xml_folder: Path to XML folder (default: FOLDER_APE_MATCH)
        output_path: Path for output parquet (default: ape_detailed_data.parquet)
        only_scores: If True, only recalculate scores without parsing XMLs

    Returns:
        Path to updated parquet file
    """
    xml_folder = xml_folder or DEFAULT_XML_FOLDER
    output_path = output_path or DEFAULT_PARQUET_PATH

    if only_scores:
        print(f"Loading existing data from {output_path}...")
        df = pd.read_parquet(output_path)
        print(f"Loaded {len(df)} records")
    else:
        print(f"Parsing APE XMLs from {xml_folder}...")
        df = parse_all_ape_xmls(xml_folder)

    # Calculate energy scores
    df = calculate_energy_scores(df)

    # Save to parquet
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"\n✅ Saved {len(df)} records to {output_path}")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Update APE parquet data from XML files and calculate energy scores"
    )
    parser.add_argument(
        "--xml-folder",
        type=Path,
        default=DEFAULT_XML_FOLDER,
        help=f"Path to folder with APE XML files (default: {DEFAULT_XML_FOLDER})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PARQUET_PATH,
        help=f"Output parquet path (default: {DEFAULT_PARQUET_PATH})",
    )
    parser.add_argument(
        "--only-scores",
        action="store_true",
        help="Only recalculate energy scores without parsing XMLs",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("APE Parquet Updater")
    print("=" * 60)

    update_ape_data(
        xml_folder=args.xml_folder,
        output_path=args.output,
        only_scores=args.only_scores,
    )

    print("\nDone!")


if __name__ == "__main__":
    main()
