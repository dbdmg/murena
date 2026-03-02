import os
import json
import csv
from pathlib import Path
from typing import Set, List
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.cluster.hierarchy import linkage, dendrogram, leaves_list
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

def plot_distribution(matrix: np.ndarray, output_path: Path):
    """
    Plots the distribution of IoU scores (excluding the diagonal).
    """
    # Extract upper triangle to avoid duplicates and the diagonal (which is always 1.0)
    num_queries = matrix.shape[0]
    triu_indices = np.triu_indices(num_queries, k=1)
    values = matrix[triu_indices]
    
    plt.figure(figsize=(10, 6))
    plt.hist(values, bins=50, color='#2c3e50', edgecolor='white', alpha=0.8)
    
    plt.title('Distribution of query results similarity (IoU)', fontsize=14, pad=15)
    plt.xlabel('IoU score', fontsize=12)
    plt.ylabel('Frequency (number of query pairs)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.savefig(output_path.with_suffix('.pdf'))
    plt.close()
    print(f"Distribution plot saved to {output_path}")

def plot_heatmap(matrix: np.ndarray, num_queries: int, output_path: Path):
    """
    Generates a professional heatmap of the IoU matrix for academic publication.
    
    Style: ECML PKDD / Scientific Paper
    """
    # Use a clean font style
    plt.rcParams.update({
        'font.family': 'serif',
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 14,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.titlesize': 16
    })

    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Using 'magma' or 'viridis' for a professional look
    im = ax.imshow(matrix, cmap='magma', interpolation='nearest', aspect='equal')
    
    # Add a refined colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('IoU (intersection over union)', rotation=270, labelpad=15)
    
    ax.set_title('Cross-query convergence analysis via IoU', pad=20)
    ax.set_xlabel('Query index', labelpad=10)
    ax.set_ylabel('Query index', labelpad=10)
    
    # Handle ticks for high density (e.g. 298 queries)
    if num_queries > 50:
        step = 50
        ticks = np.arange(0, num_queries, step)
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.set_xticklabels([str(t) for t in ticks])
        ax.set_yticklabels([str(t) for t in ticks])
    else:
        ax.set_xticks(np.arange(num_queries))
        ax.set_yticks(np.arange(num_queries))

    # Add minor gridlines to help guide the eye
    ax.set_xticks(np.arange(-.5, num_queries, 10 if num_queries > 100 else 1), minor=True)
    ax.set_yticks(np.arange(-.5, num_queries, 10 if num_queries > 100 else 1), minor=True)
    ax.grid(which='minor', color='w', linestyle='-', linewidth=0.1, alpha=0.3)

    plt.tight_layout()
    
    # Save as PNG (300 DPI) and PDF (vector for LaTeX)
    print(f"Saving high-res plots to {output_path} and its .pdf version...")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.savefig(output_path.with_suffix('.pdf'), bbox_inches='tight')
    plt.close()

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
    csv_output = output_dir / "iou_matrix.csv"
    plot_output = output_dir / "iou_heatmap.png"
    dist_output = output_dir / "iou_distribution.png"
    
    # 1. Load data
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return

    json_files = sorted(list(results_dir.glob("*.json")), key=lambda x: x.name)
    if not json_files:
        print(f"No JSON results found in {results_dir}")
        return

    print(f"[CONFIG] Analyzing model: {args.model}")
    print(f"Loading IDs from {len(json_files)} files...")
    query_ids = []
    filenames = []
    
    for f in json_files:
        try:
            with open(f, 'r') as jf:
                data = json.load(jf)
                # Exclude queries where relaxation was applied
                if data.get("relaxation_applied") is True:
                    print(f"Skipping {f.name}: relaxation applied.")
                    continue

                # Extrating only the IDs, ignoring scores
                ranking = data.get("ranking", [])
                ids = {str(item["id"]) for item in ranking if "id" in item}
                query_ids.append(ids)
                filenames.append(f.stem) # use stem (e.g. 'query_001') for cleaner labels
        except Exception as e:
            print(f"Failed to read {f.name}: {e}")

    num_queries = len(query_ids)
    if num_queries == 0:
        print("No valid queries found after filtering.")
        return

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

    # 3. Clustering
    print("Performing hierarchical clustering for better visualization...")
    # Convert IoU (similarity) to Distance (1 - similarity)
    # We use a small epsilon to avoid negative zeros
    distance_matrix = np.maximum(0, 1 - iou_matrix)
    
    # Hierarchical clustering
    try:
        # Use Ward linkage or complete linkage
        linkage_matrix = linkage(squareform(distance_matrix), method='ward')
        # Get the new order of labels
        reordered_indices = leaves_list(linkage_matrix)
        
        clustered_matrix = iou_matrix[reordered_indices, :][:, reordered_indices]
        print("Clustering complete.")
        
        # 4. Create Heatmap
        print("Generating academic-grade clustered heatmap...")
        plot_heatmap(clustered_matrix, num_queries, plot_output)
    except Exception as e:
        print(f"Clustering failed (probably too few queries or constant values): {e}")
        print("Generating standard heatmap instead...")
        plot_heatmap(iou_matrix, num_queries, plot_output)

    # 5. Create Distribution Plot
    plot_distribution(iou_matrix, dist_output)
    
    print(f"Done! Results available in {output_dir}")

if __name__ == "__main__":
    main()
