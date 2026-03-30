import json
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from .calculators import calculate_iou

def analyze_ranking_differentiation(results_dir: Path) -> float:
    """
    Calculates the pairwise IoU of rankings across different queries.
    Lower IoU indicates higher differentiation (better ranking performance).
    """
    data_list = []
    files = sorted(results_dir.glob("*.json"))
    for f in files:
        if "_tr" in f.name: continue
        with open(f) as jf:
            ids = [str(i["id"]) for i in json.load(jf).get("ranking", [])]
            data_list.append((f.absolute(), ids))
    
    if len(data_list) < 2: return 1.0
    ious = []
    for i in range(len(data_list)):
        for j in range(i+1, len(data_list)):
            iou = calculate_iou(data_list[i][1], data_list[j][0])
            ious.append(iou)
    
    return round(float(np.mean(ious)), 3)

def analyze_ranking_consistency(consistency_dir: Path) -> float:
    """
    Calculates the self-consistency of rankings across independent trials for the same query.
    Used for Table 1 (Intra-Model IoU).
    """
    trial_ious = {}
    for f in consistency_dir.glob("query_*_tr*.json"):
        # Expecting filenames like query_001_tr1.json, query_001_tr2.json
        parts = f.name.split("_")
        q_idx = parts[1]
        if q_idx not in trial_ious: trial_ious[q_idx] = []
        with open(f) as jf: 
            rank = [str(r['id']) for r in json.load(jf).get('ranking', [])]
            trial_ious[q_idx].append(rank)
    
    avg_ious = []
    for q_idx, entries in trial_ious.items():
        if len(entries) < 2: continue
        pair_ious = []
        for i in range(len(entries)):
            for j in range(i+1, len(entries)):
                iou = calculate_iou(entries[i], entries[j])
                pair_ious.append(iou)
        avg_ious.append(np.mean(pair_ious))
    
    return round(float(np.mean(avg_ious)), 3) if avg_ious else 1.0

def analyze_ranking_impact(multiagent_dir: Path, no_ranking_dir: Path) -> Dict[str, Any]:
    """
    Quantifies the marginal impact of the ranking agent on property selection.
    Compares the full pipeline output with a version where the ranking agent is disabled.
    """
    ious = []
    ma_files = {f.name: f for f in multiagent_dir.glob("*.json") if "_tr" not in f.name}
    nr_files = {f.name: f for f in no_ranking_dir.glob("*.json")}
    
    for name, f_ma in ma_files.items():
        if name in nr_files:
            f_nr = nr_files[name]
            with open(f_ma) as fa, open(f_nr) as fb:
                da, db = json.load(fa), json.load(fb)
                iou = calculate_iou([str(r['id']) for r in da.get('ranking', [])], [str(r['id']) for r in db.get('ranking', [])])
                ious.append(iou)
    
    mean_iou = float(np.mean(ious)) if ious else 1.0
    return {"mean_iou": round(mean_iou, 3), "impact": round(1.0 - mean_iou, 3)}
