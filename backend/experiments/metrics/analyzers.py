import json
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from .calculators import calculate_iou, calculate_f1, get_activated_agents, calculate_pmr

def analyze_activation(results_dir: Path, mapping_path: Path, model_name: str) -> Dict[str, Any]:
    """
    Analyzes agent activation precision, recall, and F1.
    Calculates PMR (Perfect Mapping Rate) for the model.
    """
    if not mapping_path.exists():
        logging.error(f"Mapping path {mapping_path} not found.")
        return {}
        
    with open(mapping_path) as mf:
        agent_mapping = json.load(mf)
        
    agents = sorted(list(set(agent_mapping.values())))
    metrics = {a: {"tp": 0, "fp": 0, "fn": 0} for a in agents}
    total_jaccard, perfect_count = 0.0, 0
    files = list(results_dir.glob("*.json"))
    
    if not files:
        return {}

    for f in files:
        with open(f) as jf:
            data = json.load(jf)
            query = data.get("query", "").lower()
            sql = data.get("final_sql", "")
            
            # Agents predicted from generated SQL
            pred_agents = get_activated_agents(sql)
            
            # Ground truth expected agents
            expected = {a for k, a in agent_mapping.items() if k.lower() in query}
            
            if not expected:
                continue

            # Check for exact match (PMR)
            if calculate_pmr(expected, pred_agents):
                perfect_count += 1
            
            # Update metrics per single agent
            for a in agents:
                is_ex, is_ac = a in expected, a in pred_agents
                if is_ex and is_ac: metrics[a]["tp"] += 1
                elif not is_ex and is_ac: metrics[a]["fp"] += 1
                elif is_ex and not is_ac: metrics[a]["fn"] += 1
            
            j = calculate_iou(list(expected), list(pred_agents))
            total_jaccard += j
            
    pmr = round(perfect_count / len(files), 3) if files else 0
    mean_jaccard = round(total_jaccard / len(files), 3) if files else 0
    
    agent_metrics = {}
    total_precision, total_recall, total_f1 = 0.0, 0.0, 0.0
    active_agents_count = 0

    for a, m in metrics.items():
        precision = m["tp"] / (m["tp"] + m["fp"]) if (m["tp"]+m["fp"]) > 0 else 0.0
        recall = m["tp"] / (m["tp"] + m["fn"]) if (m["tp"]+m["fn"]) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        agent_metrics[a] = {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}
        
        if (m["tp"] + m["fn"]) > 0:
            total_precision += precision
            total_recall += recall
            total_f1 += f1
            active_agents_count += 1

    summary = {
        "model": model_name, 
        "pmr": pmr,  # Perfect Mapping Rate
        "mean_jaccard": mean_jaccard, 
        "mean_precision": round(total_precision / active_agents_count, 3) if active_agents_count else 0.0,
        "mean_recall": round(total_recall / active_agents_count, 3) if active_agents_count else 0.0,
        "mean_f1": round(total_f1 / active_agents_count, 3) if active_agents_count else 0.0
    }
    
    return {"summary": summary, "agent_metrics": agent_metrics}
