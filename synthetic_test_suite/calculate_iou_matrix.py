import os
import json
import csv
from pathlib import Path
from typing import Set, List
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def calculate_iou(set1: Set[str], set2: Set[str]) -> float:
    """
    Calculates the Intersection over Union (IoU) of two sets of IDs.
    
    Time Complexity: O(min(len(set1), len(set2))) for intersection, 
    O(len(set1) + len(set2)) for union.
    """
    if not set1 and not set2:
        return 1.0
    
    intersection_size = len(set1.intersection(set2))
    union_size = len(set1.union(set2))
    
    if union_size == 0:
        return 0.0
        
    return intersection_size / union_size

def plot_heatmap(matrix: np.ndarray, labels: List[str], output_path: Path):
    """
    Generates and saves a heatmap of the IoU matrix.
    """
    plt.figure(figsize=(12, 10))
    # Using matplotlib directly since seaborn might not be available
    plt.imshow(matrix, cmap='viridis', interpolation='nearest')
    plt.colorbar(label='IoU Score')
    
    plt.title('Queries Results IoU Matrix')
    plt.xlabel('Query Index')
    plt.ylabel('Query Index')
    
    # If there are too many labels, don't show all of them to keep it readable
    if len(labels) <= 50:
        plt.xticks(range(len(labels)), labels, rotation=90, fontsize=8)
        plt.yticks(range(len(labels)), labels, fontsize=8)
    else:
        # Show only some indices
        step = len(labels) // 20
        indices = range(0, len(labels), step)
        plt.xticks(indices, [labels[i] for i in indices], rotation=45, fontsize=8)
        plt.yticks(indices, [labels[i] for i in indices], fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()

def main():
    base_path = Path("/Users/marcodeluca/Downloads/real-estate-ai/synthetic_test_suite")
    results_dir = base_path / "composed_results"
    csv_output = base_path / "iou_matrix.csv"
    plot_output = base_path / "iou_heatmap.png"
    
    # 1. Load data
    json_files = sorted(list(results_dir.glob("*.json")), key=lambda x: x.name)
    if not json_files:
        print("No JSON results found.")
        return

    print(f"Loading IDs from {len(json_files)} files...")
    query_ids = []
    filenames = []
    
    for f in json_files:
        try:
            with open(f, 'r') as jf:
                data = json.load(jf)
                # Extrating only the IDs, ignoring scores
                ranking = data.get("ranking", [])
                ids = {str(item["id"]) for item in ranking if "id" in item}
                query_ids.append(ids)
                filenames.append(f.stem) # use stem (e.g. 'query_001') for cleaner labels
        except Exception as e:
            print(f"Failed to read {f.name}: {e}")

    num_queries = len(query_ids)
    iou_matrix = np.zeros((num_queries, num_queries))

    print(f"Calculating {num_queries}x{num_queries} IoU matrix...")
    for i in range(num_queries):
        for j in range(i, num_queries): # Symmetric matrix
            iou = calculate_iou(query_ids[i], query_ids[j])
            iou_matrix[i, j] = iou
            iou_matrix[j, i] = iou
        if (i+1) % 50 == 0:
            print(f"Progress: {i+1}/{num_queries} rows processed.")

    # 2. Save CSV
    print(f"Saving matrix to {csv_output}...")
    df = pd.DataFrame(iou_matrix, index=filenames, columns=filenames)
    df.to_csv(csv_output)

    # 3. Create Heatmap
    print(f"Creating heatmap at {plot_output}...")
    plot_heatmap(iou_matrix, filenames, plot_output)
    
    print("Done!")

if __name__ == "__main__":
    main()
