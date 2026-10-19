"""Reproducible APE/MURENA dataset profiling; does not modify production data.

The profiler reads Parquet with DuckDB and optionally counts/samples XML files.
It writes JSON, CSV, Markdown, and dependency-free SVG artifacts.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import random
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ALIASES = {
    "is_meta_estate": ("is_meta_estate", "meta_immobile"),
    "cadastral_units_count": ("cadastral_units_count", "numero_immobili_per_catasto"),
    "cadastral_sheet": ("cadastral_sheet", "foglio"),
    "cadastral_parcel": ("cadastral_parcel", "particella"),
    "cadastral_subaltern": ("cadastral_subaltern", "subalterno"),
    "comune_code": ("comune_code", "codice_comune"),
    "municipality": ("municipality",),
    "istat_code": ("istat_code",),
    "surface_area": ("surface_area", "superficie_di_riferimento_mq", "heated_usable_surface"),
    "address": ("address", "indirizzo"),
    "house_number": ("house_number", "numero_civico"),
    "latitude": ("latitude", "latitudine", "xml_latitude"),
    "longitude": ("longitude", "longitudine", "xml_longitude"),
    "omi_zone": ("omi_zone", "zona_omi"),
    "property_type": ("property_type", "tipologia_bene_immobile", "dpr412_class_code"),
    "construction_period": ("construction_period", "epoca_costruzione", "construction_year"),
    "issue_date": ("effective_date", "data_decorrenza", "issue_date"),
    "energy_class": ("energy_class", "classe_energetica_ape"),
    "epglnren": ("epglnren", "epglnren_ape"),
    "epglren": ("epglren", "epglren_ape"),
    "co2_emissions": ("co2_emissions", "emissioni_co2"),
    "target_energy_class": ("target_energy_class", "classe_target_ape"),
    "heating_energy_need": ("heating_energy_need",),
    "cooling_energy_need": ("cooling_energy_need",),
    "heating_system_type": ("heating_system_type",),
    "has_heating": ("has_heating",),
    "has_dhw": ("has_dhw",),
    "climate_zone": ("climate_zone",),
    "xml_schema_version": ("xml_schema_version",),
    "attestation_object_code": ("attestation_object_code",),
    "dpr412_class_code": ("dpr412_class_code",),
    "number_real_estate_units": ("number_real_estate_units",),
    "source_record_id": ("source_record_id",),
    "intervention_code": ("intervention_code",),
    "reachable_epglnren": ("reachable_epglnren",),
    "reachable_energy_class": ("reachable_energy_class",),
    "overall_reachable_epglnren": ("overall_reachable_epglnren",),
    "parse_status": ("parse_status",),
    "coordinate_provenance": ("coordinate_provenance",),
    "geocoding_confidence": ("geocoding_confidence",),
    "ape_file_list": ("ape_file_list", "lista_file_ape"),
    "id_list": ("id_list",),
    "cadastral_municipality": ("cadastral_municipality",),
    "istat_code": ("istat_code",),
    "source_sha256": ("source_sha256",),
}

DESCRIPTIONS = {
    "id": ("MURENA row identifier", "application export", "identifier", "Not a source certificate ID."),
    "source_record_id": ("Stable identifier derived from source-relative path and APE identifier", "APE extraction", "identifier", "Identifies a source certificate file; use source_filename and hash for provenance."),
    "source_sha256": ("SHA-256 digest of original XML bytes", "source XML", "hex digest", "Allows checking source file integrity without storing its contents in Parquet."),
    "parse_status": ("Strict parse or explicitly normalized parse outcome", "APE extraction", "category", "Normalized records preserve valid UTF-8 and map only invalid UTF-8 bytes through inferred CP1252."),
    "source_encoding_declared": ("Encoding declared in the XML prolog", "source XML", "encoding label", "May be absent or inaccurate."),
    "source_encoding_used": ("Decoder used to construct the parsed text", "APE extraction", "encoding/provenance", "For repaired records, CP1252 mapping is inferred only for invalid UTF-8 bytes."),
    "source_repaired_byte_count": ("Number of invalid UTF-8 bytes mapped through CP1252", "APE extraction", "count", "All repaired bytes are counted; original file remains unchanged."),
    "potentially_lossy": ("Whether parser used lossy recovery", "APE extraction", "boolean", "Current parser does not emit lxml recovery trees; recovered bytes use strict reversible decoding."),
    "parser_warning_count": ("Warnings emitted by the parsing strategy", "APE extraction", "count", "Strict and controlled normalization parses have zero recovery warnings."),
    "is_meta_estate": ("Whether the row is a derived metaestate", "application export", "boolean", "Derived; exclude or group with care."),
    "id_list": ("String list of constituent MURENA row IDs", "application export", "identifier list", "Useful for provenance; not a physical-building ground truth."),
    "cadastral_sheet": ("Cadastral sheet/foglio", "APE/application export", "coded identifier", "Zeros may be missing-value placeholders in legacy exports."),
    "cadastral_parcel": ("Cadastral parcel/particella", "APE/application export", "coded identifier", "A parcel may contain multiple buildings."),
    "cadastral_subaltern": ("Cadastral subaltern/unit identifier", "APE/application export", "coded identifier", "May be missing or conventional zero."),
    "surface_area": ("Reference usable surface", "APE", "m²", "Check zero, negative, and outlier values."),
    "heated_usable_surface": ("Heated usable floor surface from the APE", "APE XML", "m²", "Certificate/unit-level measurement; not necessarily whole-building area."),
    "cadastral_municipality": ("Cadastral municipality code", "APE XML", "coded string", "Preserved as provided, including leading zeros."),
    "istat_code": ("ISTAT municipality code", "APE XML", "coded string", "Preserved as provided, including leading zeros."),
    "attestation_object_code": ("APE attestation object code", "APE XML", "source code", "Raw code is retained; semantics are not inferred."),
    "dpr412_class_code": ("DPR 412 building-use class code", "APE XML", "source code", "Raw code is retained; not current occupancy or use permission."),
    "construction_period": ("Reported construction year/period", "APE", "year or code", "Not necessarily a precise construction year."),
    "issue_date": ("Certificate effective/issue date", "APE", "date", "Used for temporal coverage."),
    "energy_class": ("APE energy class", "APE", "class code", "Certified for the unit/certificate, not necessarily whole building."),
    "epglnren": ("Global non-renewable primary energy performance", "APE", "kWh/m²·year (typically)", "Check source/version-specific unit and anomalous values."),
    "epglren": ("Global renewable primary energy performance", "APE", "kWh/m²·year (typically)", "Check source/version-specific unit."),
    "co2_emissions": ("Reported CO₂ emissions indicator", "APE", "kgCO₂/m²·year (typically)", "Check source/version-specific unit."),
    "latitude": ("Latitude", "XML/OSM enrichment", "decimal degrees", "Coordinate provenance is absent in both current Parquet snapshots."),
    "longitude": ("Longitude", "XML/OSM enrichment", "decimal degrees", "Coordinate provenance is absent in both current Parquet snapshots."),
    "property_type": ("DPR 412/use classification label", "APE/application mapping", "coded category", "A regulatory category, not current occupancy or functional suitability."),
    "omi_zone": ("OMI market zone", "OMI enrichment", "zone code", "Coverage reflects enrichment configuration."),
    "commercial": ("Commercial amenity score", "POI enrichment", "score / percentile", "Derived accessibility proxy; not service demand."),
    "education": ("Education amenity score", "POI enrichment", "score / percentile", "Derived accessibility proxy; not service demand."),
    "mobility": ("Mobility amenity score", "POI enrichment", "score / percentile", "Derived accessibility proxy; not universal accessibility compliance."),
    "healthcare": ("Healthcare amenity score", "POI enrichment", "score / percentile", "Derived accessibility proxy; not health-service capacity."),
    "green": ("Green amenity score", "POI enrichment", "score / percentile", "Derived proximity score."),
    "sport": ("Sport amenity score", "POI enrichment", "score / percentile", "Derived proximity score."),
    "heating_energy_need": ("Heating energy need", "APE", "kWh/m²·year (likely)", "Available only in workspace snapshot."),
    "cooling_energy_need": ("Cooling energy need", "APE", "kWh/m²·year (likely)", "Available only in workspace snapshot; often missing."),
    "heating_system_type": ("Heating system type", "APE", "source code/label", "Unavailable in exported Parquet snapshots."),
    "has_heating": ("Heating service indicator", "APE", "boolean", "Unavailable in exported Parquet snapshots."),
    "has_dhw": ("DHW service indicator", "APE", "boolean", "Unavailable in exported Parquet snapshots."),
    "climate_zone": ("Climate zone", "APE", "zone code", "Unavailable in exported Parquet snapshots."),
    "xml_schema_version": ("APE XML version", "APE XML", "version string", "Unavailable in exported Parquet snapshots."),
    "attestation_object_code": ("Attestation object code", "APE XML", "source code", "Unavailable in exported Parquet snapshots."),
    "dpr412_class_code": ("DPR 412 use classification code", "APE XML", "source code", "Unavailable as a source code in exported Parquet snapshots."),
    "coordinate_provenance": ("Coordinate source", "pipeline", "category", "Not present in current snapshots."),
    "geocoding_confidence": ("Geocoding confidence", "pipeline", "category", "Not present in current snapshots."),
}

USE_CASES = [
    ("Community healthcare facilities", "Partially evaluable", "surface_area; construction_period; energy_class; epglnren; coordinates; healthcare", "Structural safety, accessibility compliance, ownership, healthcare licensing/capacity, availability, retrofit cost, local demand."),
    ("Social and community centers", "Partially evaluable", "surface_area; construction_period; energy_class; epglnren; coordinates; education/mobility/green", "Occupancy, accessibility, fire safety, ownership, availability, operating cost, local demand."),
    ("Libraries and cultural facilities", "Partially evaluable", "surface_area; property_type; energy_class; coordinates; education/mobility", "Floor loading, daylight/acoustics, conservation constraints, accessibility, ownership, availability and demand."),
    ("Educational and training spaces", "Partially evaluable", "surface_area; property_type; energy_class; coordinates; education/mobility", "School authorization, occupancy limits, accessibility, fire safety, capacity, demand and operating costs."),
    ("Public administration offices", "Partially evaluable", "surface_area; property_type; energy_class; coordinates; mobility", "Ownership, availability, security, accessibility, floor layout, service demand and public-sector reuse permissions."),
    ("Social housing", "Partially evaluable", "surface_area; construction_period; energy_class; epglnren; coordinates", "Unit layout, tenure/ownership, habitability, structural safety, accessibility, affordability, availability and housing need."),
    ("Climate shelters", "Partially evaluable", "surface_area; energy_class; heating/cooling needs when present; coordinates; green/mobility", "Thermal resilience, backup power, water, accessible routes, opening/operating arrangements, capacity and population exposure."),
    ("Multifunctional urban regeneration spaces", "Partially evaluable", "surface_area; property_type; construction_period; energy metrics; coordinates; POI scores", "Ownership, structural condition, zoning, contamination, accessibility, renovation cost, vacancy, demand and governance."),
]


def qi(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    p = successes / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / den
    return [max(0.0, center - half), min(1.0, center + half)]


def input_spec(spec: str, outdir: Path) -> tuple[str, Path]:
    if "=" not in spec:
        raise ValueError(f"Input must be NAME=PATH, got: {spec}")
    name, value = spec.split("=", 1)
    if "::" in value:
        archive, member = value.split("::", 1)
        extracted = outdir / ".cache" / f"{name}_{Path(member).name}"
        extracted.parent.mkdir(parents=True, exist_ok=True)
        if not extracted.exists():
            with zipfile.ZipFile(archive) as zf:
                extracted.write_bytes(zf.read(member))
        return name, extracted
    return name, Path(value)


def iter_xml_files(root: Path):
    """Yield XML paths in stable order while keeping directory traversal bounded."""
    for directory, dirs, files in os.walk(root):
        dirs.sort()
        for filename in sorted(files):
            if filename.lower().endswith(".xml"):
                yield Path(directory) / filename


def schema_info(con: duckdb.DuckDBPyConnection, path: Path) -> list[dict[str, str]]:
    rows = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
    return [{"name": r[0], "type": r[1]} for r in rows]


def canonical_columns(schema: list[dict[str, str]]) -> dict[str, str | None]:
    names = {c["name"] for c in schema}
    return {canonical: next((candidate for candidate in candidates if candidate in names), None)
            for canonical, candidates in ALIASES.items()}


def profile_one(path: Path, name: str, outdir: Path, sample_size: int | None, seed: int) -> dict[str, Any]:
    con = duckdb.connect(database=":memory:")
    schema = schema_info(con, path)
    cols = canonical_columns(schema)
    source = "read_parquet(" + "?" + ")"
    if sample_size:
        # DuckDB requires a literal sample size in USING SAMPLE.
        con.execute(f"CREATE TEMP TABLE prof AS SELECT * FROM {source} USING SAMPLE reservoir({int(sample_size)} ROWS) REPEATABLE ({int(seed)})", [str(path)])
        source = "prof"
    else:
        source = f"read_parquet('{str(path).replace(chr(39), chr(39)*2)}')"
    row_count = int(con.execute(f"SELECT count(*) FROM {source}").fetchone()[0])
    field_profiles: dict[str, Any] = {}
    dictionary_rows = []
    existing_types = {c["name"]: c["type"] for c in schema}
    for col in schema:
        name_q = qi(col["name"])
        base = con.execute(f"SELECT count({name_q}), count(DISTINCT {name_q}) FROM {source}").fetchone()
        nonnull, distinct = int(base[0]), int(base[1])
        profile: dict[str, Any] = {"type": col["type"], "nonnull": nonnull, "null": row_count - nonnull,
                                    "nonnull_pct": 100 * nonnull / row_count if row_count else None,
                                    "null_pct": 100 * (row_count - nonnull) / row_count if row_count else None,
                                    "distinct": distinct}
        if re.search(r"(INT|DOUBLE|FLOAT|DECIMAL|HUGEINT|BIGINT)", col["type"].upper()):
            q = con.execute(f"SELECT min({name_q}), max({name_q}), median({name_q}), quantile_cont({name_q},[0.01,0.05,0.25,0.5,0.75,0.95,0.99]) FROM {source}").fetchone()
            profile.update({"min": q[0], "max": q[1], "median": q[2], "quantiles": q[3]})
        if not re.search(r"(INT|DOUBLE|FLOAT|DECIMAL|HUGEINT|BIGINT|TIMESTAMP|DATE)", col["type"].upper()):
            profile["top_values"] = [{"value": r[0], "count": int(r[1])} for r in con.execute(
                f"SELECT cast({name_q} as varchar), count(*) n FROM {source} WHERE {name_q} IS NOT NULL GROUP BY 1 ORDER BY n DESC, 1 LIMIT 15"
            ).fetchall()]
        field_profiles[col["name"]] = profile
        desc = DESCRIPTIONS.get(col["name"], (col["name"].replace("_", " ").capitalize(), "unknown/source export", "unknown", "Description and semantic validity require source specification."))
        dictionary_rows.append({
            "dataset": name, "name": col["name"], "type": col["type"], "description": desc[0], "source": desc[1], "unit": desc[2],
            "nonnull": nonnull, "null": row_count - nonnull, "missing_pct": round(100 * (row_count - nonnull) / row_count, 4) if row_count else None,
            "validity_checks": "see dataset_profile.json anomalies", "reliability_notes": desc[3],
            "benchmark_suitability": benchmark_suitability(col["name"]),
        })

    canonical_counts: dict[str, Any] = {}
    for canonical, physical in cols.items():
        if physical is not None:
            canonical_counts[canonical] = {
                "physical_column": physical,
                "nonnull": field_profiles[physical]["nonnull"], "null": field_profiles[physical]["null"],
                "missing_pct": field_profiles[physical]["null_pct"], "distinct": field_profiles[physical]["distinct"],
            }
        else:
            canonical_counts[canonical] = {"physical_column": None, "availability": "unavailable"}

    anomalies: dict[str, Any] = {}
    def count_where(expr: str) -> int:
        return int(con.execute(f"SELECT count(*) FROM {source} WHERE {expr}").fetchone()[0])
    for key, expr in {
        "zero_surface": f"{qi(cols['surface_area'])}=0" if cols['surface_area'] else None,
        "negative_surface": f"{qi(cols['surface_area'])}<0" if cols['surface_area'] else None,
        "construction_year_before_1800": f"try_cast({qi(cols['construction_period'])} as integer)<1800" if cols['construction_period'] else None,
        "construction_year_after_2026": f"try_cast({qi(cols['construction_period'])} as integer)>2026" if cols['construction_period'] else None,
        "invalid_latitude": f"({qi(cols['latitude'])} < -90 OR {qi(cols['latitude'])} > 90)" if cols['latitude'] else None,
        "invalid_longitude": f"({qi(cols['longitude'])} < -180 OR {qi(cols['longitude'])} > 180)" if cols['longitude'] else None,
        "negative_epglnren": f"{qi(cols['epglnren'])}<0" if cols['epglnren'] else None,
        "negative_epglren": f"{qi(cols['epglren'])}<0" if cols['epglren'] else None,
        "negative_co2": f"{qi(cols['co2_emissions'])}<0" if cols['co2_emissions'] else None,
        "missing_issue_date": f"{qi(cols['issue_date'])} IS NULL" if cols['issue_date'] else None,
        "suspicious_issue_date_year": f"(year(try_cast({qi(cols['issue_date'])} as timestamp)) < 2000 OR year(try_cast({qi(cols['issue_date'])} as timestamp)) > 2026)" if cols['issue_date'] else None,
        "missing_cadastral_key": "(" + " OR ".join(
            f"{qi(cols[k])} IS NULL" + (f" OR try_cast({qi(cols[k])} as bigint)=0" if k != "comune_code" else "")
            for k in ("comune_code", "cadastral_sheet", "cadastral_parcel", "cadastral_subaltern") if cols[k]
        ) + ")" + (f" AND (coalesce({qi(cols['is_meta_estate'])},false)=false)" if cols.get("is_meta_estate") else "")
        if any(cols[k] for k in ("comune_code", "cadastral_sheet", "cadastral_parcel", "cadastral_subaltern")) else None,
    }.items():
        if expr:
            denominator = row_count
            if key == "missing_cadastral_key" and cols.get("is_meta_estate"):
                denominator = int(con.execute(f"select count(*) from {source} where coalesce({qi(cols['is_meta_estate'])},false)=false").fetchone()[0])
            anomaly_count = count_where(expr)
            anomalies[key] = {"count": anomaly_count, "pct": 100 * anomaly_count / denominator if denominator else None,
                              "denominator_rows": denominator,
                              "classification": "objective invalidity" if key.startswith(("negative_", "invalid_")) else "suspicious; review source semantics"}

    distributions: dict[str, Any] = {}
    for canonical in ("issue_date", "comune_code", "municipality", "istat_code", "xml_schema_version", "attestation_object_code", "dpr412_class_code", "property_type", "energy_class", "target_energy_class", "omi_zone"):
        physical = cols.get(canonical)
        if physical:
            group_expr = qi(physical)
            if canonical == "issue_date": group_expr = f"year(try_cast({group_expr} as timestamp))"
            distributions[canonical] = [{"value": r[0], "count": int(r[1])} for r in con.execute(
                f"SELECT {group_expr}, count(*) FROM {source} WHERE {group_expr} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 100"
            ).fetchall()]
        else:
            distributions[canonical] = None

    identity = identity_profile(con, source, cols, row_count)
    relationships = relationship_profile(con, source, cols)
    candidates = candidate_profile(con, source, cols, name)
    grouped_missingness = grouped_missingness_profile(con, source, cols)
    plots = make_plots(con, source, cols, field_profiles, outdir / "figures", name)
    all_rows = int(con.execute("select count(*) from read_parquet(?)", [str(path)]).fetchone()[0])
    con.close()
    return {
        "dataset": name, "path": str(path), "rows_profiled": row_count, "rows_in_file": all_rows,
        "sampled": sample_size is not None, "sample_size_requested": sample_size, "schema": schema,
        "canonical_attribute_availability": canonical_counts, "attribute_profiles": field_profiles,
        "distributions": distributions, "anomalies": anomalies, "identity": identity,
        "grouped_missingness": grouped_missingness, "relationships": relationships,
        "candidate_availability": candidates, "figures": plots,
        "representation_note": "APE certificates are not a random sample of the Italian building stock; these describe this Parquet export only.",
    }, dictionary_rows


def benchmark_suitability(name: str) -> str:
    if name in {"surface_area", "energy_class", "epglnren", "construction_period", "latitude", "longitude", "property_type", "effective_date", "data_decorrenza", "classe_energetica_ape", "epglnren_ape"}:
        return "Deterministic observed-value constraint/ranking; not full suitability."
    if name in {"commercial", "education", "mobility", "healthcare", "green", "sport", "omi_zone", "zona_omi"}:
        return "Derived location proxy; useful for ranking with provenance caveats."
    return "Context/provenance only or unavailable for a defensible suitability claim."


def first_col(cols: dict[str, str | None], key: str) -> str | None:
    return cols.get(key)


def identity_profile(con, source: str, cols: dict[str, str | None], rows: int) -> dict[str, Any]:
    meta_col = cols.get("is_meta_estate")
    sheet, parcel, sub, muni = (cols.get(k) for k in ("cadastral_sheet", "cadastral_parcel", "cadastral_subaltern", "comune_code"))
    class_col = cols.get("property_type")
    out: dict[str, Any] = {"unit_of_analysis": "export row; certificates are deduplicated/aggregated and cannot be reconstructed exactly from this file."}
    if meta_col:
        out["metaestate_rows"] = con.execute(f"select count(*) from {source} where {qi(meta_col)}=true").fetchone()[0]
        out["non_meta_rows"] = con.execute(f"select count(*) from {source} where {qi(meta_col)}=false or {qi(meta_col)} is null").fetchone()[0]
    if all((sheet, parcel, sub)):
        where = f"coalesce(try_cast({qi(sheet)} as bigint),0)<>0 and coalesce(try_cast({qi(parcel)} as bigint),0)<>0 and coalesce(try_cast({qi(sub)} as bigint),0)<>0"
        if meta_col: where += f" and coalesce({qi(meta_col)},false)=false"
        out["complete_cadastral_unit_rows"] = con.execute(f"select count(*) from {source} where {where}").fetchone()[0]
        base_rows = rows
        if meta_col:
            base_rows = int(con.execute(f"select count(*) from {source} where {qi(meta_col)}=false or {qi(meta_col)} is null").fetchone()[0])
        out["incomplete_or_zero_cadastral_rows"] = base_rows - out["complete_cadastral_unit_rows"]
        key = f"{qi(muni)}, {qi(sheet)}, {qi(parcel)}, {qi(sub)}" if muni else f"{qi(sheet)}, {qi(parcel)}, {qi(sub)}"
        out["duplicate_unit_keys"] = con.execute(f"select count(*) from (select {key},count(*) n from {source} where {where} group by {key} having n>1)").fetchone()[0]
        parcel_key = f"{qi(muni)}, {qi(sheet)}, {qi(parcel)}" if muni else f"{qi(sheet)}, {qi(parcel)}"
        out["units_per_parcel_quantiles"] = con.execute(f"select quantile_cont(n,[0.5,0.9,0.99]),max(n) from (select {parcel_key},count(*) n from {source} where {where} group by {parcel_key})").fetchone()[0:2]
        if class_col:
            out["parcels_with_multiple_use_categories"] = con.execute(f"select count(*) from (select {parcel_key},count(distinct {qi(class_col)}) n from {source} where {where} group by {parcel_key} having n>1)").fetchone()[0]
    out["certificates_per_cadastral_unit"] = "Unavailable: no certificate-level raw Parquet is present; current exports are already deduplicated."
    out["attribute_conflicts_within_unit"] = "Unavailable from current exports; requires ape_raw.parquet before unit deduplication."
    out["temporal_history_per_unit"] = "Unavailable from current exports; historical certificate rows were reduced."
    out["physical_building_reliability"] = "Municipality + sheet + parcel is not proof of one physical building; parcels can contain multiple structures."
    out["split_leakage_risk"] = "High if rows/certificates sharing parcel or constituent IDs are split independently; group splits by parcel and retain unit/APE linkage."
    return out


def relationship_profile(con, source: str, cols: dict[str, str | None]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    numeric_pairs = [("surface_area", "epglnren"), ("construction_period", "epglnren"), ("heating_energy_need", "surface_area"), ("cooling_energy_need", "surface_area")]
    for a, b in numeric_pairs:
        ca, cb = cols.get(a), cols.get(b)
        if ca and cb:
            xa = f"try_cast({qi(ca)} as double)" if a == "construction_period" else qi(ca)
            n, corr = con.execute(f"select count(*) filter(where {xa} is not null and {qi(cb)} is not null), corr({xa},{qi(cb)}) from {source}").fetchone()
            result[f"{a}_vs_{b}"] = {"n": int(n), "pearson_r": corr, "interpretation": "descriptive association; not causal"}
    cls, prop, ep = cols.get("energy_class"), cols.get("property_type"), cols.get("epglnren")
    for label, group_col in (("energy_class_by_property_type", prop), ("energy_class_counts", cls)):
        if cls and group_col:
            result[label] = [{"group": r[0], "energy_class": r[1], "count": int(r[2])} for r in con.execute(
                f"select cast({qi(group_col)} as varchar),cast({qi(cls)} as varchar),count(*) from {source} where {qi(cls)} is not null group by 1,2 order by 1,2"
            ).fetchall()[:500]]
    if prop and cols.get("surface_area"):
        pc, sc = qi(prop), qi(cols["surface_area"])
        result["surface_by_property_type"] = [{"property_type": r[0], "n": int(r[1]), "median_surface_m2": r[2],
            "p25_surface_m2": r[3], "p75_surface_m2": r[4]} for r in con.execute(
            f"select cast({pc} as varchar),count(*),median(try_cast({sc} as double)),quantile_cont(try_cast({sc} as double),.25),quantile_cont(try_cast({sc} as double),.75) from {source} where {pc} is not null and try_cast({sc} as double)>0 group by 1 order by 2 desc"
        ).fetchall()]
    if cols.get("comune_code") and cls:
        mc=qi(cols["comune_code"])
        result["energy_class_by_municipality"]=[{"municipality":r[0],"energy_class":r[1],"n":int(r[2])} for r in con.execute(
            f"select cast({mc} as varchar),cast({qi(cls)} as varchar),count(*) from {source} where {qi(cls)} is not null group by 1,2 order by 1,2"
        ).fetchall()[:1000]]
    return result


def grouped_missingness_profile(con, source: str, cols: dict[str, str | None]) -> dict[str, Any]:
    keys = ("issue_date", "comune_code", "property_type", "xml_schema_version")
    measures = ("surface_area", "energy_class", "epglnren", "latitude", "longitude")
    out = {}
    for key in keys:
        group_col = cols.get(key)
        if not group_col:
            out[key] = "unavailable"
            continue
        available = [m for m in measures if cols.get(m)]
        projections = ",".join(f"count(*) filter(where {qi(cols[m])} is null) as {qi(m + '_missing')}" for m in available)
        group_expr = f"year(try_cast({qi(group_col)} as timestamp))" if key == "issue_date" else qi(group_col)
        out[key] = con.execute(f"select {group_expr} as group_value,count(*) n,{projections} from {source} where {group_expr} is not null group by 1 order by n desc limit 100").fetchdf().to_dict(orient="records")
    return out


def candidate_profile(con, source: str, cols: dict[str, str | None], dataset: str) -> dict[str, Any]:
    surface, year, ep, energy = (cols.get(k) for k in ("surface_area", "construction_period", "epglnren", "energy_class"))
    output: dict[str, Any] = {"thresholds": "Dataset quantiles only; exploratory cut points, not normative requirements.", "combinations": []}
    if surface and year and ep:
        quantile_rows = con.execute(f"select quantile_cont({qi(surface)},[.25,.5,.75]),quantile_cont(try_cast({qi(year)} as double),[.25,.5,.75]),quantile_cont({qi(ep)},[.25,.5,.75]) from {source}").fetchone()
        qs, qy, qe = [list(x) if x else [] for x in quantile_rows]
        output["quantile_thresholds"] = {"surface_min": qs, "construction_year_min": qy, "epglnren_max": qe}
        for s in qs:
            for y in qy:
                for e in qe:
                    count = con.execute(f"select count(*) from {source} where {qi(surface)} >= ? and try_cast({qi(year)} as double) >= ? and {qi(ep)} <= ?", [s,y,e]).fetchone()[0]
                    output["combinations"].append({"surface_min_m2": s,"construction_year_min": y,"epglnren_max": e,"eligible_rows": int(count)})
    if energy:
        output["energy_class_counts"] = [{"class": r[0], "rows": int(r[1])} for r in con.execute(f"select cast({qi(energy)} as varchar),count(*) from {source} group by 1 order by 2 desc").fetchall()]
    output["unsupported_common_constraints"] = [k for k in ("heating_system_type", "has_heating", "climate_zone") if not cols.get(k)]
    output["interpretation"] = "Counts describe retained export rows; they are not counts of available, safe, vacant, or legally reusable buildings."
    return output


def _write_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields=list(rows[0]) if rows else []
    with path.open("w",newline="",encoding="utf-8") as f:
        if not fields:
            f.write("\n"); return
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def _write_bar_svg(path: Path, title: str, rows: list[tuple[str, float]], value_label: str = "") -> None:
    """Write a compact, dependency-free horizontal bar chart."""
    rows = rows[:20]
    width, left, top, row_h = 900, 300, 70, 26
    height = max(180, top + len(rows) * row_h + 35)
    maximum = max((max(0.0, float(value)) for _, value in rows), default=1.0) or 1.0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="20" y="32" font-size="20" font-family="sans-serif">{html.escape(title)}</text>']
    for i, (label, value) in enumerate(rows):
        y = top + i * row_h
        bar_w = max(0.0, float(value)) / maximum * 500
        parts.append(f'<text x="{left-10}" y="{y+16}" text-anchor="end" font-size="12" font-family="sans-serif">{html.escape(str(label)[:44])}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{bar_w:.2f}" height="17" fill="#3878a8"/>')
        parts.append(f'<text x="{left+bar_w+6:.2f}" y="{y+14}" font-size="12" font-family="sans-serif">{float(value):.1f}{html.escape(value_label)}</text>')
    parts.append('</svg>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(parts), encoding='utf-8')


NUMERIC_CONSTRAINT_FIELDS={"heated_usable_surface","cooled_usable_surface","construction_year","epglnren","epglren","co2_emissions","number_real_estate_units","xml_latitude","xml_longitude"}


def _quantile_value(con, table: str, field: str, quantile: float) -> float | None:
    if not 0 <= quantile <= 1: raise ValueError(f"Quantile must be in [0,1]: {quantile}")
    result=con.execute(f"select quantile_cont(try_cast({_qi(field)} as double), ?) from {table} where try_cast({_qi(field)} as double) is not null",[quantile]).fetchone()[0]
    return float(result) if result is not None else None


def _qi(name: str) -> str:
    return '"'+name.replace('"','""')+'"'


def _resolve_scenarios(con, table: str, rec_available: bool, config_path: Path | None) -> list[dict[str, Any]]:
    if config_path:
        config=json.loads(config_path.read_text(encoding="utf-8"))
        scenarios=config.get("scenarios",config) if isinstance(config,dict) else config
        if not isinstance(scenarios,list): raise ValueError("Constraint config must be a list or an object with a scenarios list")
        return scenarios
    scenarios=[]
    available={r[0] for r in con.execute(f"describe {table}").fetchall()}
    qs={field:{q:_quantile_value(con,table,field,q) for q in (.25,.5,.75)} for field in ("heated_usable_surface","construction_year","epglnren") if field in available}
    for field, quantiles in qs.items():
        for q,value in quantiles.items():
            if value is None: continue
            op="lte" if field=="epglnren" else "gte"
            scenarios.append({"scenario":f"{field}_{op}_q{int(q*100)}","constraints":[{"field":field,"op":op,"value":value}]})
    if "energy_class" in available:
        classes=con.execute(f"select energy_class,count(*) n from {table} where energy_class is not null group by 1 order by n,energy_class").fetchall()
        if classes:
            rare=str(classes[0][0]); common=str(classes[-1][0])
            scenarios += [{"scenario":"rare_energy_class","constraints":[{"field":"energy_class","op":"eq","value":rare}]},
                          {"scenario":"common_energy_class","constraints":[{"field":"energy_class","op":"eq","value":common}]}]
    rare_energy = str(classes[0][0]) if "energy_class" in available and classes else None
    rare_use = None
    rare_municipality = None
    for field,label in (("dpr412_class_code","use_code"),("municipality","municipality"),("istat_code","istat_code")):
        if field in available:
            values=con.execute(f"select cast({_qi(field)} as varchar),count(*) n from {table} where {_qi(field)} is not null group by 1 order by n desc,1").fetchall()
            if values:
                scenarios.append({"scenario":f"common_{label}","constraints":[{"field":field,"op":"eq","value":values[0][0]}]})
                if len(values)>1:
                    scenarios.append({"scenario":f"rare_{label}","constraints":[{"field":field,"op":"eq","value":values[-1][0]}]})
                    if field == "dpr412_class_code": rare_use=str(values[-1][0])
                    if field == "municipality": rare_municipality=str(values[-1][0])
    if "heated_usable_surface" in qs and "epglnren" in qs and qs["heated_usable_surface"][.75] is not None and qs["epglnren"][.5] is not None:
        scenarios.append({"scenario":"large_and_median_or_better_energy","constraints":[
            {"field":"heated_usable_surface","op":"gte","value":qs["heated_usable_surface"][.75]},
            {"field":"epglnren","op":"lte","value":qs["epglnren"][.5]}]})
    if "heated_usable_surface" in qs and "construction_year" in qs and "epglnren" in qs:
        vals=[qs[x][q] for x,q in (("heated_usable_surface",.75),("construction_year",.5),("epglnren",.25))]
        if all(x is not None for x in vals):
            scenarios.append({"scenario":"large_newer_low_ep","constraints":[
                {"field":"heated_usable_surface","op":"gte","value":vals[0]},
                {"field":"construction_year","op":"gte","value":vals[1]},
                {"field":"epglnren","op":"lte","value":vals[2]}]})
    if rare_energy is not None and rare_use is not None:
        rare_combo=[{"field":"energy_class","op":"eq","value":rare_energy},
                    {"field":"dpr412_class_code","op":"eq","value":rare_use}]
        if "heated_usable_surface" in qs and qs["heated_usable_surface"][.75] is not None:
            rare_combo.append({"field":"heated_usable_surface","op":"gte","value":qs["heated_usable_surface"][.75]})
        scenarios.append({"scenario":"rare_energy_use_large_surface_combination","constraints":rare_combo})
    if rare_use is not None and rare_municipality is not None:
        scenarios.append({"scenario":"rare_use_in_rare_municipality","constraints":[
            {"field":"dpr412_class_code","op":"eq","value":rare_use},
            {"field":"municipality","op":"eq","value":rare_municipality}]})
    if rec_available: scenarios.append({"scenario":"has_documented_recommendation","constraints":[{"field":"has_recommendation","op":"eq","value":True}]})
    return scenarios


def _profile_cadastral_identity(con, table: str, columns: set[str], outdir: Path) -> dict[str, Any]:
    unit_fields=["cadastral_municipality","cadastral_sheet","cadastral_parcel","cadastral_subaltern"]
    parcel_fields=unit_fields[:3]
    if not set(unit_fields).issubset(columns):
        return {"available":False,"reason":"complete cadastral unit fields are unavailable"}
    unit_tuple="("+",".join(_qi(x) for x in unit_fields)+")"
    parcel_tuple="("+",".join(_qi(x) for x in parcel_fields)+")"
    complete=" and ".join(f"{_qi(x)} is not null" for x in unit_fields)
    numeric_key_fields=unit_fields[1:]
    zero_pred=" or ".join(f"coalesce(try_cast({_qi(x)} as bigint)=0,false)" for x in numeric_key_fields)
    nonnumeric_pred=" or ".join(f"try_cast({_qi(x)} as bigint) is null" for x in numeric_key_fields)
    valid_complete=f"({complete}) and not ({zero_pred})"
    parcel_complete=" and ".join(f"{_qi(x)} is not null" for x in parcel_fields)
    total=int(con.execute(f"select count(*) from {table}").fetchone()[0])
    nonnull_rows=int(con.execute(f"select count(*) from {table} where {complete}").fetchone()[0])
    zero_coded_rows=int(con.execute(f"select count(*) from {table} where {complete} and ({zero_pred})").fetchone()[0])
    nonnumeric_key_rows=int(con.execute(f"select count(*) from {table} where {complete} and ({nonnumeric_pred})").fetchone()[0])
    complete_rows=int(con.execute(f"select count(*) from {table} where {valid_complete}").fetchone()[0])
    n_units=int(con.execute(f"select count(distinct {unit_tuple}) from {table} where {valid_complete}").fetchone()[0])
    n_parcels=int(con.execute(f"select count(distinct {parcel_tuple}) from {table} where {parcel_complete}").fetchone()[0])
    repeated=int(con.execute(f"select count(*) from (select {unit_tuple} from {table} where {valid_complete} group by 1 having count(*)>1)").fetchone()[0])
    cert_distribution=[{"certificates_per_unit":int(r[0]),"unit_count":int(r[1])} for r in con.execute(f"select n,count(*) from (select {unit_tuple},count(*) n from {table} where {valid_complete} group by 1) group by n order by n").fetchall()]
    units_per_parcel=[{"units_per_parcel":int(r[0]),"parcel_count":int(r[1])} for r in con.execute(f"select n,count(*) from (select {parcel_tuple},count(distinct {_qi('cadastral_subaltern')}) n from {table} where {parcel_complete} and not ({zero_pred}) group by 1) group by n order by n").fetchall()]
    conflicts=[]
    attrs=[x for x in ("dpr412_class_code","attestation_object_code","construction_year","heated_usable_surface","energy_class","xml_latitude","xml_longitude") if x in columns]
    for attr in attrs:
        n=int(con.execute(f"select count(*) from (select {unit_tuple} from {table} where {valid_complete} and {_qi(attr)} is not null group by 1 having count(distinct cast({_qi(attr)} as varchar))>1)").fetchone()[0])
        conflicts.append({"attribute":attr,"units_with_conflicting_nonnull_values":n,"unit_count":n_units,"pct_of_complete_units":100*n/n_units if n_units else None})
    multi_use=0
    if "dpr412_class_code" in columns:
        multi_use=int(con.execute(f"select count(*) from (select {parcel_tuple} from {table} where {parcel_complete} and not ({zero_pred}) and dpr412_class_code is not null group by 1 having count(distinct dpr412_class_code)>1)").fetchone()[0])
    temporal={"units_with_multiple_certificates":repeated}
    if "issue_date" in columns:
        temporal["units_with_multiple_issue_years"]=int(con.execute(f"select count(*) from (select {unit_tuple} from {table} where {valid_complete} and try_cast(issue_date as timestamp) is not null group by 1 having count(distinct year(try_cast(issue_date as timestamp)))>1)").fetchone()[0])
    if "energy_class" in columns:
        temporal["units_with_multiple_energy_classes"]=int(con.execute(f"select count(*) from (select {unit_tuple} from {table} where {valid_complete} and energy_class is not null group by 1 having count(distinct energy_class)>1)").fetchone()[0])
    rows=[{"distribution":"certificates_per_unit","value":x["certificates_per_unit"],"count":x["unit_count"]} for x in cert_distribution]
    rows += [{"distribution":"units_per_parcel","value":x["units_per_parcel"],"count":x["parcel_count"]} for x in units_per_parcel]
    _write_rows_csv(outdir/"cadastral_identity_distributions.csv",rows)
    _write_rows_csv(outdir/"cadastral_attribute_conflicts.csv",conflicts)
    return {"available":True,"certificates":total,"non_null_cadastral_key_certificates":nonnull_rows,
      "zero_coded_cadastral_key_certificates":zero_coded_rows,"nonnumeric_cadastral_key_certificates":nonnumeric_key_rows,
      "complete_cadastral_unit_certificates":complete_rows,
      "complete_unit_certificate_pct":100*complete_rows/total if total else None,"unique_cadastral_units":n_units,
      "unique_cadastral_parcels":n_parcels,"units_with_multiple_certificates":repeated,
      "units_per_parcel_distribution":units_per_parcel,"certificates_per_unit_distribution":cert_distribution,
      "parcels_with_multiple_dpr412_codes":multi_use,"conflicting_attributes":conflicts,"temporal_patterns":temporal,
      "physical_building_limitation":"A cadastral parcel may contain multiple physical buildings; a cadastral unit may also be only part of a building. Parcel/unit keys are grouping aids, not physical-building ground truth."}


def profile_raw_research(raw_path: Path, recommendations_path: Path | None, outdir: Path,
                         seed: int=20261016, sample_size: int | None=None,
                         constraint_config: Path | None=None) -> dict[str, Any]:
    """Research analyses that require linking certificate rows to intervention rows."""
    outdir.mkdir(parents=True,exist_ok=True); con=duckdb.connect(database=":memory:")
    raw_sql=str(raw_path).replace("'","''")
    con.execute(f"create view raw_source as select * from read_parquet('{raw_sql}')")
    if sample_size:
        con.execute(f"create temp table research_raw as select * from raw_source using sample reservoir({int(sample_size)} rows) repeatable ({int(seed)})")
    else: con.execute("create temp table research_raw as select * from raw_source")
    raw_cols={r[0] for r in con.execute("describe research_raw").fetchall()}
    has_recommendations=bool(recommendations_path and recommendations_path.exists())
    if has_recommendations:
        rec_sql=str(recommendations_path).replace("'","''")
        con.execute(f"create view rec_source as select * from read_parquet('{rec_sql}')")
        if "source_record_id" in raw_cols:
            con.execute("create temp table research_recs as select r.* from rec_source r where exists (select 1 from research_raw a where a.source_record_id=r.source_record_id)")
        else: con.execute("create temp table research_recs as select * from rec_source where false")
    else:
        con.execute("create temp table research_recs(source_record_id varchar, reachable_epglnren double)")

    rec_analysis: dict[str, Any] = {"available": has_recommendations, "certificates_with_recommendations": 0,
                                    "recommendation_coverage_pct": 0.0, "intervention_count_distribution": [],
                                    "intervention_code_distribution": [], "payback_summary": {},
                                    "individual_reachable_class_distribution": [], "individual_potential_reduction": {},
                                    "overall_reachable_class_distribution": [], "overall_potential_reduction": {},
                                    "overall_reachable_conflicting_certificates": 0}
    if has_recommendations and "source_record_id" in raw_cols:
        rec_columns={r[0] for r in con.execute("describe research_recs").fetchall()}
        rec_total=int(con.execute("select count(*) from research_raw").fetchone()[0])
        with_recs=int(con.execute("select count(distinct source_record_id) from research_recs").fetchone()[0])
        rec_analysis["certificates_with_recommendations"]=with_recs
        rec_analysis["recommendation_coverage_pct"]=100*with_recs/rec_total if rec_total else None
        rec_analysis["recommendation_rows"]=int(con.execute("select count(*) from research_recs").fetchone()[0])
        if "source_record_id" in rec_columns:
            rec_analysis["intervention_count_distribution"]=[{"interventions_per_certificate":int(r[0]),"certificates":int(r[1])} for r in con.execute("select n,count(*) from (select source_record_id,count(*) n from research_recs group by 1) group by 1 order by 1").fetchall()]
        for col,key in (("intervention_code","intervention_code_distribution"),("reachable_energy_class","individual_reachable_class_distribution"),("overall_reachable_energy_class","overall_reachable_class_distribution")):
            if col in rec_columns:
                rec_analysis[key]=[{"value":r[0],"rows":int(r[1])} for r in con.execute(f"select cast({_qi(col)} as varchar),count(*) from research_recs where {_qi(col)} is not null group by 1 order by 2 desc,1").fetchall()]
        if "payback_period_years" in rec_columns:
            r=con.execute("select count(try_cast(payback_period_years as double)),quantile_cont(try_cast(payback_period_years as double),[.05,.25,.5,.75,.95]),min(try_cast(payback_period_years as double)),max(try_cast(payback_period_years as double)) from research_recs").fetchone()
            rec_analysis["payback_summary"]={"n":int(r[0]),"p05":(r[1] or [None]*5)[0],"p25":(r[1] or [None]*5)[1],"median":(r[1] or [None]*5)[2],"p75":(r[1] or [None]*5)[3],"p95":(r[1] or [None]*5)[4],"min":r[2],"max":r[3]}
        def potential(column: str, result_key: str, baseline_column: str) -> None:
            if column not in rec_columns or baseline_column not in raw_cols: return
            baseline=f"try_cast(a.{_qi(baseline_column)} as double)"; reachable=f"try_cast(r.{_qi(column)} as double)"
            query=f"""select count(*) n,count(*) filter(where {baseline} > 0 and {reachable} is not null) as valid_n,
              quantile_cont({baseline}-{reachable},[.05,.25,.5,.75,.95]) abs_q,
              quantile_cont(100*({baseline}-{reachable})/nullif({baseline},0),[.05,.25,.5,.75,.95]) pct_q,
              count(*) filter(where {baseline}>0 and {reachable} is not null and {reachable}<{baseline}) improved
              from research_recs r join research_raw a using(source_record_id)
              where {baseline}>0 and {reachable} is not null"""
            result=con.execute(query).fetchone(); aq=result[2] or [None]*5; pq=result[3] or [None]*5
            rec_analysis[result_key]={"n_valid_intervention_or_certificate_rows":int(result[1] or 0),"n_lower_reachable_than_baseline":int(result[4] or 0),
              "absolute_reduction_kwh_m2_year_quantiles":{"p05":aq[0],"p25":aq[1],"median":aq[2],"p75":aq[3],"p95":aq[4]},
              "percentage_reduction_quantiles":{"p05":pq[0],"p25":pq[1],"median":pq[2],"p75":pq[3],"p95":pq[4]},
              "interpretation":"Modeled reachable performance, not observed renovation; individual interventions are not additive."}
        potential("reachable_epglnren","individual_potential_reduction","epglnren")
        if "overall_reachable_epglnren" in rec_columns and "epglnren" in raw_cols:
            conflict_sql="""select count(*) from (select source_record_id from research_recs where overall_reachable_epglnren is not null group by 1 having count(distinct overall_reachable_epglnren)>1)"""
            rec_analysis["overall_reachable_conflicting_certificates"]=int(con.execute(conflict_sql).fetchone()[0])
            con.execute("""create temp table unique_overall as select source_record_id,min(try_cast(overall_reachable_epglnren as double)) overall_reachable_epglnren from research_recs where overall_reachable_epglnren is not null group by 1 having count(distinct overall_reachable_epglnren)=1""")
            if "overall_reachable_energy_class" in rec_columns:
                con.execute("""create temp table overall_recs as select u.source_record_id,u.overall_reachable_epglnren,min(r.overall_reachable_energy_class) overall_reachable_energy_class from unique_overall u join research_recs r using(source_record_id) group by 1,2 having count(distinct r.overall_reachable_energy_class)<=1""")
                rec_analysis["overall_reachable_class_distribution"]=[{"value":r[0],"certificates":int(r[1])} for r in con.execute("select overall_reachable_energy_class,count(*) from overall_recs group by 1 order by 2 desc,1").fetchall()]
            else:
                con.execute("create temp table overall_recs as select source_record_id,overall_reachable_epglnren from unique_overall")
            base=f"try_cast(a.epglnren as double)"; reach="r.overall_reachable_epglnren"
            res=con.execute(f"select count(*),quantile_cont({base}-{reach},[.05,.25,.5,.75,.95]),quantile_cont(100*({base}-{reach})/nullif({base},0),[.05,.25,.5,.75,.95]),count(*) filter(where {reach}<{base}) from overall_recs r join research_raw a using(source_record_id) where {base}>0 and {reach} is not null").fetchone()
            aq=res[1] or [None]*5; pq=res[2] or [None]*5
            rec_analysis["overall_potential_reduction"]={"n_valid_certificates":int(res[0]),"n_lower_reachable_than_baseline":int(res[3]),
              "absolute_reduction_kwh_m2_year_quantiles":{"p05":aq[0],"p25":aq[1],"median":aq[2],"p75":aq[3],"p95":aq[4]},
              "percentage_reduction_quantiles":{"p05":pq[0],"p25":pq[1],"median":pq[2],"p75":pq[3],"p95":pq[4]},
              "interpretation":"Overall modeled potential, not observed renovation."}
        profile_rows=[]
        for key in ("intervention_code_distribution","individual_reachable_class_distribution","overall_reachable_class_distribution"):
            for item in rec_analysis.get(key,[]): profile_rows.append({"measure":key,"category":item.get("value"),"count":item.get("rows",item.get("certificates")),"value":None})
        for item in rec_analysis["intervention_count_distribution"]: profile_rows.append({"measure":"interventions_per_certificate","category":item["interventions_per_certificate"],"count":item["certificates"],"value":None})
        for key in ("individual_potential_reduction","overall_potential_reduction"):
            for stat,value in rec_analysis.get(key,{}).get("absolute_reduction_kwh_m2_year_quantiles",{}).items(): profile_rows.append({"measure":key+"_absolute_kwh_m2_year", "category":stat,"count":None,"value":value})
            for stat,value in rec_analysis.get(key,{}).get("percentage_reduction_quantiles",{}).items(): profile_rows.append({"measure":key+"_percentage", "category":stat,"count":None,"value":value})
        _write_rows_csv(outdir/"recommendation_analysis.csv",profile_rows)

    # Surface distributions, retaining source codes rather than undocumented category labels.
    surface_groups=[]
    group_specs=[("dpr412_class_code","dpr412_class_code"),("attestation_object_code","attestation_object_code"),
                 ("construction_decade","floor(try_cast(construction_year as double)/10)*10"),
                 ("municipality","municipality"),("istat_code","istat_code"),("energy_class","energy_class"),
                 ("real_estate_units","number_real_estate_units")]
    for label,expr in group_specs:
        needed={"dpr412_class_code":{"dpr412_class_code"},"attestation_object_code":{"attestation_object_code"},
                "construction_decade":{"construction_year"},"municipality":{"municipality"},"istat_code":{"istat_code"},
                "energy_class":{"energy_class"},"real_estate_units":{"number_real_estate_units"}}[label]
        if not needed.issubset(raw_cols) or "heated_usable_surface" not in raw_cols: continue
        for r in con.execute(f"select cast({expr} as varchar) group_value,count(*) n,quantile_cont(try_cast(heated_usable_surface as double),[.05,.25,.5,.75,.95]) qs,avg(try_cast(heated_usable_surface as double)) mean from research_raw where {expr} is not null and try_cast(heated_usable_surface as double)>0 group by 1 order by n desc,1").fetchall():
            qs=r[2] or [None]*5
            surface_groups.append({"grouping":label,"group_value":r[0],"n":int(r[1]),"mean_surface_m2":r[3],"p05_m2":qs[0],"p25_m2":qs[1],"median_m2":qs[2],"p75_m2":qs[3],"p95_m2":qs[4]})
    _write_rows_csv(outdir/"surface_distribution_by_group.csv",surface_groups)
    dpr_surface=[(f"{r['group_value']} (n={r['n']})", float(r["median_m2"]))
                 for r in surface_groups if r["grouping"]=="dpr412_class_code" and r["median_m2"] is not None]
    if dpr_surface:
        _write_bar_svg(outdir/"figures"/"raw_surface_median_by_dpr412.svg", "Median usable surface by DPR 412 code (m²)", dpr_surface)

    if {"dpr412_class_code","attestation_object_code","construction_year","energy_class","heated_usable_surface"}.issubset(raw_cols):
        joint=con.execute("""select dpr412_class_code,attestation_object_code,
          floor(try_cast(construction_year as double)/10)*10 construction_decade,energy_class,
          count(*) n,quantile_cont(try_cast(heated_usable_surface as double),[.25,.5,.75]) surface_quantiles
          from research_raw where dpr412_class_code is not null and attestation_object_code is not null
          and construction_year is not null and energy_class is not null and try_cast(heated_usable_surface as double)>0
          group by 1,2,3,4 order by n desc""").fetchall()
        joint_rows=[{"dpr412_class_code":r[0],"attestation_object_code":r[1],"construction_decade":r[2],"energy_class":r[3],"n":int(r[4]),"p25_m2":r[5][0],"median_m2":r[5][1],"p75_m2":r[5][2]} for r in joint]
    else: joint_rows=[]
    _write_rows_csv(outdir/"surface_intersections.csv",joint_rows)

    bundles={
        "basic_retrieval":["heated_usable_surface","dpr412_class_code","construction_year","energy_class"],
        "energy_aware_ranking":["heated_usable_surface","dpr412_class_code","construction_year","energy_class","epglnren","epglren","co2_emissions"],
        "spatial_retrieval":["heated_usable_surface","dpr412_class_code","construction_year","energy_class","xml_latitude","xml_longitude","municipality"],
    }
    surface_valid="try_cast(heated_usable_surface as double)>0" if "heated_usable_surface" in raw_cols else "false"
    lat_valid=("try_cast(xml_latitude as double) between -90 and 90 and try_cast(xml_longitude as double) between -180 and 180" if {"xml_latitude","xml_longitude"}.issubset(raw_cols) else "false")
    exprs={}
    for name,fields in bundles.items():
        terms=[]; missing_fields=[]
        for field in fields:
            if field not in raw_cols: missing_fields.append(field); terms.append("false")
            elif field=="heated_usable_surface": terms.append(surface_valid)
            elif field in {"xml_latitude","xml_longitude"}: terms.append(lat_valid)
            else: terms.append(f"{_qi(field)} is not null")
        exprs[name]=" and ".join(f"({x})" for x in terms)
    completeness=[]
    total=int(con.execute("select count(*) from research_raw").fetchone()[0])
    for bundle, condition in exprs.items():
        complete=int(con.execute(f"select count(*) from research_raw where {condition}").fetchone()[0])
        completeness.append({"bundle":bundle,"grouping":"all","group_value":"all","n_total":total,"n_complete":complete,"pct_complete":100*complete/total if total else None,
                             "unavailable_fields":";".join(f for f in bundles[bundle] if f not in raw_cols)})
        for group_name,field in (("issue_year","issue_date"),("building_use","dpr412_class_code"),("municipality","municipality")):
            if field not in raw_cols: continue
            group_expr=f"year(try_cast({_qi(field)} as timestamp))" if group_name=="issue_year" else _qi(field)
            for row in con.execute(f"select cast({group_expr} as varchar),count(*),count(*) filter(where {condition}) from research_raw where {group_expr} is not null group by 1 order by 2 desc").fetchall():
                completeness.append({"bundle":bundle,"grouping":group_name,"group_value":row[0],"n_total":int(row[1]),"n_complete":int(row[2]),"pct_complete":100*row[2]/row[1] if row[1] else None,"unavailable_fields":";".join(f for f in bundles[bundle] if f not in raw_cols)})
    retrofit_fields=["epglnren"]
    rec_ready=has_recommendations and {"source_record_id","reachable_epglnren"}.issubset({r[0] for r in con.execute("describe research_recs").fetchall()})
    if rec_ready:
        retrofit=int(con.execute("select count(*) from research_raw a where a.epglnren is not null and exists(select 1 from research_recs r where r.source_record_id=a.source_record_id and r.reachable_epglnren is not null)").fetchone()[0])
        bundles["retrofit_evaluation"]=["epglnren","recommendation with reachable_epglnren"]
        completeness.append({"bundle":"retrofit_evaluation","grouping":"all","group_value":"all","n_total":total,"n_complete":retrofit,"pct_complete":100*retrofit/total if total else None,"unavailable_fields":""})
        for group_name,field in (("issue_year","issue_date"),("building_use","dpr412_class_code"),("municipality","municipality")):
            if field not in raw_cols: continue
            group_expr=f"year(try_cast({_qi(field)} as timestamp))" if group_name=="issue_year" else _qi(field)
            for row in con.execute(f"""select cast({group_expr} as varchar),count(*),count(*) filter(where a.epglnren is not null and exists(select 1 from research_recs r where r.source_record_id=a.source_record_id and r.reachable_epglnren is not null))
                from research_raw a where {group_expr} is not null group by 1 order by 2 desc""").fetchall():
                completeness.append({"bundle":"retrofit_evaluation","grouping":group_name,"group_value":row[0],"n_total":int(row[1]),"n_complete":int(row[2]),"pct_complete":100*row[2]/row[1] if row[1] else None,"unavailable_fields":""})
    else:
        completeness.append({"bundle":"retrofit_evaluation","grouping":"all","group_value":"all","n_total":total,"n_complete":0,"pct_complete":0.0,"unavailable_fields":"ape_recommendations.parquet or reachable_epglnren unavailable"})
    _write_rows_csv(outdir/"joint_attribute_completeness.csv",completeness)
    all_bundle_rows=[r for r in completeness if r["grouping"]=="all"]
    if all_bundle_rows:
        _write_bar_svg(outdir/"figures"/"raw_joint_attribute_completeness.svg", "Joint attribute completeness (% of certificates)",
                       [(r["bundle"], float(r["pct_complete"] or 0)) for r in all_bundle_rows], "%")

    scenarios=_resolve_scenarios(con,"research_raw",rec_ready,constraint_config)
    cadastral_fields=["cadastral_municipality","cadastral_sheet","cadastral_parcel","cadastral_subaltern"]
    has_cad=set(cadastral_fields).issubset(raw_cols)
    distinct_unit_expr=("count(distinct case when "+" and ".join(f"a.{_qi(f)} is not null" for f in cadastral_fields)+" then concat_ws('|',"+",".join(f"a.{_qi(f)}" for f in cadastral_fields)+") end)" if has_cad else "0")
    candidates=[]
    for scenario in scenarios:
        constraints=scenario.get("constraints",[]); where=[];params=[];missing=[];near_terms=[];near_params=[]
        for spec in constraints:
            field=spec.get("field"); op=spec.get("op","eq"); value=spec.get("value")
            if field=="has_recommendation":
                if not rec_ready: where.append("false"); continue
                where.append("exists (select 1 from research_recs r where r.source_record_id=a.source_record_id)"); continue
            if field not in raw_cols: where.append("false");missing.append("true");continue
            physical=field; val=value
            if isinstance(val,dict) and "quantile" in val:
                val=_quantile_value(con,"research_raw",field,float(val["quantile"]))
            numeric=field in NUMERIC_CONSTRAINT_FIELDS
            col=f"try_cast(a.{_qi(physical)} as double)" if numeric else f"a.{_qi(physical)}"
            if op in {"gte","gt","lte","lt","eq"}:
                operator={"gte":">=","gt":">","lte":"<=","lt":"<","eq":"="}[op]
                where.append(f"{col} {operator} ?");params.append(val)
                if field=="heated_usable_surface": missing.append(f"({col} is null or {col}<=0)")
                elif field in {"xml_latitude","xml_longitude"}: missing.append("not (try_cast(a.xml_latitude as double) between -90 and 90 and try_cast(a.xml_longitude as double) between -180 and 180)")
                else: missing.append(f"(a.{_qi(physical)} is null"+(f" or {col} is null" if numeric else "")+")")
                if numeric and isinstance(val,(int,float)):
                    near_terms.append(f"abs({col}-?) <= ?");near_params.extend([val,max(1.0,abs(float(val))*.05)])
            elif op=="between" and isinstance(val,list) and len(val)==2:
                where.append(f"{col} between ? and ?");params.extend(val);missing.append(f"(a.{_qi(physical)} is null or {col} is null)")
            else: raise ValueError(f"Unsupported constraint operator/value: {op}/{val}")
        predicate=" and ".join(f"({p})" for p in where) or "true"
        n=int(con.execute(f"select count(*) from research_raw a where {predicate}",params).fetchone()[0])
        units=int(con.execute(f"select {distinct_unit_expr} from research_raw a where {predicate}",params).fetchone()[0]) if has_cad else 0
        missing_pred=" or ".join(f"({x})" for x in missing) or "false"
        missing_n=int(con.execute(f"select count(*) from research_raw a where {missing_pred}").fetchone()[0])
        near_pred=" or ".join(f"({x})" for x in near_terms) or "false"
        near_n=int(con.execute(f"select count(*) from research_raw a where {near_pred}",near_params).fetchone()[0]) if near_terms else 0
        candidates.append({"scenario":scenario.get("scenario","unnamed"),"constraints":json.dumps(constraints,ensure_ascii=False),
            "candidate_universe":total,"eligible_certificates":n,"eligible_distinct_cadastral_units":units,
            "records_missing_required_info":missing_n,"selectivity_pct":100*n/total if total else None,
            "near_threshold_certificates":near_n,"threshold_basis":"configurable explicit value or full/raw-sample quantile; exploratory, not normative"})
    _write_rows_csv(outdir/"candidate_availability.csv",candidates)
    if candidates:
        _write_bar_svg(outdir/"figures"/"raw_candidate_availability.svg", "Eligible certificates under structured constraints",
                       [(f"{r['scenario']} (n={r['eligible_certificates']})", float(r["selectivity_pct"] or 0)) for r in candidates], "%")

    cadastral_identity=_profile_cadastral_identity(con,"research_raw",raw_cols,outdir)
    result={"sampled":sample_size is not None,"rows_profiled":total,"recommendation_table_available":has_recommendations,
        "recommendation_rows_profiled":int(con.execute("select count(*) from research_recs").fetchone()[0]),
        "surface_group_rows":len(surface_groups),"surface_intersection_rows":len(joint_rows),
        "completeness_bundles":completeness,"candidate_scenarios":candidates,"recommendation_analysis":rec_analysis,
        "cadastral_identity_analysis":cadastral_identity,
        "recommendation_scope_note":"Intervention rows are linked by source_record_id; separate interventions are not added together."}
    con.close();return result


def make_plots(con, source: str, cols: dict[str, str | None], field_profiles: dict[str, Any], figdir: Path, dataset: str) -> list[str]:
    figdir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    def bar(name: str, title: str, values: list[tuple[str, float]]) -> None:
        if not values: return
        width, height, left, top, chart_w, chart_h = 960, 540, 260, 80, 650, 390
        max_v = max(v for _,v in values) or 1
        step = min(34, chart_h / len(values))
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                 '<rect width="100%" height="100%" fill="white"/>', f'<text x="30" y="38" font-size="22" font-family="sans-serif">{title} ({dataset})</text>']
        for i,(label,value) in enumerate(values):
            y=top+i*step
            label = str(label)[:35].replace('&','&amp;').replace('<','&lt;')
            parts += [f'<text x="{left-10}" y="{y+15}" text-anchor="end" font-size="12" font-family="sans-serif">{label}</text>',
                      f'<rect x="{left}" y="{y}" width="{chart_w*value/max_v:.2f}" height="{max(8,step-3):.2f}" fill="#3878a8"/>',
                      f'<text x="{left+chart_w*value/max_v+6:.2f}" y="{y+15}" font-size="11" font-family="sans-serif">{value:,.0f}</text>']
        parts.append('</svg>')
        target=figdir/f'{dataset}_{name}.svg'; target.write_text('\n'.join(parts),encoding='utf-8'); files.append(str(target))

    for key, title, canonical in (("energy_class", "Energy class distribution", "energy_class"),
                                  ("property_type", "Building use classification", "property_type"),
                                  ("issue_year", "Certificate issue year", "issue_date"),
                                  ("municipality", "Municipality coverage", "comune_code")):
        col=cols.get(canonical)
        if not col: continue
        expr=f"year(try_cast({qi(col)} as timestamp))" if canonical=="issue_date" else f"cast({qi(col)} as varchar)"
        values=[(str(r[0]),float(r[1])) for r in con.execute(f"select {expr},count(*) from {source} where {expr} is not null group by 1 order by 2 desc limit 20").fetchall()]
        bar(key,title,values)
    for canonical, slug, title in (("surface_area","surface","Usable surface distribution"),("epglnren","epglnren","EPgl,nren distribution")):
        col=cols.get(canonical)
        if not col: continue
        vals=[r[0] for r in con.execute(f"select {qi(col)} from {source} where {qi(col)} is not null and {qi(col)}>=0").fetchall()]
        if not vals: continue
        lo,hi=min(vals),max(vals)
        if hi==lo: edges=[lo,hi+1]; bins=[len(vals)]
        else:
            nb=30; edges=[lo+(hi-lo)*i/nb for i in range(nb+1)]; bins=[0]*nb
            for val in vals: bins[min(nb-1,int((val-lo)/(hi-lo)*nb))]+=1
        bar(slug,title,[(f'{edges[i]:.1f}–{edges[i+1]:.1f}',float(v)) for i,v in enumerate(bins)])

    # Missingness is shown for every exported column (truncated only for readability).
    missing = sorted(((k, float(v["null_pct"] or 0)) for k,v in field_profiles.items()), key=lambda x:x[1], reverse=True)[:25]
    bar("missingness", "Attribute missingness (%)", missing)

    # Coordinate density grid is an explicitly descriptive spatial coverage plot.
    lat, lon = cols.get("latitude"), cols.get("longitude")
    if lat and lon:
        grid = con.execute(f"""select floor(try_cast({qi(lon)} as double)*20)/20 x,
            floor(try_cast({qi(lat)} as double)*20)/20 y, count(*) n
            from {source} where try_cast({qi(lat)} as double) between -90 and 90
            and try_cast({qi(lon)} as double) between -180 and 180 group by 1,2""").fetchall()
        if grid:
            max_n=max(int(r[2]) for r in grid); parts=['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="560" viewBox="0 0 760 560">','<rect width="100%" height="100%" fill="white"/>',f'<text x="20" y="30" font-size="20" font-family="sans-serif">Coordinate density grid ({dataset}, 0.05° bins)</text>']
            for x,y,n in grid:
                px=50+(float(x)+180)/360*650; py=500-(float(y)+90)/180*420; opacity=.15+.8*int(n)/max_n
                parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="{max(2,min(18,3+int(n/max_n*12)))}" fill="#b33b35" fill-opacity="{opacity:.2f}"/>')
            parts.append('</svg>'); target=figdir/f'{dataset}_coordinate_density.svg'; target.write_text('\n'.join(parts),encoding='utf-8'); files.append(str(target))

    # A bounded deterministic DuckDB sample supports a readable relationship plot.
    surf, ep=cols.get("surface_area"),cols.get("epglnren")
    if surf and ep:
        pts=con.execute(f"select * from (select try_cast({qi(surf)} as double) x,try_cast({qi(ep)} as double) y from {source} where try_cast({qi(surf)} as double)>0 and try_cast({qi(ep)} as double)>=0) using sample reservoir(1500 rows) repeatable (20261016)").fetchall()
        pts=[(float(x),float(y)) for x,y in pts if x is not None and y is not None]
        if pts:
            x0,x1=min(x for x,_ in pts),max(x for x,_ in pts); y0,y1=min(y for _,y in pts),max(y for _,y in pts)
            dx=max(x1-x0,1e-9);dy=max(y1-y0,1e-9)
            parts=['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="560" viewBox="0 0 760 560">','<rect width="100%" height="100%" fill="white"/>',f'<text x="20" y="30" font-size="20" font-family="sans-serif">Surface vs EPgl,nren ({dataset}); n={len(pts)}</text>']
            parts += [f'<circle cx="{75+(x-x0)/dx*640:.2f}" cy="{490-(y-y0)/dy*420:.2f}" r="2" fill="#3878a8" fill-opacity="0.45"/>' for x,y in pts]
            parts += [f'<text x="300" y="545" font-size="13">Surface (m²)</text>',f'<text x="5" y="280" font-size="13">EPgl,nren</text>','</svg>']
            target=figdir/f'{dataset}_surface_vs_epglnren.svg';target.write_text('\n'.join(parts),encoding='utf-8');files.append(str(target))

    # Current exports have no intervention-level recommendations. Emit an explicit
    # artifact instead of implying that retrofit outcomes were measured.
    if "recommend" not in dataset.lower():
        target=figdir/f'{dataset}_retrofit_recommendations.svg'
        target.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="180"><rect width="100%" height="100%" fill="white"/><text x="24" y="55" font-size="20" font-family="sans-serif">Retrofit recommendation coverage ({dataset})</text><text x="24" y="105" font-size="16" font-family="sans-serif">Intervention-level recommendations require a linked recommendation dataset.</text></svg>',encoding='utf-8');files.append(str(target))
    return files


def xml_inventory(root: Path, sample_size: int, seed: int) -> dict[str, Any]:
    rng=random.Random(seed); selected: list[Path]=[]; n=0; file_years=Counter()
    for p in iter_xml_files(root):
        n+=1
        if n % 50000 == 0:
            print(f"XML inventory: discovered {n:,} files", flush=True)
        match=re.match(r"(\d{4})_",p.name)
        if match: file_years[match.group(1)]+=1
        if len(selected)<sample_size: selected.append(p)
        else:
            j=rng.randrange(n)
            if j<sample_size: selected[j]=p
    result={"files_discovered":n,"filename_prefix_year_counts":dict(sorted(file_years.items())),"xml_sample_size_requested":sample_size}
    try:
        from data.metadata.ape_extraction import parse_ape_xml, APEParseError
    except Exception as exc:
        result["sample_parse_status"]={"unavailable":str(exc)}
        return result
    stats={"parsed":0,"failed":0,"versions":Counter(),"attestation_object_codes":Counter(),"dpr412_codes":Counter(),"issue_years":Counter(),"failure_reasons":Counter()}
    for p in selected:
        try:
            raw,_=parse_ape_xml(p)
            stats["parsed"]+=1
            for key,counter in (("xml_schema_version","versions"),("attestation_object_code","attestation_object_codes"),("dpr412_class_code","dpr412_codes")):
                if raw.get(key) is not None: stats[counter][str(raw[key])]+=1
            date=raw.get("issue_date")
            if date and len(str(date))>=4: stats["issue_years"][str(date)[:4]]+=1
        except Exception as exc:
            stats["failed"]+=1
            message=str(exc)
            if "Invalid bytes in character encoding" in message:
                reason="invalid_bytes_in_declared_encoding"
            elif "xml_syntax_or_encoding" in message:
                reason="xml_syntax_or_encoding_other"
            else:
                reason=message.split(":",1)[0]
            stats["failure_reasons"][reason]+=1
    for key in ("versions","attestation_object_codes","dpr412_codes","issue_years","failure_reasons"):
        stats[key]=dict(stats[key])
    stats["sample_size"] = len(selected)
    stats["failure_rate_wilson_95"] = wilson(stats["failed"],len(selected))
    stats["warning"] = "Random file sample is not a complete parse count; no extrapolation to all source files is made."
    result["sample_parse_status"]=stats
    return result


def write_readiness_csv(path: Path, raw_available: bool=False, recommendations_available: bool=False) -> None:
    rows=[]
    for use_case, feasibility, fields, missing in USE_CASES:
        rows.append({"use_case":use_case,"requirement":"Building selection for stated public-interest use",
                     "required_fields":fields,"availability":feasibility,
                     "evaluation_feasibility":"Partially evaluable as deterministic filtering/ranking of available proxies; not as legal/functional suitability.",
                     "missing_information":missing,"recommended_treatment":"Report constraint satisfaction on observed fields; label proxy and unknown requirements explicitly."})
    rows += [
        {"use_case":"Generic MURENA retrieval","requirement":"Surface, construction year, energy class, EPgl,nren and mapped municipality constraints","required_fields":"surface_area; construction_period; energy_class; epglnren; comune_code","availability":"Certificate-level fields available" if raw_available else "Application export fields only","evaluation_feasibility":"Deterministic filtering and ranking against observed certificate/export values.","missing_information":"Codes and zero placeholders require review; geographic/legal suitability and certificate history linkage remain incomplete.","recommended_treatment":"Use raw APE records for certificate-level filtering and grouping-aware splits; preserve nulls and source linkage." if raw_available else "Benchmark at row/export level first; use raw APE records once generated and preserve nulls."},
        {"use_case":"Retrofit screening","requirement":"Rank on baseline energy indicators","required_fields":"energy_class; epglnren; epglren; heating_energy_need; envelope fields","availability":"Certificate-level recommendations available" if recommendations_available else "Partially evaluable; no intervention-level recommendation dataset","evaluation_feasibility":"Baseline and recommended reachable outcomes can be compared descriptively where present; this is not observed retrofit performance." if recommendations_available else "Baseline ranking is possible for available measurements.","missing_information":"Retrofit costs, intervention compatibility and observed post-retrofit outcomes absent.","recommended_treatment":"Keep individual recommendation rows separate; do not add potential outcomes or call them observed renovations." if recommendations_available else "Do not score retrofit plans or combine recommendation outcomes until intervention-level data and assumptions are available."},
        {"use_case":"Territorial accessibility","requirement":"Rank by existing amenity proximity scores","required_fields":"latitude; longitude; healthcare; education; mobility; green; sport; commercial","availability":"Directly evaluable as stored enrichment scores","evaluation_feasibility":"Can compare deterministic rankings on existing scores.","missing_information":"Coordinate provenance/confidence absent in snapshots; population demand, transit travel times and POI completeness absent.","recommended_treatment":"Treat as snapshot-specific proximity proxies; validate against dated source POIs."},
    ]
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def write_reports(outdir: Path, profiles: list[dict[str, Any]], dictionary_rows: list[dict[str, Any]], xml_report: dict[str, Any] | None, sample_size: int | None, seed: int, input_specs: list[str], research: dict[str, Any] | None=None) -> None:
    outdir.mkdir(parents=True,exist_ok=True)
    extraction_report = None
    raw_input = next((Path(spec.split("=",1)[1]) for spec in input_specs if spec.split("=",1)[0].lower() in {"raw","ape_raw"}),None)
    if raw_input is not None:
        reconciliation_path=(raw_input if raw_input.is_dir() else raw_input.parent)/"ape_data_quality_report.json"
        if reconciliation_path.exists():
            extraction_report=json.loads(reconciliation_path.read_text(encoding="utf-8"))
    payload={"generated_utc":datetime.now(timezone.utc).isoformat(),"configuration":{"inputs":input_specs,"sample_size":sample_size,"seed":seed},
             "xml_inventory":xml_report,"source_population_note":"XML file count is distinct from successfully parsed certificates, unique cadastral units, and derived metaestates.",
             "extraction_reconciliation":extraction_report,
             "datasets":{p["dataset"]:p for p in profiles},"raw_research_analyses":research,
             "missing_dataset_files":[name for name,patterns in (("ape_raw.parquet",("raw","ape_raw")),("ape_recommendations.parquet",("recommendations","ape_recommendations"))) if not any(p["dataset"].lower() in patterns for p in profiles)]}
    (outdir/"dataset_profile.json").write_text(json.dumps(sanitize_json(payload),indent=2,ensure_ascii=False,allow_nan=False,default=json_default),encoding="utf-8")
    with (outdir/"data_dictionary.csv").open("w",newline="",encoding="utf-8") as f:
        fields=list(dictionary_rows[0]) if dictionary_rows else ["dataset","name","type","description","source","unit","nonnull","null","missing_pct","validity_checks","reliability_notes","benchmark_suitability"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(dictionary_rows)
    raw_available=any(p["dataset"].lower() in {"raw","ape_raw"} for p in profiles)
    rec_available=any(p["dataset"].lower() in {"recommendations","ape_recommendations"} for p in profiles)
    write_readiness_csv(outdir/"benchmark_readiness.csv",raw_available,rec_available)
    (outdir/"data_quality_report.md").write_text(render_quality(profiles,xml_report,sample_size,research,extraction_report),encoding="utf-8")
    (outdir/"benchmark_feasibility_report.md").write_text(render_feasibility(profiles,xml_report,research,extraction_report),encoding="utf-8")


def json_default(value: Any):
    if hasattr(value,"item"): return value.item()
    if hasattr(value,"isoformat"): return value.isoformat()
    if isinstance(value, float) and math.isnan(value): return None
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def sanitize_json(value: Any):
    if isinstance(value,dict): return {str(k):sanitize_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [sanitize_json(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value): return None
    if hasattr(value,"item"):
        try: return sanitize_json(value.item())
        except (ValueError,TypeError): pass
    return value


def render_quality(profiles: list[dict[str, Any]], xml: dict[str, Any] | None, sample_size: int | None, research: dict[str, Any] | None=None, extraction: dict[str, Any] | None=None) -> str:
    lines=["# APE dataset quality report", "", f"Analysis mode: {'deterministic sample ('+str(sample_size)+' rows)' if sample_size else 'full available Parquet snapshots'}.", "",
           "## Source and export composition", ""]
    if xml:
        lines += [f"- XML files discovered by directory walk: **{xml['files_discovered']:,}**.",
                  (f"- Extraction reconciliation: {extraction['attempted']:,} attempted; {extraction['successfully_extracted']:,} extracted; {extraction['recovered']:,} normalized; {extraction['failed']:,} failed; {extraction['not_yet_processed']:,} pending. Processing complete: {extraction['processing_complete']}." if extraction else "- Full-corpus parse totals are not linked to this profile; only the sample below was parsed here."),
                  f"- Sampled XML parse result: `{json.dumps(xml.get('sample_parse_status',{}),ensure_ascii=False)}`.", ""]
        if extraction and extraction.get("failure_reasons"):
            lines.append("- Extraction failure reasons: " + "; ".join(f"{k}: {v:,}" for k,v in extraction["failure_reasons"].items()) + ".")
        if extraction:
            lines.append(f"- Duplicate source IDs: {extraction.get('duplicate_source_identifiers','unavailable')}; repeated non-null APE identifier groups: {extraction.get('duplicate_certificate_identifier_count','unavailable')}. Repeated APE IDs are not treated as duplicate source files.")
    else: lines += ["- XML root was not supplied; source-file counts and XML sample checks were not run.", ""]
    for p in profiles:
        raw_dataset=p["dataset"].lower() in {"raw","ape_raw"}
        raw_identity=(research or {}).get("cadastral_identity_analysis",{}) if raw_dataset else {}
        complete_units=(raw_identity.get("complete_cadastral_unit_certificates") if raw_identity.get("available") else p["identity"].get("complete_cadastral_unit_rows","unavailable"))
        incomplete_units=(p["rows_in_file"]-complete_units if raw_dataset and isinstance(complete_units,int) else p["identity"].get("incomplete_or_zero_cadastral_rows","unavailable"))
        repeated_units=(raw_identity.get("units_with_multiple_certificates") if raw_identity.get("available") else p["identity"].get("duplicate_unit_keys","unavailable"))
        lines += [f"### {p['dataset']}", "",f"- Rows in file: {p['rows_in_file']:,}; rows profiled: {p['rows_profiled']:,}; sampled: {p['sampled']}.",
                  f"- Columns: {len(p['schema'])}.", f"- Metaestate rows: {p['identity'].get('metaestate_rows','unavailable')}; non-meta rows: {p['identity'].get('non_meta_rows','unavailable')}.",
                  f"- Complete cadastral unit rows (excluding zero-coded/missing fields): {complete_units}.",
                  f"- Rows with incomplete or zero-coded cadastral fields: {incomplete_units}.",
                  (f"- Unit keys with repeated certificates: {repeated_units}; these include repeated historical certificates and are not duplicate source rows." if raw_dataset else f"- Duplicate unit keys after export: {repeated_units}."),
                  ("- This is certificate-level source extraction; source paths and hashes are retained." if raw_dataset else "- This Parquet dataset is an application export and does not retain all certificates or source-level provenance."),"", "#### Selected quality anomalies", ""]
        for key,value in p["anomalies"].items(): lines.append(f"- {key}: {value['count']:,} ({value['pct']:.2f}%; {value['classification']}).")
        if not p["anomalies"]: lines.append("- No anomaly checks were applicable to the available columns.")
        for key in ("issue_date", "comune_code", "municipality", "istat_code", "xml_schema_version", "attestation_object_code", "dpr412_class_code", "property_type", "energy_class"):
            vals=p["distributions"].get(key)
            if vals is not None:
                summary=", ".join(f"{v['value']}: {v['count']:,}" for v in vals[:12]) or "no non-null values"
                lines.append(f"- {key} distribution (top values): {summary}.")
        missing=sorted(((k,v["null_pct"]) for k,v in p["attribute_profiles"].items()),key=lambda x:(x[1] is not None, x[1] or 0),reverse=True)[:10]
        lines += ["", "#### Most-missing attributes", ""]+[f"- `{k}`: {v:.2f}% missing." for k,v in missing if v is not None]
        lines += ["", "#### Missing fields", ""]+[f"- `{k}`" for k,v in p["canonical_attribute_availability"].items() if v.get("physical_column") is None]
        combos=p["candidate_availability"].get("combinations",[])
        if combos:
            counts=[x["eligible_rows"] for x in combos]
            lines += ["", "#### Exploratory candidate-space counts", "",
                      f"- Evaluated {len(combos)} combinations of within-dataset quartile cut points for minimum surface, minimum construction year and maximum EPgl,nren.",
                      f"- Eligible export rows range from {min(counts):,} to {max(counts):,}; {sum(v==0 for v in counts)} combinations yield no rows.",
                      "- These are empirical availability probes, not normative requirements or counts of vacant/usable buildings."]
        lines.append("")
    if research:
        basics=next((x for x in research["completeness_bundles"] if x["bundle"]=="basic_retrieval" and x["grouping"]=="all"),None)
        energy=next((x for x in research["completeness_bundles"] if x["bundle"]=="energy_aware_ranking" and x["grouping"]=="all"),None)
        spatial=next((x for x in research["completeness_bundles"] if x["bundle"]=="spatial_retrieval" and x["grouping"]=="all"),None)
        retrofit=next((x for x in research["completeness_bundles"] if x["bundle"]=="retrofit_evaluation" and x["grouping"]=="all"),None)
        lines += ["## Certificate-level research analyses", "",f"- Raw certificate rows profiled: {research['rows_profiled']:,}; recommendations profiled: {research['recommendation_rows_profiled']:,}.",
                  f"- Basic retrieval joint completeness: {basics['n_complete']:,}/{basics['n_total']:,} ({basics['pct_complete']:.2f}%)." if basics else "- Basic retrieval completeness unavailable.",
                  f"- Energy-aware joint completeness: {energy['n_complete']:,}/{energy['n_total']:,} ({energy['pct_complete']:.2f}%)." if energy else "- Energy-aware completeness unavailable.",
                  f"- Spatial joint completeness: {spatial['n_complete']:,}/{spatial['n_total']:,} ({spatial['pct_complete']:.2f}%)." if spatial else "- Spatial completeness unavailable.",
                  f"- Retrofit joint completeness: {retrofit['n_complete']:,}/{retrofit['n_total']:,} ({retrofit['pct_complete']:.2f}%)." if retrofit else "- Retrofit completeness unavailable.",
                  f"- Surface grouping rows: {research['surface_group_rows']:,}; multidimensional use/object/decade/class intersections: {research['surface_intersection_rows']:,}.",
                  "- Supporting detail is in `surface_distribution_by_group.csv`, `surface_intersections.csv`, `joint_attribute_completeness.csv`, `candidate_availability.csv`, `recommendation_analysis.csv`, `cadastral_identity_distributions.csv`, and `cadastral_attribute_conflicts.csv`. DPR and attestation values remain source codes; no undocumented labels are inferred.",""]
        rec=research.get("recommendation_analysis",{})
        identity=research.get("cadastral_identity_analysis",{})
        if identity.get("available"):
            temporal=identity.get("temporal_patterns",{})
            conflict_summary=", ".join(f"{x['attribute']}: {x['units_with_conflicting_nonnull_values']:,}" for x in identity.get("conflicting_attributes",[]))
            lines += [f"- Cadastral identity: {identity['complete_cadastral_unit_certificates']:,} certificates have complete source unit keys excluding numeric zero placeholders, representing {identity['unique_cadastral_units']:,} distinct units and {identity['unique_cadastral_parcels']:,} distinct parcels.",
                      f"- {identity['zero_coded_cadastral_key_certificates']:,} certificates have all key fields present but at least one numeric sheet/parcel/subaltern code of zero; these source values are preserved and excluded from grouping. {identity['nonnumeric_cadastral_key_certificates']:,} have alphanumeric/non-numeric codes retained as source strings; these counts can overlap.",
                      f"- Repeated certificates occur for {identity['units_with_multiple_certificates']:,} unit keys; {identity['parcels_with_multiple_dpr412_codes']:,} parcels have multiple DPR 412 codes. These are not duplicate source records and parcels are not physical-building ground truth.",
                      f"- Units with multiple recorded issue years: {temporal.get('units_with_multiple_issue_years','unavailable')}; with multiple energy classes: {temporal.get('units_with_multiple_energy_classes','unavailable')}.",
                      f"- Units with conflicting non-null attributes (by attribute): {conflict_summary or 'none detected'}.",
                      "- Detailed distributions and conflicts: `cadastral_identity_distributions.csv` and `cadastral_attribute_conflicts.csv`.",""]
        if rec.get("available"):
            payback=rec.get("payback_summary",{})
            overall=rec.get("overall_potential_reduction",{})
            lines += [f"- Certificates with at least one recommendation: {rec.get('certificates_with_recommendations',0):,} ({(rec.get('recommendation_coverage_pct') or 0):.2f}%).",
                      f"- Individual interventions per certificate distribution: {len(rec.get('intervention_count_distribution',[]))} observed count values; intervention code frequencies are in `recommendation_analysis.csv`.",
                      f"- Payback period among reported values: n={payback.get('n',0):,}, median={payback.get('median')} years; reachable classes and individual/overall modeled reductions are in `dataset_profile.json` and `recommendation_analysis.csv`.",
                      f"- Overall reachable EPgl,nren has conflicting values across recommendation rows for {rec.get('overall_reachable_conflicting_certificates',0):,} certificates; those certificates are excluded from the certificate-level overall reduction summary.",
                      "- Reachable values are modeled potential, not observed renovation outcomes; individual intervention outcomes are not additive.",""]
    lines += ["## Interpretation limits", "", "Observed values and confidence intervals describe the available APE/export records, not a random sample of Italian buildings. Workspace and ZIP snapshots have different schemas and counts and are profiled separately. Zero cadastral identifiers may represent legacy missing-value filling; they are not treated as valid identifiers in unit-level completeness. Anomalous records are reported, not removed.", ""]
    lines += ["## Existing identity and aggregation logic", "", "The inspected production code deduplicates only complete municipality + sheet + parcel + subaltern keys, retains incomplete-key rows, and chooses the newest effective date after first-address consistency filtering. This reduces historical certificate records and can discard conflicting address rows, so exported unit counts are not certificate counts. Metaestates are generated from same municipality/sheet/parcel groups with at least two members only when normalized addresses match and coordinates are complete and within 50 m. This is a conservative screen, not proof that a parcel is one physical building. `aggregation_methods` records summed area, surface-weighted energy indicators, an estimated weighted-mode energy class, and derived/aggregated scores.",
              ("The raw certificate analysis above retains this history and quantifies repeated keys and attribute conflicts. Legacy application export aggregates remain application estimates, not certified building-level values; row and metaestate counts are listed above." if research else "The current application exports have already reduced certificate history; a certificate-level conflict/history audit requires `ape_raw.parquet`."), ""]
    return "\n".join(lines)


def render_feasibility(profiles: list[dict[str, Any]], xml: dict[str, Any] | None, research: dict[str, Any] | None=None, extraction: dict[str, Any] | None=None) -> str:
    raw_available=any(p["dataset"].lower() in {"raw","ape_raw"} for p in profiles)
    rec_available=any(p["dataset"].lower() in {"recommendations","ape_recommendations"} for p in profiles)
    lines=["# MURENA benchmark feasibility assessment", "", "## What can be evaluated now", "",
           "The available application Parquet rows support deterministic retrieval/ranking experiments for observed, non-null fields such as surface, issue date, mapped use category, energy class, EPgl,nren, coordinates, OMI zone, and stored POI scores. This measures constraint handling and ranking over an already filtered export. It does not establish building availability, legal reuse, structural condition, or suitability for a public service.","",
           "## Public-interest use cases", ""]
    for use,feas,fields,missing in USE_CASES:
        lines += [f"### {use}","",f"- Readiness: **{feas}**.",f"- Observable candidate features: {fields}.",f"- Required additions: {missing}",""]
    lines += ["## Data representation, bias, and leakage", "",
              ("The workspace snapshot contains 36,328 rows; the repository ZIP contains a distinct 89,200-row snapshot with renamed columns and different coverage. Both report one municipality code (Torino). These are city-specific application exports, not representative national samples. The certificate-level raw dataset separately accounts for the XML extraction population; the smaller application exports reflect filtering, deduplication and metaestate aggregation." if raw_available else "The workspace snapshot contains 36,328 rows; the repository ZIP contains a distinct 89,200-row snapshot with renamed columns and different coverage. Both report one municipality code (Torino). These are city-specific application exports, not representative national samples. The current exports cannot count successfully parsed APEs because they have already undergone geographic filtering, deduplication and metaestate aggregation. The XML directory contains many more files than the retained rows; do not infer parse success or retention from row counts."), "",
              ("The raw certificate audit measures repeated cadastral unit keys, multiple DPR 412 codes per parcel, and temporal energy-class changes. Parcels remain uncertain proxies for physical buildings; keep all certificates linked by complete unit/parcel keys on the same side of any benchmark split. A parcel can contain multiple buildings and multiple unit-use categories." if raw_available else "Parcels are not reliable physical-building identifiers by themselves. Candidate splits should group by municipality + cadastral parcel when complete, retain unit and source-file links, and keep all historical certificates for linked units on one side of a split. The current export has already reduced temporal history, so it cannot support a certificate-level leakage audit."),"",
              "## Retrofit feasibility", "",
              (f"Certificate-level extraction is available with {research['rows_profiled']:,} rows and {research['recommendation_rows_profiled']:,} individual recommendation rows in the profiled scope. Joint baseline-plus-recommendation completeness is reported separately. Reachable values are modeled potential, not observed post-renovation performance; separate interventions are not additive." if raw_available and rec_available and research else "No certificate-level recommendations were available in this profiling input. Retrofit selection can be stratified by baseline energy performance only; intervention selection, payback distributions, and achievable reductions remain unassessed."),"",
              "## Highest-value additional data", "",
              ("1. Enrich certificate and recommendation records with linked ownership/availability, cost, observed renovation outcomes and building-level identity." if raw_available and rec_available else "1. Generate and retain `ape_raw.parquet` and `ape_recommendations.parquet` with stable certificate IDs and source provenance."),
              ("2. Add corrected-coordinate provenance/confidence and a validated physical-building link; the raw XML coordinates and cadastral strings are preserved, but do not identify buildings with certainty." if raw_available else "2. Preserve municipality/sheet/parcel/subaltern as strings and distinguish absent IDs from zero; add source coordinate provenance and confidence."),
              "3. Add building-level structural safety, accessibility compliance, legal ownership/availability, zoning, vacancy, floor plans, hazardous-material and renovation-cost data.",
              "4. Add dated POI source data, public-transport travel times, population/service demand and authoritative building-stock totals for representativeness checks.","",
              "## Synthetic data", "",
              "Synthetic records are not needed for Benchmark v1 and must not be mixed into empirical candidate or outcome evaluation. They could later support disclosed stress tests for rare constraint combinations or software robustness when real observations are sparse, with generated records kept in a separate partition and never presented as observed buildings or ground truth.","",
              "## Recommended MURENA Benchmark v1 scope", "",
              ("Start with certificate-level retrieval and ranking on source-observed surface, DPR code, year, energy class and energy indicators. Use municipality and coordinate fields where valid, and recommendation rows only for potential retrofit screening. Group related certificates by cadastral unit/parcel for splits and report unit-level versus certificate-level counts separately. Public-service suitability remains out of scope without building-level safety, accessibility, availability and demand data." if raw_available else "Start with deterministic retrieval and ranking over observed attributes in the Torino export: usable surface, construction period, APE energy class, EPgl,nren, mapped use, location, OMI zone and POI scores. Keep benchmark claims limited to that already-filtered candidate universe."),
              "Evaluate constraint satisfaction, candidate counts, completeness-sensitive coverage, and grouping-aware splits. Do not generate natural-language benchmark queries or synthetic candidate records in this phase.","",
              "## XML source inventory", ""]
    if xml:
        if extraction:
            lines.append(f"XML files discovered: {xml['files_discovered']:,}; full extraction attempted {extraction['attempted']:,}, extracted {extraction['successfully_extracted']:,}, failed {extraction['failed']:,}, pending {extraction['not_yet_processed']:,}. Complete: {extraction['processing_complete']}.")
        else:
            lines.append(f"XML files discovered: {xml['files_discovered']:,}. A deterministic random sample of {xml.get('sample_parse_status',{}).get('sample_size',0)} files was parsed for schema/object/use-code coverage only. This is not a full-corpus parse count.")
    else: lines.append("No XML root was provided; XML source inventory remains pending.")
    lines += ["", "## Statistical interpretation", "", "All proportions and correlations in the profile are descriptive of these Parquet exports. Wilson intervals are included only for sampled XML parse outcomes where applicable; they do not correct the non-random source population. Correlations are associations and must not be interpreted causally.",""]
    if research:
        counts=[x["eligible_certificates"] for x in research["candidate_scenarios"]]
        lines += ["## Structured candidate availability", "",f"Evaluated {len(counts)} configured/quantile-based scenarios; eligible counts range from {min(counts):,} to {max(counts):,}, with {sum(n==0 for n in counts)} empty-result scenarios. See `candidate_availability.csv`; quantiles are exploratory thresholds and not regulatory cutoffs.",""] if counts else []
    return "\n".join(lines)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet",action="append",required=True,metavar="NAME=PATH[::ZIP_MEMBER]")
    parser.add_argument("--xml-root",type=Path)
    parser.add_argument("--xml-sample-size",type=int,default=100)
    parser.add_argument("--output-dir",type=Path,default=REPO_ROOT/"backend/research/ape_profile")
    parser.add_argument("--sample-size",type=int,help="Deterministic reservoir sample per Parquet input; omit for full available Parquet scans")
    parser.add_argument("--constraint-config",type=Path,help="Optional JSON file defining structured candidate constraint scenarios")
    parser.add_argument("--seed",type=int,default=20261016)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    resolved=[input_spec(spec,args.output_dir) for spec in args.parquet]
    profiles=[]; dictionary=[]
    for (name,path),spec in zip(resolved,args.parquet):
        print(f"Profiling {name}: {path}",flush=True)
        profile,rows=profile_one(path,name,args.output_dir,args.sample_size,args.seed)
        profile["path"] = spec.split("=",1)[1]
        profiles.append(profile);dictionary.extend(rows)
    research=None
    raw_spec=next(((n,p) for n,p in resolved if n.lower() in {"raw","ape_raw"}),None)
    rec_spec=next(((n,p) for n,p in resolved if n.lower() in {"recommendations","ape_recommendations"}),None)
    if raw_spec:
        research=profile_raw_research(raw_spec[1],rec_spec[1] if rec_spec else None,args.output_dir,args.seed,args.sample_size,args.constraint_config)
        raw_profile=next((p for p in profiles if p["dataset"].lower() in {"raw","ape_raw"}),None)
        if raw_profile and research.get("cadastral_identity_analysis",{}).get("available"):
            identity=research["cadastral_identity_analysis"]
            raw_profile["identity"].update({
                "unit_of_analysis":"one row per successfully parsed source certificate; historical certificates retained",
                "complete_cadastral_unit_rows":identity["complete_cadastral_unit_certificates"],
                "incomplete_or_zero_cadastral_rows":raw_profile["rows_in_file"]-identity["complete_cadastral_unit_certificates"],
                "duplicate_unit_keys":identity["units_with_multiple_certificates"],
                "certificates_per_cadastral_unit":identity["certificates_per_unit_distribution"],
                "attribute_conflicts_within_unit":identity["conflicting_attributes"],
                "temporal_history_per_unit":identity["temporal_patterns"],
                "parcels_with_multiple_use_categories":identity["parcels_with_multiple_dpr412_codes"],
                "physical_building_reliability":identity["physical_building_limitation"],
                "split_leakage_risk":"Group all historical certificates by complete nonzero cadastral unit/parcel keys; parcel identifiers can still group multiple physical buildings.",
            })
    xml=xml_inventory(args.xml_root,args.xml_sample_size,args.seed) if args.xml_root else None
    write_reports(args.output_dir,profiles,dictionary,xml,args.sample_size,args.seed,args.parquet,research)
    print(f"Wrote profiling artifacts to {args.output_dir}",flush=True)


if __name__=="__main__": main()
