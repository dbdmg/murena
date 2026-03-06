import json
import os
import itertools
import csv
from collections import defaultdict

def analyze_relaxation_stats(base_path: str):
    json_path = os.path.join(base_path, "query_variables_possibilities.json")
    results_base_dir = os.path.join(base_path, "composed_results")
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Define keys and ordering according to template logic in generate_compositions.py
    keys_order = [
        "tipologia_immobile",
        "punto_di_interesse",
        "metratura_totale",
        "classe_energetica",
        "progetto_destinazione_uso",
        "servizi_accessori"
    ]
    
    # Prepare option lists
    option_lists = []
    for key in keys_order:
        values = data.get(key, [])
        if key == "tipologia_immobile":
            option_lists.append([(v, key) for v in values])
        else:
            option_lists.append([(v, key) for v in values] + [(None, key)])
            
    all_compositions = []
    
    # Generate Cartesian product
    for combo in itertools.product(*option_lists):
        # Count non-None variables
        var_count = sum(1 for val, key in combo if val is not None)
        
        # Build query string (to match logical order/sorting)
        tipo = combo[0][0]
        query = f"Cerca un {tipo}"
        
        # Replicate generate_compositions.py logic for query string
        # 0: tipo, 1: poi, 2: metratura, 3: classe, 4: progetto, 5: servizi
        poi = combo[1][0]
        metratura = combo[2][0]
        classe = combo[3][0]
        progetto = combo[4][0]
        servizi = combo[5][0]
        
        if poi:
            query += f" vicino a {poi}"
        if metratura:
            query += f" con superficie {metratura}"
        if classe:
            query += f" in classe {classe}"
        if progetto:
            query += f", finalizzato a {progetto}"
        if servizi:
            query += f" e situato vicino a {servizi}"
            
        all_compositions.append({
            "query": query,
            "var_count": var_count
        })
    
    # Sort by character length (ascending) to match file naming query_001, query_002...
    all_compositions.sort(key=lambda x: len(x["query"]))
    
    # Models to analyze
    models = [d for d in os.listdir(results_base_dir) if os.path.isdir(os.path.join(results_base_dir, d))]
    
    for model in models:
        print(f"\n--- Statistics for model: {model} ---")
        model_dir = os.path.join(results_base_dir, model)
        
        # stats[var_count] = {"total": 0, "relaxed": 0}
        stats = defaultdict(lambda: {"total": 0, "relaxed": 0})
        
        for i, comp in enumerate(all_compositions):
            query_file = os.path.join(model_dir, f"query_{i+1:03d}.json")
            if os.path.exists(query_file):
                try:
                    with open(query_file, 'r', encoding='utf-8') as f:
                        res = json.load(f)
                        var_count = comp["var_count"]
                        relaxed = res.get("relaxation_applied", False)
                        
                        stats[var_count]["total"] += 1
                        if relaxed:
                            stats[var_count]["relaxed"] += 1
                except Exception as e:
                    pass # Skip problematic files
        
        # Header
        print(f"{'Variables':<12} | {'Total':<10} | {'Relaxed':<10} | {'Relaxation %':<15}")
        print("-" * 55)
        
        sorted_counts = sorted(stats.keys())
        for count in sorted_counts:
            total = stats[count]["total"]
            relaxed = stats[count]["relaxed"]
            percentage = (relaxed / total * 100) if total > 0 else 0
            print(f"{count:<12} | {total:<10} | {relaxed:<10} | {percentage:>12.2f}%")

if __name__ == "__main__":
    base_path = "/Users/marcodeluca/Downloads/real-estate-ai/synthetic_test_suite"
    analyze_relaxation_stats(base_path)
