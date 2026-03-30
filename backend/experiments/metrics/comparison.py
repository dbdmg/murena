import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from .calculators import calculate_iou, extract_sql_columns

def analyze_architecture_comparison(murena_dir: Path, baseline_dir: Path) -> Dict[str, Any]:
    """
    Compares the generated SQL column sets between MURENA and monolithic baselines.
    Used for Table 2 (Column-set IoU).
    """
    sql_ious, ranking_ious = [], []
    murena_files = {f.name: f for f in murena_dir.glob("query_*.json") if "_tr" not in f.name}
    baseline_files = {f.name: f for f in baseline_dir.glob("query_*.json")}
    
    for name, f_m in murena_files.items():
        if name in baseline_files:
            f_b = baseline_files[name]
            with open(f_m) as fm, open(f_b) as fb:
                da, db = json.load(fm), json.load(fb)
                # Compare SQL structure
                cols_m = extract_sql_columns(da.get("final_sql", ""))
                cols_b = extract_sql_columns(db.get("final_sql", ""))
                iou_sql = calculate_iou(list(cols_m), list(cols_b))
                sql_ious.append(iou_sql)
                
                # Compare final rankings
                iou_rank = calculate_iou([str(r['id']) for r in da.get('ranking', [])], [str(r['id']) for r in db.get('ranking', [])])
                ranking_ious.append(iou_rank)
                
    return {
        "mean_sql_iou": round(float(np.mean(sql_ious)), 3) if sql_ious else 0.0, 
        "mean_ranking_iou": round(float(np.mean(ranking_ious)), 3) if ranking_ious else 0.0, 
        "sample_size": len(sql_ious)
    }

def analyze_domain_coverage(results_dir: Path) -> float:
    """
    Measures the thematic domain coverage defined in the paper.
    Used for Table 2 (Domain F1).
    """
    domains = ["energy", "location", "proximity", "regulatory", "property_technical"]
    coverage_scores = []
    
    for f in results_dir.glob("*.json"):
        with open(f) as jf:
            data = json.load(jf)
            sql = data.get("final_sql", "").lower()
            cols = extract_sql_columns(sql)
            # A domain is covered if at least one corresponding column appears in the SQL.
            covered_domains = 0
            for d in domains:
                # Approximate columns to domain mapping for F1-score
                # (Actual mapping should be consistent with the paper's contribution statement)
                matching_cols = False
                if d == "energy" and any(c in cols for c in ["classe_energetica_ape", "epglnren_ape"]): matching_cols = True
                elif d == "location" and any(c in cols for c in ["indirizzo", "latitudine", "longitudine"]): matching_cols = True
                elif d == "proximity" and any(c in cols for c in ["sanita", "mobilita", "verde", "sport"]): matching_cols = True
                elif d == "regulatory" and any(c in cols for c in ["superficie_di_riferimento_mq", "tipologia_bene_immobile"]): matching_cols = True
                elif d == "property_technical" and any(c in cols for c in ["epoca_costruzione", "id"]): matching_cols = True
                
                if matching_cols: covered_domains += 1
            
            coverage_scores.append(covered_domains / len(domains))
            
    return round(float(np.mean(coverage_scores)), 3) if coverage_scores else 0.0
