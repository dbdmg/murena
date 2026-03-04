import os
import json
import csv
from pathlib import Path
from typing import Set, List, Dict, Any
import numpy as np
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

def calculate_iou(set1: Set[str], set2: Set[str]) -> float:
    """
    Calculates the Intersection over Union (IoU) of two sets of IDs.
    """
    if not set1 and not set2:
        return 1.0
    
    intersection_size = len(set1.intersection(set2))
    union_size = len(set1.union(set2))
    
    if union_size == 0:
        return 0.0
        
    return intersection_size / union_size

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=["gpt-oss-120b", "gpt-5-nano"], default="gpt-oss-120b", help="LLM model flavor")
    args = parser.parse_args()

    # Detect the directory where the script is located
    script_dir = Path(__file__).parent.absolute()
    
    # The results are in the parent directory's 'composed_results' folder, now model-specific
    results_dir = script_dir.parent / "composed_results" / args.model
    
    # Model-specific output directory
    output_dir = script_dir / args.model
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Outputs in the model-specific directory
    json_output = output_dir / "analysis.json"
    
    # 1. Load data
    if not results_dir.exists():
        print(json.dumps({"error": f"Results directory not found: {results_dir}"}))
        return

    json_files = sorted(list(results_dir.glob("*.json")), key=lambda x: x.name)
    if not json_files:
        print(json.dumps({"error": f"No JSON results found in {results_dir}"}))
        return

    query_ids = []
    filenames = []
    skipped_count = 0
    
    for f in json_files:
        try:
            with open(f, 'r') as jf:
                data = json.load(jf)
                # Exclude queries where relaxation was applied
                if data.get("relaxation_applied") is True:
                    skipped_count += 1
                    continue

                # Extracting only the IDs, ignoring scores
                ranking = data.get("ranking", [])
                ids = {str(item["id"]) for item in ranking if "id" in item}
                query_ids.append(ids)
                filenames.append(f.stem)
        except Exception as e:
            continue

    num_queries = len(query_ids)
    if num_queries == 0:
        print(json.dumps({"error": "No valid queries found after filtering."}))
        return

    iou_matrix = np.zeros((num_queries, num_queries))

    for i in range(num_queries):
        for j in range(i, num_queries): # Symmetric matrix
            iou = calculate_iou(query_ids[i], query_ids[j])
            iou_matrix[i, j] = iou
            iou_matrix[j, i] = iou

    # 2. Calculate statistics
    # Extract upper triangle to avoid duplicates and the diagonal
    triu_indices = np.triu_indices(num_queries, k=1)
    values = iou_matrix[triu_indices]
    
    # Handle case with only 1 query (no pairs)
    if len(values) > 0:
        stats = {
            "mean_iou": float(np.mean(values)),
            "median_iou": float(np.median(values)),
            "std_iou": float(np.std(values)),
            "min_iou": float(np.min(values)),
            "max_iou": float(np.max(values)),
            "p25_iou": float(np.percentile(values, 25)),
            "p75_iou": float(np.percentile(values, 75)),
            "zero_iou_percentage": float(np.mean(values == 0) * 100)
        }
    else:
        stats = {
            "mean_iou": 1.0,
            "median_iou": 1.0,
            "std_iou": 0.0,
            "min_iou": 1.0,
            "max_iou": 1.0,
            "p25_iou": 1.0,
            "p75_iou": 1.0,
            "zero_iou_percentage": 0.0
        }

    # Identify most similar pairs (excluding identity)
    top_pairs = []
    if num_queries > 1:
        # Get coordinates of highest values in upper triangle
        flat_indices = np.argsort(values)[::-1][:10] # Top 10
        for idx in flat_indices:
            row_idx = triu_indices[0][idx]
            col_idx = triu_indices[1][idx]
            top_pairs.append({
                "query_a": filenames[row_idx],
                "query_b": filenames[col_idx],
                "iou": float(iou_matrix[row_idx, col_idx])
            })

    analysis = {
        "model": args.model,
        "total_files_checked": len(json_files),
        "queries_analyzed": num_queries,
        "queries_skipped_relaxation": skipped_count,
        "statistics": stats,
        "top_similar_pairs": top_pairs
    }

    # 4. Save and output JSON
    with open(json_output, 'w') as f:
        json.dump(analysis, f, indent=4)
    
    print(json.dumps(analysis, indent=4))

if __name__ == "__main__":
    main()
