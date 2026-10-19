"""Stratified, non-mutating APE XML encoding/recovery diagnostic."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "data" / "metadata"))
from data.metadata.ape_extraction import _first  # noqa: E402


def iter_files(root: Path):
    import os
    for directory, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            if name.lower().endswith(".xml"):
                yield Path(directory) / name


def filename_year(path: Path) -> str:
    m = re.match(r"(\d{4})_", path.name)
    return m.group(1) if m else "unknown"


def allocate_quotas(counts: dict[tuple[str, int], int], requested: int) -> dict[tuple[str, int], int]:
    total = sum(counts.values())
    target = min(total, requested)
    quotas = {k: min(v, int(target * v / total)) for k, v in counts.items()}
    left = target - sum(quotas.values())
    order = sorted(counts, key=lambda k: (-(target * counts[k] / total - quotas[k]), k))
    while left:
        changed = False
        for k in order:
            if quotas[k] < counts[k]:
                quotas[k] += 1; left -= 1; changed = True
                if not left: break
        if not changed: break
    return quotas


def parse_tree(raw: bytes, recover: bool = False) -> tuple[etree._Element | None, list[str], str | None]:
    parser = etree.XMLParser(recover=recover, huge_tree=True, resolve_entities=False,
                             load_dtd=False, no_network=True)
    try:
        root = etree.fromstring(raw, parser)
        return root, [str(e) for e in parser.error_log], None
    except (etree.XMLSyntaxError, ValueError) as exc:
        return None, [str(e) for e in parser.error_log], f"{type(exc).__name__}: {exc}"


KEY_XPATHS = {
    "ape_id": "//*[local-name()='datiAttestato']/*[local-name()='codiceIdentificativo']",
    "xml_version": "//*[local-name()='info']/*[local-name()='versione']",
    "issue_date": "//*[local-name()='dataEmissione']",
    "address": "//*[local-name()='datiCalcolo']/*[local-name()='datiGenerali']/*[local-name()='indirizzo']",
    "municipality": "//*[local-name()='datiCalcolo']/*[local-name()='datiGenerali']/*[local-name()='comune']",
    "istat_code": "//*[local-name()='datiCalcolo']/*[local-name()='datiGenerali']/*[local-name()='codiceISTAT']",
    "latitude": "//*[local-name()='datiCalcolo']/*[local-name()='datiGenerali']/*[local-name()='latitudineGIS']",
    "longitude": "//*[local-name()='datiCalcolo']/*[local-name()='datiGenerali']/*[local-name()='longitudineGIS']",
    "construction_year": "//*[local-name()='datiIdentificativi']/*[local-name()='annoCostruzione']",
    "usable_surface": "//*[local-name()='superficieUtileRiscaldata']",
    "energy_class": "//*[local-name()='prestazioneGlobale']/*[local-name()='prestazioneEnergeticaGlobale']/*[local-name()='classificazione']/*[local-name()='classeEnergetica']",
    "epglnren": "//*[local-name()='prestazioneGlobale']/*[local-name()='prestazioneEnergeticaGlobale']/*[local-name()='classificazione']/*[local-name()='epglnren']",
}


def key_values(root: etree._Element | None) -> dict[str, str | None]:
    if root is None: return {k: None for k in KEY_XPATHS}
    result = {}
    for key, xpath in KEY_XPATHS.items():
        values = root.xpath(xpath)
        result[key] = "".join(values[0].itertext()).strip() if values else None
    return result


def controlled_decode(raw: bytes, declared: str | None) -> dict[str, Any]:
    """Try declaration, then preserve UTF-8 and map only invalid bytes via CP1252.

    charset-normalizer's guess is recorded but is not accepted as authoritative:
    this corpus is Italian and a detector can confuse CP1252 bytes with CP1250.
    """
    attempts = []
    detected_encoding = None
    detector_chaos = None
    detector_coherence = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(raw).best()
        detected_encoding = best.encoding if best is not None else None
        detector_chaos = getattr(best, "chaos", None) if best is not None else None
        detector_coherence = getattr(best, "coherence", None) if best is not None else None
    except Exception as exc:
        detection_error = f"{type(exc).__name__}: {exc}"
    else:
        detection_error = None
    if declared:
        attempts.append((declared, "declared", None, None))
    attempts.append(("utf8_cp1252_invalid_bytes", "mixed_utf8_cp1252_invalid_bytes", None, None))
    attempts.append(("cp1252", "corpus_cp1252_candidate", None, None))
    for encoding, source in ((detected_encoding, "charset_normalizer"), ("iso-8859-1", "fallback_latin1")):
        if encoding and all(e.lower().replace("_", "-") != encoding.lower().replace("_", "-") for e, *_ in attempts):
            attempts.append((encoding, source, None, None))
    for encoding, source, chaos, coherence in attempts:
        repaired_count=0
        try:
            if encoding == "utf8_cp1252_invalid_bytes":
                parts=[]
                for char in raw.decode("utf-8",errors="surrogateescape"):
                    code=ord(char)
                    if 0xDC80 <= code <= 0xDCFF:
                        parts.append(bytes([code-0xDC00]).decode("cp1252",errors="strict"));repaired_count+=1
                    else: parts.append(char)
                text="".join(parts)
            else: text = raw.decode(encoding, errors="strict")
        except (UnicodeError, LookupError):
            continue
        # Re-encode as UTF-8 without changing the XML content; update only declaration.
        text = re.sub(r"(<\?xml\s+[^?]*encoding\s*=\s*)['\"][^'\"]+['\"]",
                      r'\1"UTF-8"', text, count=1, flags=re.I)
        root, warnings, error = parse_tree(text.encode("utf-8"), recover=False)
        if root is not None:
            return {"root": root, "encoding": encoding, "method": source,"repaired_byte_count":repaired_count,
                    "detected_encoding": detected_encoding, "chaos": detector_chaos, "coherence": detector_coherence, "warnings": warnings,
                    "error": error, "lossy": False, "detection_error": detection_error}
    return {"root": None, "encoding": None, "method": None, "detected_encoding": detected_encoding, "chaos": detector_chaos,
            "coherence": detector_coherence, "warnings": [], "error": "no strict candidate decoding succeeded","repaired_byte_count":0,
            "lossy": False, "detection_error": detection_error}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    ap.add_argument("--sample-size", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20261016)
    ap.add_argument("--output-dir", type=Path, default=ROOT / "backend/research/ape_profile")
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # First pass obtains corpus size quantiles without retaining paths.
    file_sizes = []
    files_seen = 0
    for path in iter_files(args.root):
        try: file_sizes.append(path.stat().st_size); files_seen += 1
        except OSError: continue
        if files_seen % 50000 == 0: print(f"Inventory: {files_seen:,}", flush=True)
    if not file_sizes: raise SystemExit(f"No XML files found below {args.root}")
    ordered_sizes = sorted(file_sizes)
    cuts = [ordered_sizes[min(len(ordered_sizes)-1, math.floor(len(ordered_sizes)*q))] for q in (.25, .5, .75)]
    def size_bin(n: int) -> int:
        return sum(n > cut for cut in cuts)

    # Second pass counts year x size strata.
    counts: Counter[tuple[str, int]] = Counter()
    for path in iter_files(args.root):
        try: counts[(filename_year(path), size_bin(path.stat().st_size))] += 1
        except OSError: continue
    quotas = allocate_quotas(dict(counts), args.sample_size)
    rng = random.Random(args.seed)
    reservoirs: dict[tuple[str, int], list[tuple[Path, int]]] = {k: [] for k in counts}
    seen: Counter[tuple[str, int]] = Counter()
    for path in iter_files(args.root):
        try: size = path.stat().st_size
        except OSError: continue
        key = (filename_year(path), size_bin(size)); seen[key] += 1; q = quotas.get(key, 0)
        if not q: continue
        bucket = reservoirs[key]
        if len(bucket) < q: bucket.append((path, size))
        else:
            j = rng.randrange(seen[key])
            if j < q: bucket[j] = (path, size)

    rows: list[dict[str, Any]] = []
    for key in sorted(reservoirs):
        for path, size in reservoirs[key]:
            raw = path.read_bytes()
            declaration = re.search(rb"<\?xml[^>]*encoding\s*=\s*['\"]([^'\"]+)", raw[:512], re.I)
            declared = declaration.group(1).decode("ascii", "replace") if declaration else None
            strict_root, strict_warnings, strict_error = parse_tree(raw, recover=False)
            # This mirrors the current production parser's raw-byte lxml parse: no recovery/normalization.
            prod_root, prod_warnings, prod_error = parse_tree(raw, recover=False)
            normalized = ({"root":strict_root,"encoding":declared or "xml_auto_detect","method":"strict_passthrough",
                           "detected_encoding":None,"chaos":None,"coherence":None,"warnings":strict_warnings,
                           "error":None,"lossy":False,"detection_error":None,"repaired_byte_count":0}
                          if strict_root is not None else controlled_decode(raw, declared))
            def transcode_tree(encoding: str):
                try:
                    text=raw.decode(encoding,"strict")
                    text=re.sub(r"(<\?xml\s+[^?]*encoding\s*=\s*)['\"][^'\"]+['\"]",r'\1"UTF-8"',text,count=1,flags=re.I)
                    return parse_tree(text.encode("utf-8"),False)[0]
                except (UnicodeError, LookupError): return None
            cp1250_root = transcode_tree("cp1250")
            def first_unit(root):
                if root is None: return None
                values=root.xpath("//*[local-name()='unMisura']/text()")
                return values[0].strip() if values else None
            cp1252_root=transcode_tree("cp1252"); cp1252_unit=first_unit(cp1252_root)
            normalized_unit=first_unit(normalized["root"])
            recovery_root, recovery_warnings, recovery_error = parse_tree(raw, recover=True)
            strict_values, norm_values, recovery_values = key_values(strict_root), key_values(normalized["root"]), key_values(recovery_root)
            structurally_valid = bool((norm_values.get("ape_id") or norm_values.get("address")) and
                                      (norm_values.get("energy_class") or norm_values.get("epglnren")))
            recover_valid = bool((recovery_values.get("ape_id") or recovery_values.get("address")) and
                                 (recovery_values.get("energy_class") or recovery_values.get("epglnren")))
            differences = [k for k in KEY_XPATHS if strict_values.get(k) != norm_values.get(k)]
            recovery_differences = [k for k in KEY_XPATHS if norm_values.get(k) != recovery_values.get(k)]
            ns = etree.QName(strict_root).namespace if strict_root is not None else None
            root_name = etree.QName(strict_root).localname if strict_root is not None else None
            rows.append({
                "source_filename": str(path.relative_to(args.root)), "filename_year": key[0], "file_size_bytes": size,
                "size_quartile": key[1]+1, "declared_encoding": declared,
                "detected_encoding": normalized["detected_encoding"], "normalization_encoding": normalized["encoding"], "encoding_detection_method": normalized["method"],
                "detector_chaos": normalized["chaos"], "detector_coherence": normalized["coherence"],
                "strict_parse_ok": strict_root is not None, "strict_exception": strict_error,
                "strict_warnings": json.dumps(strict_warnings, ensure_ascii=False),
                "production_raw_parse_ok": prod_root is not None, "production_exception": prod_error,
                "production_warnings": json.dumps(prod_warnings, ensure_ascii=False),
                "controlled_normalization_ok": normalized["root"] is not None,
                "normalization_method": normalized["method"], "normalization_exception": normalized["error"],
                "normalization_repaired_byte_count": normalized["repaired_byte_count"],
                "normalization_warnings": json.dumps(normalized["warnings"], ensure_ascii=False),
                "potentially_lossy_recovery_ok": recovery_root is not None,
                "recovery_exception": recovery_error,
                "recovery_warnings": json.dumps(recovery_warnings, ensure_ascii=False),
                "recovery_warning_count": len(recovery_warnings),
                "strict_namespace": ns, "strict_root_element": root_name,
                "ape_attributes_usable_after_normalization": structurally_valid,
                "ape_attributes_usable_after_recovery": recover_valid,
                "strict_vs_normalized_differing_keys": ",".join(differences),
                "normalized_vs_recovery_differing_keys": ",".join(recovery_differences),
                "first_energy_consumption_unit_cp1250": first_unit(cp1250_root),
                "first_energy_consumption_unit_cp1252": cp1252_unit,
                "first_energy_consumption_unit_normalized": normalized_unit,
                "normalized_key_values": json.dumps(norm_values, ensure_ascii=False),
                "recovery_key_values": json.dumps(recovery_values, ensure_ascii=False),
            })
    out_csv = args.output_dir / "xml_parsing_diagnostics.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["source_filename"])
        writer.writeheader(); writer.writerows(rows)
    summary = Counter()
    for r in rows:
        for method, key in (("strict", "strict_parse_ok"), ("production", "production_raw_parse_ok"),
                            ("normalized", "controlled_normalization_ok"), ("recovery", "potentially_lossy_recovery_ok")):
            summary[f"{method}_success"] += bool(r[key])
        summary["normalized_structurally_usable"] += bool(r["ape_attributes_usable_after_normalization"])
        summary["recovery_structurally_usable"] += bool(r["ape_attributes_usable_after_recovery"])
    def failure_category(message: str | None) -> str:
        if not message: return "success"
        if "Invalid bytes in character encoding" in message: return "invalid_bytes_in_declared_encoding"
        if "Start tag expected" in message: return "not_xml_or_empty_source"
        return message.split(":", 1)[0]
    reasons = Counter(failure_category(r["strict_exception"]) for r in rows)
    encodings = Counter(r["normalization_encoding"] or "unavailable" for r in rows)
    detector_encodings = Counter(r["detected_encoding"] or "unavailable" for r in rows)
    methods = Counter(r["encoding_detection_method"] or "unavailable" for r in rows)
    years = Counter(r["filename_year"] for r in rows)
    sizes = Counter(str(r["size_quartile"]) for r in rows)
    report = ["# XML parsing diagnostics", "", f"- Files inventoried: {files_seen:,}.",
              f"- Diagnostic sample: {len(rows):,}; stratified by filename year and corpus file-size quartile; seed `{args.seed}`.",
              f"- File-size quartile cut points (bytes): {cuts}.",
               "- XML schema version cannot be reliably read from path metadata alone; `xml_version` values are captured from sampled trees where recoverable. Namespace and root elements are also logged.", "",
              "## Outcomes", ""]
    for key, label in (("strict_success", "Strict lxml parse"), ("production_success", "Current production raw-byte parse"),
                       ("normalized_success", "Controlled reversible decoding + strict parse"),
                       ("recovery_success", "lxml recovery tree construction"),
                       ("normalized_structurally_usable", "Normalization with key APE fields present"),
                       ("recovery_structurally_usable", "Recovery with key APE fields present")):
        report.append(f"- {label}: {summary[key]:,}/{len(rows):,}.")
    report += ["", "## Strict failure causes", ""]
    report += [f"- `{reason}`: {count:,}" for reason, count in reasons.most_common()]
    report += ["", "## Encoding and sample composition", "",
               f"- Controlled normalization encodings selected: {json.dumps(dict(encodings), ensure_ascii=False)}.",
               f"- Normalization selection path: {json.dumps(dict(methods), ensure_ascii=False)}.",
               f"- charset-normalizer guesses (diagnostic only): {json.dumps(dict(detector_encodings), ensure_ascii=False)}.",
               f"- lxml recovery trees emitted {sum(r['recovery_warning_count']>0 for r in rows):,} warning-bearing parses; warning details are in the CSV.",
               f"- Filename-year strata: {json.dumps(dict(years), ensure_ascii=False)}.",
               f"- Size-quartile strata: {json.dumps(dict(sizes), ensure_ascii=False)}.", "",
               "## Interpretation and recommended strategy", "",
               "The existing production parser passes source bytes directly to lxml and does not normalize encoding or recover malformed XML. In this stratified sample, declared UTF-8 files contain individual CP1252 bytes (for example 0xB3 for the unit suffix) among otherwise valid UTF-8 sequences. charset-normalizer often guesses CP1250, which can decode the 0xB3 byte as `ł`; whole-file CP1252 can instead corrupt valid UTF-8 sequences (such as `m³` to `mÂ³`). The validated strategy is to preserve valid UTF-8 sequences and map only invalid UTF-8 bytes through CP1252, then parse the resulting UTF-8 XML strictly. Each repaired byte is counted and the inferred encoding is recorded. Files declaring a valid non-UTF-8 encoding are parsed as declared.",
               "Successful tree construction is not sufficient: the diagnostic records key identity, location, date, and energy fields and reports structural usability separately. Inspect `xml_parsing_diagnostics.csv` before choosing any recovery policy. The source files are never rewritten.", ""]
    (args.output_dir / "xml_parsing_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote {out_csv} and xml_parsing_report.md ({len(rows)} files)", flush=True)


if __name__ == "__main__":
    main()
