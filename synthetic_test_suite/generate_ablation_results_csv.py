import json
import csv
import os
from pathlib import Path

def generate_csv():
    """
    Reads all JSON result files from the ablation_results directory (including subdirectories)
    and creates a summary CSV.
    """
    base_dir = Path(__file__).parent
    results_dir = base_dir / "ablation_results"
    output_csv = base_dir / "ablation_results_summary.csv"
    
    if not results_dir.exists():
        print(f"Error: {results_dir} folder not found.")
        return
        
    data = []
    
    # Recursively find all query_*.json files
    json_files = sorted(results_dir.rglob("query_*.json"))
    
    for json_file in json_files:
        # The parent directory name tells us which agent was disabled
        config_name = json_file.parent.name
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                query = content.get("query", "")
                count = content.get("results_count", 0)
                time = content.get("execution_time_ms", 0)
                relaxed = 1 if content.get("relaxation_applied", False) else 0
                disabled = ", ".join(content.get("disabled_agents", [])) or "none"
                
                # Extract main weights if available
                logic = content.get("ranking_logic", {})
                weights = logic.get("original_weights", {})
                
                row = {
                    "config": config_name,
                    "disabled_agents": disabled,
                    "query": query,
                    "results_count": count if count is not None else 0,
                    "execution_time_ms": time,
                    "is_relaxed": relaxed
                }
                
                # Add weights to CSV
                for agent, weight in weights.items():
                    row[f"weight_{agent}"] = weight
                    
                data.append(row)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error processing {json_file.name}: {e}")

    if not data:
        print("No results found to summarize.")
        return

    # Determine fieldnames
    fieldnames = ["config", "disabled_agents", "query", "results_count", "execution_time_ms", "is_relaxed"]
    weight_cols = sorted({k for row in data for k in row.keys() if k.startswith("weight_")})
    fieldnames.extend(weight_cols)
    
    try:
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"Successfully created CSV: {output_csv}")
    except IOError as e:
        print(f"Error writing CSV: {e}")

if __name__ == "__main__":
    generate_csv()
