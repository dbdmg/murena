import csv
import io
import logging
import threading
import contextlib
import fcntl
from pathlib import Path
from typing import List, Any, Optional, Dict, Set
import pandas as pd
from contextvars import ContextVar
import numpy as np

try:
    import sqlglot
    from sqlglot import exp
    HAS_SQLGLOT = True
except ImportError:
    HAS_SQLGLOT = False

# --- CONTEXT VARIABLES ---
query_ctx: ContextVar[str] = ContextVar("query_ctx", default="SYSTEM")
experiment_ctx: ContextVar[str] = ContextVar("experiment_ctx", default="N/A")
log_dir_ctx: ContextVar[Optional[Path]] = ContextVar("log_dir_ctx", default=None)

def format_csv_line(row: List[Any]) -> str:
    """Helper to generate a properly quoted CSV line."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="")
    writer.writerow(row)
    return output.getvalue()

class CsvLoggingFilter(logging.Filter):
    def filter(self, record):
        record.query_id = query_ctx.get()
        record.experiment_id = experiment_ctx.get()
        return True

class CsvFormatter(logging.Formatter):
    def __init__(self, run_id: str, datefmt: Optional[str] = None):
        super().__init__(datefmt=datefmt)
        self.run_id = run_id

    def format(self, record):
        query_id = getattr(record, 'query_id', 'SYSTEM')
        experiment_id = getattr(record, 'experiment_id', 'N/A')
        msg = record.getMessage().strip()
        timestamp = self.formatTime(record, self.datefmt)
        return format_csv_line([timestamp, self.run_id, experiment_id, query_id, record.levelname, record.name, msg])

class DynamicFolderHandler(logging.Handler):
    """Routes logs to the specific folder of the active experiment."""
    def __init__(self, fallback_path: Path):
        super().__init__()
        self.fallback_path = fallback_path
        self._handles = {}
        self._lock = threading.Lock()

    def _get_target_path(self) -> Path:
        current_dir = log_dir_ctx.get()
        if current_dir:
            return current_dir / "execution.csv"
        return self.fallback_path

    def emit(self, record):
        try:
            target_path = self._get_target_path()
            msg = self.format(record)
            
            with self._lock:
                if target_path not in self._handles:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    is_new = not target_path.exists()
                    f = open(target_path, "a", encoding='utf-8')
                    if is_new:
                        f.write(format_csv_line(["timestamp", "run_id", "experiment", "query", "level", "logger", "message"]) + "\n")
                    self._handles[target_path] = f
                
                self._handles[target_path].write(msg + "\n")
                self._handles[target_path].flush()
        except Exception:
            self.handleError(record)

@contextlib.contextmanager
def file_lock(path: Path):
    """File lock using fcntl for cross-process synchronization."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    if not lock_path.exists():
        lock_path.touch()
    
    with open(lock_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

def safe_update_csv_column(csv_path: Path, index: int, column: str, value: Any):
    """Safely updates a single cell in a CSV file across processes."""
    with file_lock(csv_path):
        df = pd.read_csv(csv_path)
        if column not in df.columns:
            df[column] = 0
        df.at[index, column] = value
        df.to_csv(csv_path, index=False)

def safe_read_csv(csv_path: Path) -> pd.DataFrame:
    """Safely reads a CSV file with a lock."""
    with file_lock(csv_path):
        return pd.read_csv(csv_path)

def safe_save_csv(df: pd.DataFrame, csv_path: Path):
    """Safely saves a CSV file with a lock."""
    with file_lock(csv_path):
        df.to_csv(csv_path, index=False)

def setup_logging(run_id: str, execution_csv_path: Path):
    """Initializes the logging system."""
    handler = DynamicFolderHandler(fallback_path=execution_csv_path)
    handler.addFilter(CsvLoggingFilter())
    handler.setFormatter(CsvFormatter(run_id=run_id, datefmt='%Y-%m-%d %H:%M:%S'))
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)

# --- METRICS & ANALYSIS ---

def calculate_iou(list_a: List[str], list_b: List[str]) -> float:
    """Calculates Intersection over Union (IoU) for two lists."""
    if not list_a and not list_b: return 1.0
    set_a, set_b = set(list_a), set(list_b)
    inter = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return inter / union if union > 0 else 0.0

def calculate_f1(gt: Set[str], pred: Set[str]) -> Dict[str, float]:
    """Calculates precision, recall, and F1 score."""
    if not gt:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    tp = len(gt.intersection(pred))
    recall = tp / len(gt)
    precision = tp / len(pred) if pred else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3)
    }

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

def generate_report(benchmark_results: Dict[str, Any], sensitivity_results: Dict[str, Any], models: List[str]) -> str:
    """Generates a comprehensive Markdown report of all experimental results."""
    report_md = "# Experimental Evaluation Report: Real Estate AI Agentic Framework\n\n"
    report_md += "This report summarizes the performance, robustness, and architectural fidelity of the multi-agent framework.\n\n"
    
    for mod in models:
        # ... (full report generation logic)
        pass
    return report_md
