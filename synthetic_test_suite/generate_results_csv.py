import json
import csv
import os
from pathlib import Path

def generate_csv():
    """
    Reads all JSON result files from the composed_results directory and creates a summary CSV.
    The CSV contains the 'query' and 'results_count' for each result.
    """
    base_dir = Path("/Users/marcodeluca/Downloads/real-estate-ai/synthetic_test_suite")
    results_dir = base_dir / "composed_results"
    output_csv = base_dir / "results_summary.csv"
    
    data = []
    
    # Get all JSON files and sort them to maintain order
    json_files = sorted(results_dir.glob("query_*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                query = content.get("query", "")
                results_count = content.get("results_count", 0)
                # Handle cases where results_count might be None or missing
                if results_count is None:
                    results_count = 0
                data.append({"query": query, "results_count": results_count})
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error processing {json_file.name}: {e}")

    # Write to CSV
    fieldnames = ["query", "results_count"]
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
