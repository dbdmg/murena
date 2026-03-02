import os
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

def calculate_iou(ids_a, ids_b):
    """Calculates Intersection over Union for two sets of IDs."""
    set_a = set(ids_a)
    set_b = set(ids_b)
    if not set_a and not set_b:
        return 1.0  # Both empty, means no change
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    if union == 0:
        return 1.0
    return intersection / union

def load_results(directory):
    """Loads all JSON results from a directory into a map {query_text: ranking_ids, relaxation_applied: bool}."""
    results = {}
    if not directory.exists():
        return results
    
    for file_path in directory.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                query = data.get("query")
                relaxation = data.get("relaxation_applied", False)
                ranking = [str(item.get("id")) for item in data.get("ranking", [])]
                if query:
                    # We store list of rankings if there are duplicates (unlikely)
                    results[query] = {
                        "ranking": ranking,
                        "relaxation": relaxation
                    }
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    return results

def main():
    base_dir = Path(__file__).resolve().parent
    ablation_root = base_dir.parent / "ablation_results"
    composed_root = base_dir.parent / "composed_results"

    models = ["gpt-oss-120b", "gpt-5-nano"]
    # Mapping Display Name -> Folder Suffix
    agent_mapping = {
        "Location": "location",
        "Proximity": "poi",
        "Building": "property_technical",
        "Energy": "ape",
        "Regulatory": "normative"
    }
    agents = list(agent_mapping.keys())
    
    # Store sensitivity results: {model: {agent: [values]}}
    sensitivity_data = {model: {agent: [] for agent in agents} for model in models}

    for model in models:
        # Load composed results for this model
        composed_model_dir = composed_root / model
        print(f"Loading composed results for {model} from {composed_model_dir}...")
        composed_map = load_results(composed_model_dir)
        print(f"Loaded {len(composed_map)} composed samples.")

        for agent in agents:
            folder_suffix = agent_mapping[agent]
            ablation_dir = ablation_root / model / f"no_{folder_suffix}"
            if not ablation_dir.exists():
                print(f"Warning: Ablation directory {ablation_dir} not found.")
                continue

            print(f"Processing ablation: {model}/{agent} (folder: no_{folder_suffix})...")
            # Load ablation results one by one to save memory if many
            for file_path in ablation_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        query = data.get("query")
                        relaxation = data.get("relaxation_applied", False)
                        
                        # Apply Filtering: "usa solo le query nelle quali non è intervenuta la relaxation"
                        if relaxation:
                            continue
                        
                        # Match with composed results
                        if query in composed_map:
                            comp_data = composed_map[query]
                            
                            # Ensure both didn't use relaxation (optional but safer)
                            if comp_data["relaxation"]:
                                continue
                                
                            ranking_ablation = [str(item.get("id")) for item in data.get("ranking", [])]
                            ranking_composed = comp_data["ranking"]
                            
                            iou = calculate_iou(ranking_ablation, ranking_composed)
                            sensitivity = 1.0 - iou
                            sensitivity_data[model][agent].append(sensitivity)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    # Calculate averages
    averages = {model: {} for model in models}
    for model in models:
        for agent in agents:
            vals = sensitivity_data[model][agent]
            avg = sum(vals) / len(vals) if vals else 0.0
            averages[model][agent] = avg
            print(f"Avg sensitivity for {model}/{agent}: {avg:.4f} (based on {len(vals)} samples)")

    # Plotting
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "text.usetex": False,  # Set to True if system has latex installed, otherwise use serif fonts
    })
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(len(agents))
    width = 0.35

    rects1 = ax.bar(x - width/2, [averages[models[0]][a] for a in agents], width, label=models[0], color='#4e79a7', edgecolor='black', linewidth=0.8)
    rects2 = ax.bar(x + width/2, [averages[models[1]][a] for a in agents], width, label=models[1], color='#f28e2b', edgecolor='black', linewidth=0.8)

    ax.set_ylabel('Sensitivity (1 - IoU)', fontsize=12)
    ax.set_title('Ablation sensitivity analysis by agent', fontsize=13, pad=20)
    ax.set_xticks(x)
    
    # Use display names directly
    ax.set_xticklabels(agents, fontsize=11)
    
    ax.legend(fontsize=10, loc='upper right', frameon=True)

    ax.yaxis.grid(True, linestyle='--', alpha=0.5)
    ax.set_axisbelow(True)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)

    autolabel(rects1)
    autolabel(rects2)

    fig.tight_layout()
    
    output_png = base_dir / "ablation_sensitivity_histogram.png"
    plt.savefig(output_png, dpi=300)
    print(f"\nGraph saved to: {output_png}")

if __name__ == "__main__":
    main()
