import json
import asyncio
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

async def evaluate_with_judge(model_key: str, results_dir: Path, judge_model: str = "gpt-5.4") -> Dict[str, Any]:
    """
    LLM-as-a-judge protocol for evaluating Pros/Cons quality.
    Evaluates generated justifications against original property data.
    Ensures alignment with Table 1 qualitative metrics.
    """
    judge_dir = results_dir.parent / "judge_eval"
    judge_dir.mkdir(parents=True, exist_ok=True)
    
    all_files = list(results_dir.glob("*.json"))
    if not all_files: return {}

    # Aggregate scores from judge results
    judge_results = []
    for f in judge_dir.glob("*.json"):
        with open(f) as jf:
            judge_results.append(json.load(jf))

    if not judge_results:
        logging.warning(f"No judge evaluation results found in {judge_dir}. Run judge script first.")
        return {}

    metrics = {
        "acc_pros": [], "acc_cons": [], 
        "rel_pros": [], "rel_cons": []
    }
    
    for r in judge_results:
        # Pros
        for p in r.get("pros", []):
            metrics["acc_pros"].append(1 if p.get("accuracy") else 0)
            metrics["rel_pros"].append(1 if p.get("relevance") else 0)
        # Cons
        for c in r.get("cons", []):
            metrics["acc_cons"].append(1 if c.get("accuracy") else 0)
            metrics["rel_cons"].append(1 if c.get("relevance") else 0)

    final = {
        "samples": len(judge_results),
        "accuracy_pros": round(float(np.mean(metrics["acc_pros"])), 3) if metrics["acc_pros"] else 0.0,
        "accuracy_cons": round(float(np.mean(metrics["acc_cons"])), 3) if metrics["acc_cons"] else 0.0,
        "relevance_pros": round(float(np.mean(metrics["rel_pros"])), 3) if metrics["rel_pros"] else 0.0,
        "relevance_cons": round(float(np.mean(metrics["rel_cons"])), 3) if metrics["rel_cons"] else 0.0,
    }
    final["accuracy_avg"] = round((final["accuracy_pros"] + final["accuracy_cons"]) / 2, 3)
    final["relevance_avg"] = round((final["relevance_pros"] + final["relevance_cons"]) / 2, 3)
    
    return final
