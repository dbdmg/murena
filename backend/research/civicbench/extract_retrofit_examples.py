"""Extract a deterministic, source-faithful sample of APE retrofit recommendations.

This research utility reads only the Phase 1 Parquet exports. It does not alter
the exports or parse the XML corpus.
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW = ROOT / "backend/data/metadata/extracted/ape_raw.parquet"
DEFAULT_RECS = ROOT / "backend/data/metadata/extracted/ape_recommendations.parquet"
DEFAULT_OUT = ROOT / "backend/research/civicbench/examples"
SEED = 20261019

CERT_FIELDS = ["source_record_id", "municipality", "dpr412_class_code", "attestation_object_code",
               "construction_year", "heated_usable_surface", "energy_class", "epglnren",
               "overall_reachable_energy_class", "overall_reachable_epglnren"]
REC_FIELDS = ["intervention_code", "intervention_description", "major_renovation_code",
              "payback_period_years", "reachable_energy_class", "reachable_epglnren"]
CSV_FIELDS = CERT_FIELDS + REC_FIELDS + ["calculated_absolute_reduction", "calculated_percentage_reduction"]


def numeric(v, allow_zero=False):
    try:
        n = float(v)
        return n if n > 0 or (allow_zero and n == 0) else None
    except (TypeError, ValueError):
        return None


def shown(v):
    return "Missing" if v is None or v == "" else str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--recommendations", type=Path, default=DEFAULT_RECS)
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    con = duckdb.connect()
    # DESCRIBE is deliberately executed before the extraction query: source field
    # names are verified at runtime rather than guessed from another export.
    schemas = {}
    for name, path in (("cert", args.raw), ("rec", args.recommendations)):
        schemas[name] = {r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()}
    required = {"cert": set(CERT_FIELDS), "rec": {"source_record_id", *REC_FIELDS}}
    for name in required:
        absent = required[name] - schemas[name]
        if absent:
            raise SystemExit(f"{name} parquet is missing required columns: {sorted(absent)}")
    certs = con.execute("SELECT " + ",".join('a."'+f+'"' for f in CERT_FIELDS) +
        " FROM read_parquet(?) a WHERE EXISTS (SELECT 1 FROM read_parquet(?) r WHERE r.source_record_id=a.source_record_id)",
        [str(args.raw), str(args.recommendations)]).fetchall()
    recs = con.execute("SELECT " + ",".join('"'+f+'"' for f in ["source_record_id", *REC_FIELDS]) +
        " FROM read_parquet(?) ORDER BY source_record_id, intervention_code, intervention_description", [str(args.recommendations)]).fetchall()
    by_id = defaultdict(list)
    for row in recs:
        by_id[row[0]].append(dict(zip(REC_FIELDS, row[1:])))
    cert_by_id = {r[0]: dict(zip(CERT_FIELDS, r)) for r in certs}
    eligible = []
    for cid, c in cert_by_id.items():
        interventions = [r for r in by_id[cid] if r["intervention_description"] and str(r["intervention_description"]).strip()]
        if not interventions:
            continue
        c["_recs"] = interventions
        eligible.append(c)

    # Seeded greedy coverage: prefer valid baselines and novel values across
    # class, use, period, surface band, intervention code and improvement band.
    rng = random.Random(args.seed)
    rng.shuffle(eligible)
    def feature(c):
        surface = numeric(c["heated_usable_surface"])
        year = numeric(c["construction_year"])
        base = numeric(c["epglnren"])
        overall = numeric(c["overall_reachable_epglnren"], allow_zero=True)
        pct = 100 * (base - overall) / base if base and overall is not None else None
        return [c["energy_class"] or "?", c["dpr412_class_code"] or "?",
                (int(year // 10) * 10 if year else "?"),
                ("small" if surface and surface < 80 else "medium" if surface and surface < 150 else "large" if surface else "?"),
                tuple(sorted({str(r["intervention_code"]) for r in c["_recs"]})),
                ("unknown" if pct is None else "low" if pct < 20 else "mid" if pct < 50 else "high"),
                bool(base), bool(overall), len(c["_recs"]) > 1]
    features = {c["source_record_id"]: feature(c) for c in eligible}
    chosen, seen = [], [Counter() for _ in range(9)]
    while eligible and len(chosen) < args.count:
        best_i, best_score = None, None
        for i, c in enumerate(eligible):
            fs = features[c["source_record_id"]]
            score = sum((2.2 if j < 2 else 1.2 if j in (4, 5, 8) else .8) / (1 + seen[j][str(fs[j])]) for j in range(9))
            score += 1.0 * bool(numeric(c["epglnren"])) + .7 * bool(numeric(c["overall_reachable_epglnren"]))
            if best_score is None or score > best_score:
                best_i, best_score = i, score
        c = eligible.pop(best_i); chosen.append(c)
        for j, value in enumerate(features[c["source_record_id"]]): seen[j][str(value)] += 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "retrofit_examples.csv"
    rows = []
    for c in chosen:
        base = numeric(c["epglnren"]); overall = numeric(c["overall_reachable_epglnren"], allow_zero=True)
        for r in c["_recs"]:
            row = {k: c.get(k) for k in CERT_FIELDS}
            row.update(r)
            row["calculated_absolute_reduction"] = base - overall if base is not None and overall is not None else None
            row["calculated_percentage_reduction"] = 100 * (base - overall) / base if base is not None and overall is not None else None
            rows.append(row)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS); w.writeheader(); w.writerows(rows)

    types = Counter(str(r["intervention_code"]) if r["intervention_code"] is not None else "Missing" for r in rows)
    md = ["# Real APE retrofit recommendation examples", "",
          f"Deterministic selection: seed `{args.seed}`; {len(chosen)} certificates and {len(rows)} intervention rows. Source files: `{args.raw}` and `{args.recommendations}`.", "",
          "Values labeled **Observed** are copied from Phase 1 Parquet. **Calculated** values use the certificate's overall reachable EPgl,nren and are not intervention-level savings. Individual recommendation outcomes are shown separately; recommendations are never summed.", "",
          "## Comparison summary", "", "| Certificate | Municipality | Use code | Initial class | Initial EPgl,nren | Overall reachable class / EPgl,nren | Calculated reduction | Interventions |", "|---|---|---|---|---:|---|---:|---:|"]
    for c in chosen:
        b, o = numeric(c["epglnren"]), numeric(c["overall_reachable_epglnren"], allow_zero=True)
        delta = f"{b-o:.2f} ({100*(b-o)/b:.1f}%)" if b is not None and o is not None else "Missing"
        md.append(f"| {c['source_record_id']} | {shown(c['municipality'])} | {shown(c['dpr412_class_code'])} | {shown(c['energy_class'])} | {shown(c['epglnren'])} | {shown(c['overall_reachable_energy_class'])} / {shown(c['overall_reachable_epglnren'])} | {delta} | {len(c['_recs'])} |")
    md += ["", "## Certificate details", ""]
    for n, c in enumerate(chosen, 1):
        b, o = numeric(c["epglnren"]), numeric(c["overall_reachable_epglnren"], allow_zero=True)
        md += [f"### {n}. `{c['source_record_id']}`", "",
               f"- **Observed building data:** municipality {shown(c['municipality'])}; building-use code {shown(c['dpr412_class_code'])}; attestation object {shown(c['attestation_object_code'])}; construction year {shown(c['construction_year'])}; heated usable surface {shown(c['heated_usable_surface'])} m²; initial class {shown(c['energy_class'])}; initial EPgl,nren {shown(c['epglnren'])}.",
               f"- **Observed overall APE reachable performance:** class {shown(c['overall_reachable_energy_class'])}; EPgl,nren {shown(c['overall_reachable_epglnren'])}."]
        if b is not None and o is not None:
            md.append(f"- **Calculated overall potential reduction:** {b-o:.2f} kWh/m²·year ({100*(b-o)/b:.2f}%).")
        else:
            md.append("- **Calculated overall potential reduction:** Missing; baseline and/or reachable EPgl,nren is absent or not positive numeric data.")
        md += ["- **Observed recommended interventions:**"]
        for r in c["_recs"]:
            md.append(f"  - Code {shown(r['intervention_code'])}: {r['intervention_description']} (major renovation: {shown(r['major_renovation_code'])}; payback: {shown(r['payback_period_years'])} years; intervention reachable class: {shown(r['reachable_energy_class'])}; intervention reachable EPgl,nren: {shown(r['reachable_epglnren'])}).")
        md += ["- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.", ""]
    md += ["## Intervention type distribution", "", "| Observed intervention code | Rows |", "|---|---:|"]
    md += [f"| {k} | {v} |" for k, v in sorted(types.items())]
    md += ["", "## Provenance and calculation", "", "The CSV has one row per documented recommendation, joined by `source_record_id`. Building fields and recommendation fields are observed Parquet values. The two calculated reduction columns use the certificate-level baseline `epglnren` and certificate-level overall reachable `overall_reachable_epglnren`; recommendation-level reachable values remain separate. No personal contacts, addresses, or cadastral identifiers are exported. Selection is a seeded greedy coverage procedure across classes, use codes, construction decades, surface bands, intervention-code combinations, improvement bands, valid energy metrics, and multiple-intervention certificates.", ""]
    (args.output_dir / "retrofit_examples.md").write_text("\n".join(md), encoding="utf-8")
    print(f"certificates={len(chosen)} interventions={len(rows)} seed={args.seed}")
    print("intervention_types=" + repr(dict(sorted(types.items()))))
    reductions = [(numeric(c["epglnren"])-numeric(c["overall_reachable_epglnren"], allow_zero=True)) for c in chosen if numeric(c["epglnren"]) is not None and numeric(c["overall_reachable_epglnren"], allow_zero=True) is not None]
    print(f"overall_reduction_range={min(reductions) if reductions else None}..{max(reductions) if reductions else None}; payback_available={sum(numeric(r['payback_period_years']) is not None for r in rows)}/{len(rows)}")
    print(f"csv={csv_path}\nmarkdown={args.output_dir / 'retrofit_examples.md'}")


if __name__ == "__main__":
    main()
