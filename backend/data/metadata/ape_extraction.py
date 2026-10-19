"""Standalone, auditable APE2015 XML extraction.

This module intentionally has no dependency on MURENA's geospatial configuration.
It preserves source codes and certificate-level observations; interpretation and
application-specific enrichment belong to later pipeline stages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from lxml import etree
import pyarrow as pa
import pyarrow.parquet as pq

LOG = logging.getLogger("ape_extraction")
NS = {"a": "http://www.csi.it/sicee/siceeweb/xml/xmlapecompleto2015/data"}

RAW_COLUMNS = [
    "source_filename", "source_record_id", "source_sha256", "parse_status",
    "source_encoding_declared", "source_encoding_used", "potentially_lossy",
    "source_repaired_byte_count", "parser_warning_count", "ape_id", "xml_schema_version",
    "issue_date", "expiration_date", "cadastral_municipality", "cadastral_sheet",
    "cadastral_parcel", "cadastral_subaltern", "address", "house_number",
    "municipality", "istat_code", "xml_latitude", "xml_longitude",
    "construction_year", "building_typology_code", "dpr412_class_code",
    "attestation_object_code", "number_real_estate_units", "floor",
    "heated_usable_surface", "cooled_usable_surface", "heated_volume", "climate_zone",
    "energy_class", "epglnren", "epglren", "co2_emissions", "heating_energy_need",
    "cooling_energy_need", "envelope_winter_quality_code", "envelope_summer_quality_code",
    "overall_reachable_energy_class", "overall_reachable_epglnren",
    "main_energy_carrier", "energy_carrier_codes_json", "energy_consumptions_json",
    "heating_system_code", "heating_system_description",
    "heating_installation_year", "dhw_system_code", "dhw_system_description",
    "dhw_installation_year", "heating_service_present", "dhw_service_present",
    "cooling_service_present", "renewable_pv_consumption", "renewable_solar_thermal_consumption",
    "heating_nominal_power", "dhw_nominal_power", "opaque_envelope_area",
    "transparent_envelope_area", "building_surface_dispersing", "building_shape_ratio",
    "solar_gain_to_useful_surface_ratio", "thermal_inertia_index", "net_building_surface",
    "net_building_volume", "gross_dispersing_surface", "gross_conditioned_volume",
    "gross_heated_volume", "gross_cooled_volume",
]
STRING_COLUMNS = set(RAW_COLUMNS) - {
    "xml_latitude", "xml_longitude", "construction_year", "number_real_estate_units",
    "heated_usable_surface", "cooled_usable_surface", "heated_volume", "epglnren",
    "epglren", "co2_emissions", "heating_energy_need", "cooling_energy_need",
    "renewable_pv_consumption", "renewable_solar_thermal_consumption",
    "heating_nominal_power", "dhw_nominal_power", "opaque_envelope_area",
    "transparent_envelope_area", "building_surface_dispersing", "building_shape_ratio",
    "solar_gain_to_useful_surface_ratio", "thermal_inertia_index", "net_building_surface",
    "net_building_volume", "gross_dispersing_surface", "gross_conditioned_volume",
    "gross_heated_volume", "gross_cooled_volume", "parser_warning_count", "source_repaired_byte_count",
}
BOOL_COLUMNS = {"heating_service_present", "dhw_service_present", "cooling_service_present", "potentially_lossy"}
INT_COLUMNS = {"parser_warning_count", "source_repaired_byte_count"}
NUMERIC_COLUMNS = set(RAW_COLUMNS) - STRING_COLUMNS - BOOL_COLUMNS
REC_COLUMNS = ["source_record_id", "ape_id", "source_filename", "intervention_code",
               "intervention_description", "major_renovation_code", "payback_period_years",
               "reachable_energy_class", "reachable_epglnren", "overall_reachable_energy_class",
               "overall_reachable_epglnren"]


class APEParseError(ValueError):
    """A source file could not be parsed completely and safely."""


def _local_xpath(root: etree._Element, path: str) -> list[etree._Element]:
    """Evaluate an XPath with namespace-independent element names."""
    return root.xpath(path)


def _first(root: etree._Element, *paths: str) -> str | None:
    for path in paths:
        vals = _local_xpath(root, path)
        for val in vals:
            if isinstance(val, etree._Element):
                value = "".join(val.itertext()).strip()
            else:
                value = str(val).strip()
            if value:
                return value
    return None


def _number(root: etree._Element, *paths: str) -> float | None:
    value = _first(root, *paths)
    if value is None:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _flag(root: etree._Element, *paths: str) -> bool | None:
    value = _first(root, *paths)
    if value is None:
        return None
    v = value.strip().lower()
    if v in {"1", "true"}: return True
    if v in {"0", "false"}: return False
    return None


def _strict_xml(path: Path) -> etree._Element:
    raw = path.read_bytes()
    return _strict_xml_bytes(raw)


def _strict_xml_bytes(raw: bytes) -> etree._Element:
    try:
        # Parse bytes, allowing XML declaration/BOM to select the actual encoding.
        parser = etree.XMLParser(recover=False, huge_tree=True, resolve_entities=False,
                                 load_dtd=False, no_network=True)
        root = etree.fromstring(raw, parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise APEParseError(f"xml_syntax_or_encoding: {exc}") from exc
    if not isinstance(root.tag, str):
        raise APEParseError("xml_has_no_document_element")
    return root


def _parse_xml_bytes(raw: bytes) -> tuple[etree._Element, dict[str, Any]]:
    """Parse strictly, then apply observed CP1252 repair without dropping bytes.

    The declared encoding and selected decoding are retained as provenance. No
    `errors=ignore`, replacement decoding, or lxml recovery is used here.
    """
    declaration = re.search(rb"<\?xml[^>]*encoding\s*=\s*['\"]([^'\"]+)", raw[:512], re.I)
    declared = declaration.group(1).decode("ascii", "replace") if declaration else None
    try:
        root = _strict_xml_bytes(raw)
        return root, {"parse_status": "strict", "source_encoding_declared": declared,
                      "source_encoding_used": declared or "xml_auto_detect", "potentially_lossy": False,
                      "source_repaired_byte_count": 0,"parser_warning_count": 0}
    except APEParseError as strict_error:
        if "Invalid bytes in character encoding" not in str(strict_error):
            raise
        try:
            # Preserve every valid UTF-8 sequence and map only invalid UTF-8
            # bytes as Windows-1252. This handles mixed legacy/UTF-8 content and
            # avoids whole-file CP1252 mojibake (e.g. m³ becoming mÂ³).
            surrogate_text = raw.decode("utf-8", errors="surrogateescape")
            repaired = 0; decoded_parts=[]
            for char in surrogate_text:
                code=ord(char)
                if 0xDC80 <= code <= 0xDCFF:
                    byte=bytes([code-0xDC00])
                    decoded_parts.append(byte.decode("cp1252", errors="strict")); repaired+=1
                else: decoded_parts.append(char)
            decoded = "".join(decoded_parts)
        except (UnicodeError, LookupError) as exc:
            raise APEParseError(f"encoding_recovery_failed: utf8_cp1252_invalid_bytes: {exc}") from strict_error
        # Only the declaration is changed; valid UTF-8 and repaired byte values are retained.
        decoded = re.sub(r"(<\?xml\s+[^?]*encoding\s*=\s*)['\"][^'\"]+['\"]",
                         r'\1"UTF-8"', decoded, count=1, flags=re.I)
        try:
            root = _strict_xml_bytes(decoded.encode("utf-8"))
        except APEParseError as exc:
            raise APEParseError(f"encoding_recovery_failed: {exc}") from strict_error
        return root, {"parse_status": "normalized_utf8_cp1252_bytes_inferred", "source_encoding_declared": declared,
                      "source_encoding_used": "UTF-8 plus CP1252 mapping for invalid bytes (inferred)",
                      "potentially_lossy": False, "source_repaired_byte_count": repaired,"parser_warning_count": 0}


def _cadastral(root: etree._Element) -> tuple[str | None, str | None, str | None, str | None]:
    nodes = _local_xpath(root, "//*[local-name()='datiCatastali']")
    if not nodes:
        return (None, None, None, None)
    n = nodes[0]
    def child(name: str) -> str | None:
        return _first(n, f"./*[local-name()='{name}']")
    municipality = child("codiceCatastale") or child("comune")
    sheet, parcel = child("foglio"), child("particella")
    sub = []
    for name in ("subDA", "subA"):
        val = _first(n, f".//*[local-name()='subalterni']/*[local-name()='{name}']")
        if val is not None and val not in sub:
            sub.append(val)  # Preserve leading zeros and the exact source value.
    return municipality, sheet, parcel, ",".join(sub) if sub else None


def _system(root: etree._Element, section: str) -> tuple[str | None, str | None, str | None, float | None]:
    base = f"//*[local-name()='datiImpianti']/*[local-name()='{section}']"
    return (
        _first(root, f"{base}/*[local-name()='impianto']/*[local-name()='tipoImpianto']"),
        _first(root, f"{base}/*[local-name()='impianto']/*[local-name()='descrizioneImpianto']"),
        _first(root, f"{base}/*[local-name()='impianto']/*[local-name()='annoInstallazione']"),
        _number(root, f"{base}/*[local-name()='impianto']/*[local-name()='potenzaNominale']"),
    )


def parse_ape_xml(path: str | Path, source_filename: str | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse one certificate and its intervention rows; errors are never swallowed."""
    path = Path(path)
    source_bytes = path.read_bytes()
    root, parse_provenance = _parse_xml_bytes(source_bytes)
    if etree.QName(root).localname not in {"documento", "ape2015"} and not _local_xpath(root, "//*[local-name()='datiAttestato']"):
        raise APEParseError("unrecognized_ape_document")
    if not _local_xpath(root, "//*[local-name()='datiAttestato']"):
        raise APEParseError("ape_attestation_section_missing")
    cad_muni, sheet, parcel, sub = _cadastral(root)
    heating = _system(root, "climatizzazioneInvernale")
    dhw = _system(root, "produzioneACS")
    rec_class = _first(root, "//*[local-name()='raccomandazioni']/*[local-name()='classificazione']/*[local-name()='classeEnergetica']")
    rec_ep = _number(root, "//*[local-name()='raccomandazioni']/*[local-name()='classificazione']/*[local-name()='epglnren']")
    rel = "//*[local-name()='datiCalcolo']/*[local-name()='datiGenerali']"
    # APE2015 national files commonly store these values in datiCalcolo/datiGenerali.
    filename_id = source_filename or path.name
    ape_identifier = _first(root, "//*[local-name()='datiAttestato']/*[local-name()='codiceIdentificativo']")
    record_id = hashlib.sha256((filename_id + "\0" + (ape_identifier or "")).encode()).hexdigest()
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    raw: dict[str, Any] = {k: None for k in RAW_COLUMNS}
    raw.update({
        "source_filename": filename_id, "source_record_id": record_id, "source_sha256": source_digest,
        **parse_provenance, "ape_id": ape_identifier,
        "xml_schema_version": _first(root, "//*[local-name()='ape2015']/*[local-name()='info']/*[local-name()='versione']", "//*[local-name()='info']/*[local-name()='versione']"),
        "issue_date": _first(root, "//*[local-name()='dataEmissione']"),
        "expiration_date": _first(root, "//*[local-name()='datiAttestato']/*[local-name()='dataScadenza']"),
        "cadastral_municipality": cad_muni, "cadastral_sheet": sheet,
        "cadastral_parcel": parcel, "cadastral_subaltern": sub,
        "address": _first(root, f"{rel}/*[local-name()='indirizzo']", "//*[local-name()='datiGenerali']/*[local-name()='indirizzo']"),
        "house_number": _first(root, f"{rel}/*[local-name()='civico']", "//*[local-name()='civico']"),
        "municipality": _first(root, f"{rel}/*[local-name()='comune']"),
        "istat_code": _first(root, f"{rel}/*[local-name()='codiceISTAT']"),
        "xml_latitude": _number(root, f"{rel}/*[local-name()='latitudineGIS']"),
        "xml_longitude": _number(root, f"{rel}/*[local-name()='longitudineGIS']"),
        "construction_year": _number(root, "//*[local-name()='datiIdentificativi']/*[local-name()='annoCostruzione']", "//*[local-name()='annoCostruzione']"),
        "building_typology_code": _first(root, "//*[local-name()='datiGenerali']/*[local-name()='datiExtra']/*[local-name()='tipologiaEdilizia']", "//*[local-name()='tipologiaEdilizia']"),
        "dpr412_class_code": _first(root, "//*[local-name()='classificazioneDPR412']"),
        "attestation_object_code": _first(root, "//*[local-name()='oggettoAttestato']"),
        "number_real_estate_units": _number(root, "//*[local-name()='numeroUnitaImmobiliari']"),
        "floor": _first(root, "//*[local-name()='datiIdentificativi']/*[local-name()='piano']", "//*[local-name()='datiFabbricato']/*[local-name()='piano']"),
        "heated_usable_surface": _number(root, "//*[local-name()='superficieUtileRiscaldata']"),
        "cooled_usable_surface": _number(root, "//*[local-name()='superficieUtileRaffrescata']"),
        "heated_volume": _number(root, "//*[local-name()='datiFabbricato']/*[local-name()='volumeRiscaldato']"),
        "climate_zone": _first(root, f"{rel}/*[local-name()='zonaClimatica']"),
        "energy_class": _first(root, "//*[local-name()='prestazioneEnergeticaGlobale']/*[local-name()='classificazione']/*[local-name()='classeEnergetica']"),
        "epglnren": _number(root, "//*[local-name()='prestazioneEnergeticaGlobale']/*[local-name()='classificazione']/*[local-name()='epglnren']"),
        "overall_reachable_energy_class": rec_class, "overall_reachable_epglnren": rec_ep,
        "epglren": _number(root, "//*[local-name()='prestazioneImpianti']/*[local-name()='epglren']"),
        "co2_emissions": _number(root, "//*[local-name()='prestazioneImpianti']/*[local-name()='emissioniCO2']"),
        "heating_energy_need": _number(root, "//*[local-name()='datiFabbricato']/*[local-name()='ephnd']"),
        "cooling_energy_need": _number(root, "//*[local-name()='datiFabbricato']/*[local-name()='epcnd']"),
        "envelope_winter_quality_code": _first(root, "//*[local-name()='prestazioneEnergeticaFabbricato']/*[local-name()='inverno']"),
        "envelope_summer_quality_code": _first(root, "//*[local-name()='prestazioneEnergeticaFabbricato']/*[local-name()='estate']"),
        "heating_system_code": heating[0], "heating_system_description": heating[1], "heating_installation_year": heating[2],
        "dhw_system_code": dhw[0], "dhw_system_description": dhw[1], "dhw_installation_year": dhw[2],
        "heating_service_present": _flag(root, "//*[local-name()='serviziEnergeticiPresenti']/*[local-name()='climatizzazioneInvernale']"),
        "dhw_service_present": _flag(root, "//*[local-name()='serviziEnergeticiPresenti']/*[local-name()='produzioneAcquaCaldaSanitaria']"),
        "cooling_service_present": _flag(root, "//*[local-name()='serviziEnergeticiPresenti']/*[local-name()='climatizzazioneEstiva']"),
        "heating_nominal_power": heating[3], "dhw_nominal_power": dhw[3],
        "opaque_envelope_area": _number(root, "//*[local-name()='superficieOpacaTotale']"),
        "transparent_envelope_area": _number(root, "//*[local-name()='superficieVetrataTotale']"),
        "building_surface_dispersing": _number(root, "//*[local-name()='datiFabbricato']/*[local-name()='superficieDisperdente']"),
        "building_shape_ratio": _number(root, "//*[local-name()='datiFabbricato']/*[local-name()='rapportoSV']"),
        "solar_gain_to_useful_surface_ratio": _number(root, "//*[local-name()='datiFabbricato']/*[local-name()='rapportoAsolAsupUtile']"),
        "thermal_inertia_index": _number(root, "//*[local-name()='datiFabbricato']/*[local-name()='yie']"),
        "net_building_surface": _number(root, "//*[local-name()='fabbricato']/*[local-name()='superficieNetta']"),
        "net_building_volume": _number(root, "//*[local-name()='fabbricato']/*[local-name()='volumeNetto']"),
        "gross_dispersing_surface": _number(root, "//*[local-name()='fabbricato']/*[local-name()='superficieLordaDisperdente']"),
        "gross_conditioned_volume": _number(root, "//*[local-name()='fabbricato']/*[local-name()='volumeLordoClimatizzato']"),
        "gross_heated_volume": _number(root, "//*[local-name()='datiIdentificativi']/*[local-name()='volumeLordoRiscaldato']"),
        "gross_cooled_volume": _number(root, "//*[local-name()='datiIdentificativi']/*[local-name()='volumeLordoRaffrescato']"),
    })
    carriers = []
    energy_consumptions: dict[str, dict[str, str | None]] = {}
    for node in _local_xpath(root, "//*[local-name()='prestazioneImpianti']/*"):
        amount = node.xpath("string(./*[local-name()='consumoAnnuo'])").strip()
        if amount:
            unit = node.xpath("string(./*[local-name()='consumoAnnuoUM'])").strip() or None
            energy_consumptions[etree.QName(node).localname] = {"consumoAnnuo": amount, "consumoAnnuoUM": unit}
            try: carriers.append((float(amount.replace(',', '.')), etree.QName(node).localname))
            except ValueError: pass
    if carriers:
        raw["main_energy_carrier"] = max(carriers)[1]
    raw["energy_consumptions_json"] = json.dumps(energy_consumptions, ensure_ascii=False, sort_keys=True) if energy_consumptions else None
    carrier_codes = [v.strip() for v in _local_xpath(root, "//*[local-name()='vettoriEnergeticiUtilizzati']/*[local-name()='vettore']/text()") if str(v).strip()]
    raw["energy_carrier_codes_json"] = json.dumps(carrier_codes, ensure_ascii=False) if carrier_codes else None
    interventions = []
    for node in _local_xpath(root, "//*[local-name()='raccomandazioni']/*[local-name()='interventoRaccomandato']"):
        interventions.append({
            "source_record_id": record_id, "ape_id": raw["ape_id"], "source_filename": filename_id,
            "intervention_code": _first(node, "./*[local-name()='codice']"),
            "intervention_description": _first(node, "./*[local-name()='tipoInterventoRaccomandato']"),
            "major_renovation_code": _first(node, "./*[local-name()='ristrutturazioneImportante']"),
            "payback_period_years": _number(node, "./*[local-name()='tempoRitornoInvestimento']"),
            "reachable_energy_class": _first(node, "./*[local-name()='classificazioneRaggiungibile']/*[local-name()='classeEnergetica']"),
            "reachable_epglnren": _number(node, "./*[local-name()='classificazioneRaggiungibile']/*[local-name()='epglnren']"),
            "overall_reachable_energy_class": rec_class, "overall_reachable_epglnren": rec_ep,
        })
    return raw, interventions


def _typed_frame(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=columns)
    for col in columns:
        if col in BOOL_COLUMNS:
            frame[col] = pd.array(frame[col], dtype="boolean")
        elif col in INT_COLUMNS:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("Int64")
        elif col in STRING_COLUMNS or col in {"source_record_id", "ape_id", "source_filename"}:
            frame[col] = frame[col].astype("string")
        elif col in NUMERIC_COLUMNS or col.endswith(("_years", "_epglnren")):
            frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("Float64")
    return frame


def _iter_xml_paths(source: Path):
    """Stable depth-first XML traversal without retaining all paths in memory."""
    import os
    for directory, dirs, files in os.walk(source):
        dirs.sort()
        for filename in sorted(files):
            if filename.lower().endswith(".xml"):
                yield Path(directory) / filename


def _sql_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _peek_xml_version(path: Path) -> str | None:
    try:
        prefix = path.open("rb").read(131072)
        match = re.search(rb"<(?:[A-Za-z0-9_]+:)?versione[^>]*>\s*([^<]+)", prefix)
        return match.group(1).decode("ascii", "replace").strip() if match else None
    except OSError:
        return None


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    temp = path.with_name(path.name + ".tmp")
    frame.to_parquet(temp, index=False, compression="zstd")
    os.replace(temp, path)


def _rebuild_parquet(batch_dir: Path, target: Path, stem: str, columns: list[str]) -> None:
    shards = sorted(batch_dir.glob(f"{stem}-*.parquet"))
    temp = target.with_name(target.name + ".tmp")
    writer = None; schema = None
    try:
        if shards:
            for shard in shards:
                table = pq.read_table(shard)
                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(temp, table.schema, compression="zstd")
                elif not table.schema.equals(schema, check_metadata=False):
                    raise ValueError(f"Inconsistent shard schema in {shard}")
                writer.write_table(table)
        else:
            _typed_frame([], columns).to_parquet(temp, index=False, compression="zstd")
    finally:
        if writer is not None: writer.close()
    os.replace(temp, target)


def _failure_reason(exc: Exception) -> str:
    message = str(exc)
    if "Invalid bytes in character encoding" in message: return "invalid_bytes_in_declared_encoding"
    if "Start tag expected" in message: return "not_xml_or_empty_source"
    if "unrecognized_ape_document" in message: return "unrecognized_ape_document"
    if "ape_attestation_section_missing" in message: return "ape_attestation_section_missing"
    return message.split(":", 1)[0]


def extract_directory(source: Path, output_dir: Path, batch_size: int = 500,
                      limit: int | None = None, retry_failed: bool = False) -> dict[str, Any]:
    """Stream XML into durable shards with a SQLite per-file manifest and resume support."""
    if batch_size <= 0: raise ValueError("batch_size must be positive")
    source = source.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    raw_path, rec_path = output_dir / "ape_raw.parquet", output_dir / "ape_recommendations.parquet"
    batch_dir = output_dir / ".ape_batches"; batch_dir.mkdir(exist_ok=True)
    manifest_db = output_dir / "ape_extraction_manifest.sqlite3"
    errors_path = output_dir / "ape_extraction_errors.jsonl"
    manifest_jsonl = output_dir / "ape_extraction_manifest.jsonl"
    db = sqlite3.connect(manifest_db)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS files (
          source_filename TEXT PRIMARY KEY, status TEXT NOT NULL, parse_status TEXT,
          batch_id INTEGER, file_size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
          filename_year TEXT, xml_schema_version TEXT, failure_reason TEXT, detail TEXT
        );
        CREATE TABLE IF NOT EXISTS current_scan (
          source_filename TEXT PRIMARY KEY, file_size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS batches (batch_id INTEGER PRIMARY KEY, files INTEGER NOT NULL, committed_utc TEXT NOT NULL);
    """)
    existing_root = db.execute("SELECT value FROM metadata WHERE key='source_root'").fetchone()
    if existing_root and existing_root[0] != str(source):
        db.close(); raise ValueError(f"Manifest source root is {existing_root[0]}, not {source}")
    db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES ('source_root',?)", [str(source)])
    db.commit()

    # Inventory all paths without storing them in Python; this distinguishes the
    # source population from this invocation's optional --limit.
    db.execute("BEGIN IMMEDIATE")
    db.execute("DELETE FROM current_scan")
    discovered = 0
    for path in _iter_xml_paths(source):
        relative = path.relative_to(source).as_posix()
        try: stat = path.stat()
        except OSError: continue
        db.execute("INSERT INTO current_scan VALUES (?,?,?)", (relative, stat.st_size, stat.st_mtime_ns))
        discovered += 1
        if discovered % 50000 == 0: LOG.info("inventory discovered=%d", discovered)
    db.commit()

    raw_rows: list[dict[str, Any]] = []; rec_rows: list[dict[str, Any]] = []; statuses: list[tuple] = []
    next_batch = int(db.execute("SELECT coalesce(max(batch_id),0)+1 FROM batches").fetchone()[0])
    current_batch = next_batch

    def flush_batch() -> None:
        nonlocal current_batch
        if not statuses: return
        for stem, rows, cols in (("raw", raw_rows, RAW_COLUMNS), ("recommendations", rec_rows, REC_COLUMNS)):
            if rows:
                final = batch_dir / f"{stem}-{current_batch:06d}.parquet"
                _write_parquet_atomic(_typed_frame(rows, cols), final)
        db.execute("BEGIN IMMEDIATE")
        db.executemany("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?,?)", statuses)
        db.execute("INSERT OR REPLACE INTO batches VALUES (?,?,datetime('now'))", (current_batch, len(statuses)))
        db.commit()
        LOG.info("committed batch=%d files=%d records=%d recommendations=%d", current_batch, len(statuses), len(raw_rows), len(rec_rows))
        current_batch += 1; raw_rows.clear(); rec_rows.clear(); statuses.clear()

    processed_this_run = 0
    for index, path in enumerate(_iter_xml_paths(source), 1):
        if limit is not None and index > limit: break
        relative = path.relative_to(source).as_posix()
        try: stat = path.stat()
        except OSError as exc:
            statuses.append((relative, "failed", None, current_batch, 0, 0,
                             re.match(r"(\d{4})_", path.name).group(1) if re.match(r"(\d{4})_", path.name) else None,
                             None, "file_stat_failed", str(exc)))
            processed_this_run += 1
            if len(statuses) >= batch_size: flush_batch()
            continue
        previous = db.execute("SELECT status,file_size,mtime_ns FROM files WHERE source_filename=?", [relative]).fetchone()
        if previous and (previous[1] != stat.st_size or previous[2] != stat.st_mtime_ns):
            db.close(); raise ValueError(f"Source file changed since prior processing: {relative}; use a fresh output directory to prevent duplicate historical output")
        unchanged = previous and previous[1] == stat.st_size and previous[2] == stat.st_mtime_ns
        if unchanged and (previous[0] != "failed" or not retry_failed): continue
        filename_year_match = re.match(r"(\d{4})_", path.name)
        filename_year = filename_year_match.group(1) if filename_year_match else None
        try:
            raw, recommendations = parse_ape_xml(path, source_filename=relative)
            raw_rows.append(raw); rec_rows.extend(recommendations)
            statuses.append((relative, "extracted", raw["parse_status"], current_batch, stat.st_size, stat.st_mtime_ns,
                             filename_year, raw["xml_schema_version"], None, None))
        except Exception as exc:
            detail = str(exc)
            statuses.append((relative, "failed", None, current_batch, stat.st_size, stat.st_mtime_ns,
                             filename_year, _peek_xml_version(path), _failure_reason(exc), detail))
        processed_this_run += 1
        if len(statuses) >= batch_size: flush_batch()
        if processed_this_run % 1000 == 0: LOG.info("progress discovered=%d attempted_this_run=%d", discovered, processed_this_run)
    flush_batch()

    # Public consolidated files are rebuilt from immutable committed shards and
    # atomically replaced, so a crash never exposes a half-written Parquet file.
    _rebuild_parquet(batch_dir, raw_path, "raw", RAW_COLUMNS)
    _rebuild_parquet(batch_dir, rec_path, "recommendations", REC_COLUMNS)

    # Materialize a readable one-row-per-source manifest and a separate failure ledger.
    with manifest_jsonl.open("w", encoding="utf-8") as mf, errors_path.open("w", encoding="utf-8") as ef:
        cursor = db.execute("""SELECT s.source_filename, coalesce(f.status,'not_yet_processed'),
            f.parse_status,s.file_size,f.filename_year,f.xml_schema_version,f.failure_reason,f.detail
            FROM current_scan s LEFT JOIN files f USING(source_filename) ORDER BY s.source_filename""")
        for row in cursor:
            record = dict(zip(("source_filename","status","parse_status","file_size_bytes","filename_year","xml_schema_version","failure_reason","detail"),row))
            mf.write(json.dumps(record, ensure_ascii=False) + "\n")
            if record["status"] == "failed": ef.write(json.dumps(record, ensure_ascii=False) + "\n")

    counts = dict(db.execute("""SELECT coalesce(f.status,'not_yet_processed'),count(*) FROM current_scan s
      LEFT JOIN files f USING(source_filename) GROUP BY 1""").fetchall())
    raw_pf, rec_pf = pq.ParquetFile(raw_path), pq.ParquetFile(rec_path)
    raw_count, recommendation_count = raw_pf.metadata.num_rows, rec_pf.metadata.num_rows
    import duckdb
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    raw_sql_path = str(raw_path).replace("'", "''"); rec_sql_path = str(rec_path).replace("'", "''")
    con.execute(f"CREATE VIEW ape_raw AS SELECT * FROM read_parquet('{raw_sql_path}')")
    con.execute(f"CREATE VIEW ape_recommendations AS SELECT * FROM read_parquet('{rec_sql_path}')")
    missing_pct = {col: con.execute(f"SELECT 100.0*count(*) FILTER (WHERE {_sql_ident(col)} IS NULL)/nullif(count(*),0) FROM ape_raw").fetchone()[0] for col in RAW_COLUMNS}
    versions = dict(con.execute("SELECT xml_schema_version,count(*) FROM ape_raw WHERE xml_schema_version IS NOT NULL GROUP BY 1").fetchall())
    object_distribution = dict(con.execute("SELECT attestation_object_code,count(*) FROM ape_raw WHERE attestation_object_code IS NOT NULL GROUP BY 1").fetchall())
    classes = dict(con.execute("SELECT energy_class,count(*) FROM ape_raw WHERE energy_class IS NOT NULL GROUP BY 1").fetchall())
    parse_status_distribution = dict(con.execute("SELECT parse_status,count(*) FROM ape_raw GROUP BY 1").fetchall())
    recommendations_by_certificate = con.execute("SELECT count(DISTINCT source_record_id) FROM ape_recommendations").fetchone()[0]
    unmatched_recs = con.execute("SELECT count(*) FROM ape_recommendations r LEFT JOIN ape_raw a USING(source_record_id) WHERE a.source_record_id IS NULL").fetchone()[0]
    duplicate_source_ids = con.execute("SELECT count(*) FROM (SELECT source_record_id FROM ape_raw GROUP BY 1 HAVING count(*)>1)").fetchone()[0]
    duplicate_cert_id_rows = con.execute("SELECT ape_id,count(*) n FROM ape_raw WHERE ape_id IS NOT NULL GROUP BY 1 HAVING n>1 ORDER BY n DESC,ape_id LIMIT 100").fetchall()
    duplicate_cert_ids = con.execute("SELECT count(*) FROM (SELECT ape_id FROM ape_raw WHERE ape_id IS NOT NULL GROUP BY 1 HAVING count(*)>1)").fetchone()[0]
    duplicate_cad_keys = con.execute("""SELECT count(*) FROM (SELECT cadastral_municipality,cadastral_sheet,cadastral_parcel,cadastral_subaltern
      FROM ape_raw WHERE cadastral_municipality IS NOT NULL AND cadastral_sheet IS NOT NULL AND cadastral_parcel IS NOT NULL
      AND cadastral_subaltern IS NOT NULL GROUP BY ALL HAVING count(*)>1)""").fetchone()[0]
    columns_all_null = [c for c in RAW_COLUMNS if con.execute(f"SELECT count({_sql_ident(c)}) FROM ape_raw").fetchone()[0] == 0]
    by_failure = db.execute("""SELECT coalesce(f.failure_reason,'unknown'),coalesce(f.filename_year,'unknown'),
      CASE WHEN f.file_size<65536 THEN '<64KiB' WHEN f.file_size<262144 THEN '64-256KiB' ELSE '>=256KiB' END,
      coalesce(f.xml_schema_version,'unknown'),count(*) FROM current_scan s JOIN files f USING(source_filename)
      WHERE f.status='failed' GROUP BY 1,2,3,4 ORDER BY 5 DESC""").fetchall()
    recovered = db.execute("SELECT count(*) FROM current_scan s JOIN files f USING(source_filename) WHERE f.parse_status LIKE 'normalized_%'").fetchone()[0]
    file_status_counts = {"discovered": discovered, "attempted": sum(counts.get(k,0) for k in ("extracted","failed")),
        "successfully_extracted": counts.get("extracted",0), "recovered": recovered,
        "failed": counts.get("failed",0), "not_yet_processed": counts.get("not_yet_processed",0)}
    report = {
        **file_status_counts, "successfully_parsed": raw_count, "raw_records": raw_count,
        "recommendation_records": recommendation_count, "recommendation_rows": recommendation_count,
        "certificates_with_recommendations": recommendations_by_certificate,
        "failure_reasons": dict(db.execute("SELECT failure_reason,count(*) FROM current_scan JOIN files USING(source_filename) WHERE status='failed' GROUP BY 1").fetchall()),
        "failures_by_year_size_version": [dict(zip(("reason","filename_year","size_band","xml_schema_version","count"),r)) for r in by_failure],
        "xml_versions": versions, "parse_status_distribution": parse_status_distribution,
        "missing_percent_by_attribute": missing_pct,
        "attestation_object_distribution": object_distribution, "energy_class_distribution": classes,
        "duplicate_source_identifiers": duplicate_source_ids,
        "duplicate_certificate_identifier_count": duplicate_cert_ids,
        "duplicate_certificate_identifiers": {str(k):int(v) for k,v in duplicate_cert_id_rows},
        "duplicate_cadastral_references": duplicate_cad_keys,
        "unmatched_recommendation_source_ids": unmatched_recs, "all_null_columns": columns_all_null,
        "schema_valid": list(raw_pf.schema_arrow.names) == RAW_COLUMNS and list(rec_pf.schema_arrow.names) == REC_COLUMNS,
        "manifest_file": str(manifest_jsonl), "manifest_database": str(manifest_db),
        "processing_complete": file_status_counts["not_yet_processed"] == 0,
    }
    con.close(); db.close()
    (output_dir / "ape_data_quality_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Directory containing APE XML files")
    parser.add_argument("--output-dir", type=Path, default=Path("backend/data/metadata/extracted"))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--limit", type=int, help="Process only the first N sorted files")
    parser.add_argument("--retry-failed", action="store_true", help="Retry files previously recorded as failed")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")
    report = extract_directory(args.source, args.output_dir, args.batch_size, args.limit, args.retry_failed)
    LOG.info("Extraction summary: %s", json.dumps({k: report[k] for k in ("discovered", "attempted", "successfully_extracted", "recovered", "failed", "not_yet_processed", "raw_records", "recommendation_records")}))


if __name__ == "__main__": main()
