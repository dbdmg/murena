import csv
import io
import logging
import threading
import contextlib
import fcntl
from pathlib import Path
from typing import List, Any, Optional, Dict
import pandas as pd
from contextvars import ContextVar

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
