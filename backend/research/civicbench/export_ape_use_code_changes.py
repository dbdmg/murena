"""Export source APE records grouped into cadastral units with varying use codes."""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW = ROOT / "backend/data/metadata/extracted/ape_raw.parquet"
DEFAULT_OUT = ROOT / "backend/research/civicbench/examples/ape_use_code_changes.csv"
LEGEND_OUT = ROOT / "backend/research/civicbench/examples/dpr412_use_code_legend.md"

USE_CODE_LABELS = {
    "0": "E1(1) abitazioni adibite a residenza con carattere continuativo",
    "1": "E1(1)bis collegi, luoghi di ricovero, case di pena, caserme, conventi",
    "2": "E1(2) abitazioni adibite a residenza con occupazione saltuaria",
    "3": "E1(3) edifici adibiti ad albergo, pensione ed attività similari",
    "4": "E2 uffici e assimilabili",
    "5": "E3 ospedali, cliniche, case di cura e assimilabili",
    "6": "E4(1) cinema e teatri, sale di riunione per congressi e assimilabili",
    "7": "E4(2) mostre, musei e biblioteche, luoghi di culto e assimilabili",
    "8": "E4(3) bar, ristoranti, sale da ballo e assimilabili",
    "9": "E5 attività commerciali e assimilabili",
    "10": "E6(1) piscine, saune e assimilabili",
    "11": "E6(2) palestre e assimilabili",
    "12": "E6(3) servizi di supporto alle attività sportive",
    "13": "E7 attività scolastiche",
    "14": "E8 attività industriali, artigianali e assimilabili",
}

FIELDS = [
    "case_id", "cadastral_municipality", "cadastral_sheet", "cadastral_parcel", "cadastral_subaltern",
    "certificates_in_case", "distinct_nonempty_use_codes", "use_codes_in_case",
    "distinct_nonzero_use_codes", "contains_code_0", "distinct_valid_issue_dates",
    "has_different_valid_issue_dates", "source_record_id", "ape_id", "issue_date", "heated_usable_surface",
    "dpr412_class_code", "dpr412_class_description",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-surface-variation-pct", type=float, default=20.0,
                        help="Keep only cadastral cases whose positive heated-surface span is at most this percent")
    args = parser.parse_args()
    if not 0 <= args.max_surface_variation_pct <= 100:
        raise SystemExit("--max-surface-variation-pct must be between 0 and 100")
    con = duckdb.connect()
    schema = {row[0] for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(args.raw)]).fetchall()}
    needed = {"source_record_id", "ape_id", "issue_date", "heated_usable_surface", "dpr412_class_code", "cadastral_municipality",
              "cadastral_sheet", "cadastral_parcel", "cadastral_subaltern"}
    absent = needed - schema
    if absent:
        raise SystemExit(f"Source Parquet missing columns: {sorted(absent)}")

    sql = """
    WITH valid AS (
      SELECT *, try_cast(issue_date AS DATE) AS parsed_issue_date
      FROM read_parquet(?)
      WHERE cadastral_municipality IS NOT NULL AND cadastral_sheet IS NOT NULL
        AND cadastral_parcel IS NOT NULL AND cadastral_subaltern IS NOT NULL
        AND NOT (
          coalesce(try_cast(cadastral_sheet AS BIGINT)=0, false) OR
          coalesce(try_cast(cadastral_parcel AS BIGINT)=0, false) OR
          coalesce(try_cast(cadastral_subaltern AS BIGINT)=0, false)
        )
    ), qualified AS (
      SELECT DISTINCT a.cadastral_municipality, a.cadastral_sheet, a.cadastral_parcel, a.cadastral_subaltern
      FROM valid a JOIN valid b USING(cadastral_municipality,cadastral_sheet,cadastral_parcel,cadastral_subaltern)
      WHERE a.dpr412_class_code IS NOT NULL AND trim(a.dpr412_class_code)<>''
        AND b.dpr412_class_code IS NOT NULL AND trim(b.dpr412_class_code)<>''
        AND a.dpr412_class_code<>b.dpr412_class_code
        AND a.parsed_issue_date IS NOT NULL AND b.parsed_issue_date IS NOT NULL
        AND a.parsed_issue_date<>DATE '1899-12-30' AND b.parsed_issue_date<>DATE '1899-12-30'
        AND a.parsed_issue_date<>b.parsed_issue_date
        AND NOT EXISTS (
          SELECT 1 FROM valid dup
          WHERE dup.cadastral_municipality=a.cadastral_municipality
            AND dup.cadastral_sheet=a.cadastral_sheet
            AND dup.cadastral_parcel=a.cadastral_parcel
            AND dup.cadastral_subaltern=a.cadastral_subaltern
          GROUP BY dup.parsed_issue_date
          HAVING count(DISTINCT dup.source_record_id)>1
        )
        AND (
          SELECT 100.0 * (max(s.heated_usable_surface)-min(s.heated_usable_surface))
            / nullif(max(s.heated_usable_surface),0)
          FROM valid s
          WHERE s.cadastral_municipality=a.cadastral_municipality
            AND s.cadastral_sheet=a.cadastral_sheet
            AND s.cadastral_parcel=a.cadastral_parcel
            AND s.cadastral_subaltern=a.cadastral_subaltern
            AND s.heated_usable_surface>0
        ) <= ?
    ), grouped AS (
      SELECT cadastral_municipality, cadastral_sheet, cadastral_parcel, cadastral_subaltern,
        count(DISTINCT source_record_id) AS certificates_in_case,
        count(DISTINCT dpr412_class_code) FILTER (WHERE dpr412_class_code IS NOT NULL AND trim(dpr412_class_code)<>'') AS distinct_nonempty_use_codes,
        string_agg(DISTINCT dpr412_class_code, ', ' ORDER BY dpr412_class_code)
          FILTER (WHERE dpr412_class_code IS NOT NULL AND trim(dpr412_class_code)<>'') AS use_codes_in_case,
        count(DISTINCT dpr412_class_code) FILTER (WHERE dpr412_class_code IS NOT NULL AND trim(dpr412_class_code)<>'' AND dpr412_class_code<>'0') AS distinct_nonzero_use_codes,
        bool_or(dpr412_class_code='0') AS contains_code_0,
        count(DISTINCT parsed_issue_date) FILTER (WHERE parsed_issue_date IS NOT NULL AND parsed_issue_date<>DATE '1899-12-30') AS distinct_valid_issue_dates
      FROM valid JOIN qualified USING(cadastral_municipality,cadastral_sheet,cadastral_parcel,cadastral_subaltern)
      GROUP BY ALL
    )
    SELECT g.cadastral_municipality, g.cadastral_sheet, g.cadastral_parcel, g.cadastral_subaltern,
      g.certificates_in_case, g.distinct_nonempty_use_codes, g.use_codes_in_case,
      g.distinct_nonzero_use_codes, g.contains_code_0, g.distinct_valid_issue_dates,
      (g.distinct_valid_issue_dates>=2) AS has_different_valid_issue_dates,
      v.source_record_id, v.ape_id, v.issue_date, v.heated_usable_surface, v.dpr412_class_code
    FROM grouped g JOIN valid v USING(cadastral_municipality,cadastral_sheet,cadastral_parcel,cadastral_subaltern)
    ORDER BY g.cadastral_municipality,g.cadastral_sheet,g.cadastral_parcel,g.cadastral_subaltern,
      v.parsed_issue_date NULLS LAST, v.source_record_id
    """
    rows = con.execute(sql, [str(args.raw), args.max_surface_variation_pct]).fetchall()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            (comune, sheet, parcel, subaltern, cert_count, code_count, codes, nonzero_count,
             has_zero, date_count, has_date_change, source_id, ape_id, issue_date, surface, use_code) = row
            key = "|".join(str(x) for x in (comune, sheet, parcel, subaltern))
            case_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            writer.writerow(dict(zip(FIELDS, [case_id, comune, sheet, parcel, subaltern, cert_count,
                code_count, codes, nonzero_count, has_zero, date_count, has_date_change,
                source_id, ape_id, issue_date, surface,
                use_code, USE_CODE_LABELS.get(use_code, "Codice non presente nella legenda fornita") if use_code else None])))
    LEGEND_OUT.write_text("# Legenda codici d’uso DPR 412\n\nLegenda fornita dall’utente; i codici sono riportati nel CSV insieme alle descrizioni.\n\n" +
        "\n".join(f"- **{code}** — {description}" for code, description in USE_CODE_LABELS.items()) + "\n",
        encoding="utf-8")
    print(f"max_surface_variation_pct={args.max_surface_variation_pct:g} cases={len({r[0:4] for r in rows})} certificate_rows={len(rows)} output={args.output}")


if __name__ == "__main__":
    main()
