import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, List

def analyze_performance(results_dir: Path) -> Dict[str, Any]:
    """
    Computes average and median latency for queries in a directory.
    Output used for Table 1 and performance evaluation.
    """
    durations = []
    for f in results_dir.glob("*.json"):
        with open(f) as jf:
            data = json.load(jf)
            if "execution_time_ms" in data:
                durations.append(data["execution_time_ms"])
    
    if not durations:
        return {"mean_ms": 0.0, "median_ms": 0.0, "sample_size": 0}
        
    return {
        "mean_ms": round(float(np.mean(durations)), 2),
        "median_ms": round(float(np.median(durations)), 2),
        "sample_size": len(durations)
    }
