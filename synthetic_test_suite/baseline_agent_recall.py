import json
import os
import sys
from pathlib import Path
from typing import Set, Dict, List, Optional
import pandas as pd

try:
    import sqlglot
    from sqlglot import exp
    HAS_SQLGLOT = True
except ImportError:
    HAS_SQLGLOT = False

# --- CONFIGURATION & MAPPINGS ---

# Mapping of agents to the columns they "see" in their prompts
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

# Reverse mapping: column -> list of agents it belongs to
COLUMN_TO_AGENTS = {}
for agent, cols in AGENT_COLUMNS.items():
    for col in cols:
        if col not in COLUMN_TO_AGENTS:
            COLUMN_TO_AGENTS[col] = []
        COLUMN_TO_AGENTS[col].append(agent)

def extract_filtering_columns(sql: str) -> Set[str]:
    """
    Extracts column names used ONLY in WHERE, JOIN, and HAVING clauses.
    This ensures we only count an agent as active if it actually filtered the data.
    """
    if not sql or not HAS_SQLGLOT:
        return set()
    try:
        # We parse the full query
        parsed = sqlglot.parse_one(sql)
        cols = set()
        
        # 1. Look in WHERE clause
        where_clause = parsed.find(exp.Where)
        if where_clause:
            for col in where_clause.find_all(exp.Column):
                cols.add(col.name.lower())
        
        # 2. Look in JOIN conditions (ON clauses)
        for join in parsed.find_all(exp.Join):
            on_clause = join.find(exp.JoinAnnotation) or join.find(exp.On)
            if on_clause:
                for col in on_clause.find_all(exp.Column):
                    cols.add(col.name.lower())
                    
        # 3. Look for function calls that might wrap columns (like HAVERSINE)
        # We check all arguments of functions in the WHERE clause
        if where_clause:
            for func in where_clause.find_all(exp.Anonymous) or where_clause.find_all(exp.Func):
                for arg in func.find_all(exp.Column):
                    cols.add(arg.name.lower())

        return cols
    except Exception:
        # Fallback: if parsing fails, we look for keywords but it's less precise
        # In a real scenario, we might want to log this or try a more robust approach
        return set()

def get_expected_agents(query: str, mapping: Dict[str, str]) -> Set[str]:
    """Identifies which agents are expected to be active based on query terms."""
    expected = set()
    query_lower = query.lower()
    for term, agent in mapping.items():
        if term.lower() in query_lower:
            expected.add(agent)
    return expected

def get_predicted_agents(sql_columns: Set[str]) -> Set[str]:
    """Identifies which agents are 'activated' by the columns present in the SQL."""
    predicted = set()
    for col in sql_columns:
        if col in COLUMN_TO_AGENTS:
            for agent in COLUMN_TO_AGENTS[col]:
                predicted.add(agent)
    return predicted

def calculate_metrics(gt: Set[str], pred: Set[str]) -> Dict[str, float]:
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

def process_directory(results_dir: Path, agent_mapping: Dict[str, str], valid_ids: Optional[Set[str]] = None) -> List[Dict]:
    """Processes all JSON files in a single directory."""
    results = []
    if not results_dir.exists():
        return []

    files = list(results_dir.glob("*.json"))
    for f in files:
        query_id = f.stem.replace("query_", "")
        if valid_ids and query_id not in valid_ids:
            continue
            
        try:
            with open(f, "r") as jf:
                data = json.load(jf)
        except Exception:
            continue
            
        query = data.get("query", "")
        # Use final_sql if available, else sql
        sql = data.get("final_sql") or data.get("sql", "")
        
        # 1. Ground Truth Agents
        gt_agents = get_expected_agents(query, agent_mapping)
        if not gt_agents:
            continue
            
        # 2. Extract Filtering Columns and Map to Predicted Agents
        # STRICTOR: Only look at WHERE/JOIN
        sql_columns = extract_filtering_columns(sql)
        
        # Handle cases where columns are implicitly used in HAVERSINE but might not be standard
        if not sql_columns and sql:
            # Minimal fallback: look for lat/lon/mq etc in lowercase string
            sql_lower = sql.lower()
            for col in COLUMN_TO_AGENTS:
                if col in sql_lower:
                    # Check if it looks like it's in a filter
                    # Simple heuristic: must be after WHERE
                    where_idx = sql_lower.find("where")
                    if where_idx != -1 and col in sql_lower[where_idx:]:
                        sql_columns.add(col)
        
        pred_agents = get_predicted_agents(sql_columns)
        
        # 3. Calculate Metrics
        m = calculate_metrics(gt_agents, pred_agents)
        
        results.append({
            "query_id": query_id,
            "query": query,
            "gt_agents": sorted(list(gt_agents)),
            "pred_agents": sorted(list(pred_agents)),
            "precision": m["precision"],
            "recall": m["recall"],
            "f1": m["f1"]
        })
    return results

def run_recall_analysis():
    synthetic_test_dir = Path("/home/mdeluca/real-estate-ai/synthetic_test_suite")
    results_root = synthetic_test_dir / "results" / "outputs"
    mapping_file = synthetic_test_dir / "agent_mapping.json"
    sensitivity_csv = synthetic_test_dir / "results" / "sensitivity_queries_suite.csv"
    
    if not mapping_file.exists():
        print(f"Mapping file not found: {mapping_file}")
        return

    with open(mapping_file, "r") as f:
        agent_mapping = json.load(f)
        
    valid_ids = load_valid_query_ids(sensitivity_csv)
    print(f"Loaded {len(valid_ids)} valid query IDs from sensitivity_queries_suite.csv")

    configs = [
        "benchmarks/gpt-oss-120b/full",
        "benchmarks/vllm-gemma3-27b/full",
        "benchmarks/vllm-qwen/full",
        "sensitivity/gpt-5.4/baseline_columns",
        "sensitivity/gpt-5.4/baseline_stats"
    ]
    
    summary = []
    
    for config in configs:
        target_dir = results_root / config
        print(f"Processing {config}...")
        
        results = process_directory(target_dir, agent_mapping, valid_ids)
        if not results:
            print(f"  Warning: No valid results found in {config}")
            continue
            
        df = pd.DataFrame(results)
        
        summary.append({
            "Configuration": config,
            "Sample Size": len(df),
            "Mean Precision": round(df["precision"].mean(), 3),
            "Mean Recall": round(df["recall"].mean(), 3),
            "Mean F1": round(df["f1"].mean(), 3)
        })
        
        # Save individual detailed results
        safe_name = config.replace("/", "_")
        output_csv = target_dir / f"agent_recall_analysis_STRICT_{safe_name}.csv"
        df.to_csv(output_csv, index=False)

    summary_df = pd.DataFrame(summary)
    print("\n--- BASELINE AGENT AGENT-PRECISION/RECALL REPORT (STRICT WHERE CLAUSE) ---")
    print(summary_df.to_string(index=False))
    
    # Save global summary
    summary_df.to_csv(results_root / "baseline_agent_metrics_summary_strict.csv", index=False)

def load_valid_query_ids(csv_path: Path) -> Set[str]:
    if not csv_path.exists():
        return set()
    df = pd.read_csv(csv_path)
    return {str(val) for val in df["query_id"].tolist()}

if __name__ == "__main__":
    run_recall_analysis()
