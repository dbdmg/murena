import json
import numpy as np
import pandas as pd
import re
from pathlib import Path
from typing import List, Dict, Any, Set, Optional

try:
    import sqlglot
    from sqlglot import exp
    HAS_SQLGLOT = True
except ImportError:
    HAS_SQLGLOT = False

# --- BASE METRICS ---

def calculate_iou(list_a: List[str], list_b: List[str]) -> float:
    """Calculates Intersection over Union for two lists."""
    if not list_a and not list_b: return 1.0
    set_a, set_b = set(list_a), set(list_b)
    inter = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return inter / union if union > 0 else 0.0

def calculate_jaccard(list_a: List[str], list_b: List[str]) -> float:
    """Alias for IoU."""
    return calculate_iou(list_a, list_b)

def calculate_f1(gt: Set[str], pred: Set[str]) -> Dict[str, float]:
    """Calculates precision, recall, and f1 score."""
    if not gt:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    
    tp = len(gt.intersection(pred))
    recall = tp / len(gt)
    precision = tp / len(pred) if pred else 0.0
    
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * (precision * recall) / (precision + recall)
        
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3)
    }

# --- SQL ANALYSIS ---

AGENT_COLUMNS = {
    "property_technical": {
        "tipologia_bene_immobile", "epoca_costruzione", "id", "codice_comune", 
        "foglio", "particella", "subalterno", "numero_immobili_per_catasto", 
        "superficie_di_riferimento_mq"
    },
    "location": {
        "indirizzo", "numero_civico", "latitudine", "longitudine", "zona_omi"
    },
    "ape": {
        "classe_energetica_ape", "epglnren_ape", "classe_target_ape", 
        "ape_score_classe", "ape_score_impianto", "ape_score_involucro", 
        "ape_score_rinnovabili", "ape_score_total"
    },
    "normative": {
        "superficie_di_riferimento_mq", "tipologia_bene_immobile"
    },
    "poi": {
        "sanita", "mobilita", "verde", "sport", "commerciale", "educazione"
    }
}

COLUMN_TO_AGENTS = {}
for agent, cols in AGENT_COLUMNS.items():
    for col in cols:
        if col not in COLUMN_TO_AGENTS:
            COLUMN_TO_AGENTS[col] = []
        COLUMN_TO_AGENTS[col].append(agent)

def extract_sql_columns(sql: str) -> Set[str]:
    """Extracts column names used in WHERE, JOIN, and HAVING clauses."""
    if not sql or not HAS_SQLGLOT:
        return set()
    try:
        parsed = sqlglot.parse_one(sql)
        cols = set()
        where_clause = parsed.find(exp.Where)
        if where_clause:
            for col in where_clause.find_all(exp.Column):
                cols.add(col.name.lower())
        for join in parsed.find_all(exp.Join):
            on_clause = join.find(exp.JoinAnnotation) or join.find(exp.On)
            if on_clause:
                for col in on_clause.find_all(exp.Column):
                    cols.add(col.name.lower())
        if where_clause:
            for func in where_clause.find_all(exp.Anonymous) or where_clause.find_all(exp.Func):
                for arg in func.find_all(exp.Column):
                    cols.add(arg.name.lower())
        return cols
    except Exception:
        # Fallback heuristic
        cols = set()
        sql_lower = sql.lower()
        for col in COLUMN_TO_AGENTS:
            if col in sql_lower:
                where_idx = sql_lower.find("where")
                if where_idx != -1 and col in sql_lower[where_idx:]:
                    cols.add(col)
        return cols

def get_activated_agents(sql: str) -> Set[str]:
    """Identifies which agents are 'activated' by the columns present in the SQL."""
    cols = extract_sql_columns(sql)
    activated = set()
    for col in cols:
        if col in COLUMN_TO_AGENTS:
            for agent in COLUMN_TO_AGENTS[col]:
                activated.add(agent)
    return activated

def calculate_architecture_agreement(sql: str, gt_agents: Set[str]) -> float:
    """Compares activated agents in SQL against ground truth agents."""
    pred_agents = get_activated_agents(sql)
    return calculate_iou(list(gt_agents), list(pred_agents))
