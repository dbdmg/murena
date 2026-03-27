import pandas as pd
import os
import subprocess
import sys
import json
from pathlib import Path

# Setup paths relative to script location for portability
suite_path = Path(__file__).resolve().parent
results_path = suite_path / "results_sampled"
results_path.mkdir(parents=True, exist_ok=True)

# Combinatorial queries (incremental complexity)
combinatorial_queries = [
    "Cerca un abitazione",
    "Cerca un abitazione vicino a Palazzo Nuovo",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a co-housing",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a co-housing e situato vicino a palestre e centri sportivi",
    "Cerca un immobile vicino a Porta Susa con superficie tra 50 e 80 mq in classe F o G, finalizzato a co-housing e situato vicino a mezzi di trasporto",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a centro per anziani e situato vicino a mezzi di trasporto"
]

# Sensitivity queries (all configurations to be tested for ablation)
sensitivity_queries = [
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a co-housing e situato vicino a palestre e centri sportivi",
    "Cerca un immobile vicino a Porta Susa con superficie tra 50 e 80 mq in classe F o G, finalizzato a co-housing e situato vicino a mezzi di trasporto",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a centro per anziani e situato vicino a mezzi di trasporto"
]

# Load variable possibilities for ID generation
pos_json = suite_path / "query_variables_possibilities.json"
with open(pos_json) as f: 
    vars_data = json.load(f)

def get_query_id(query):
    # Order: tipologia_immobile, punto_di_interesse, metratura_totale, classe_energetica, progetto_destinazione_uso, servizi_accessori
    keys = ["tipologia_immobile", "punto_di_interesse", "metratura_totale", "classe_energetica", "progetto_destinazione_uso", "servizi_accessori"]
    indices = []
    
    # tipologia_immobile (Mandatory in query string usually)
    t_found = 0
    for i, val in enumerate(vars_data["tipologia_immobile"], 1):
        if val in query:
            t_found = i
            break
    indices.append(str(t_found))
    
    # Other optional variables
    for k in keys[1:]:
        found = 0
        for i, val in enumerate(vars_data[k], 1):
            if val in query:
                found = i
                break
        indices.append(str(found))
    
    return "".join(indices)

print(f"[*] Prepared {len(combinatorial_queries)} combinatorial queries and {len(sensitivity_queries)} sensitivity queries.")

# Create combinatorial CSV
rows_bench = [{"query_id": get_query_id(q), "query": q, "status": 0} for q in combinatorial_queries]
df_bench = pd.DataFrame(rows_bench)
df_bench.to_csv(results_path / "combinatorial_queries_suite.csv", index=False)

# Create sensitivity CSV (all queries x all ablation variables)
sens_cols = [
    'query_id', 'query', 'status_all_enabled', 'status_no_ranking', 'status_no_knowledge',
    'status_baseline_columns', 'status_baseline_stats',
    'status_no_poi', 'status_no_normative', 'status_no_location',
    'status_no_ape', 'status_no_property_technical'
]
rows_sens = []
for q in sensitivity_queries:
    row = {"query_id": get_query_id(q), "query": q}
    for col in sens_cols[2:]:
        row[col] = 0
    rows_sens.append(row)

df_sens = pd.DataFrame(rows_sens)
df_sens = df_sens[sens_cols] # Ensure column order
df_sens.to_csv(results_path / "sensitivity_queries_suite.csv", index=False)

# Set environment variable for custom results directory
env = os.environ.copy()
env["EXPERIMENT_RESULTS_DIR"] = str(results_path)
# Ensure backend and site-packages are in PYTHONPATH
backend_dir = suite_path.parent / "backend"
if "PYTHONPATH" in env:
    env["PYTHONPATH"] = f"{backend_dir}:{suite_path}:{env['PYTHONPATH']}"
else:
    env["PYTHONPATH"] = f"{backend_dir}:{suite_path}"

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--only-analysis", action="store_true")
args = parser.parse_args()

# Run the full conductor
print(f"\n[*] Launching 'experiments.py' on sampled queries...")
print(f"[*] Results will be saved in: {results_path}")
print("-" * 50)

try:
    cmd = [sys.executable, str(suite_path / "experiments.py"), "--max-concurrent", "10"]
    if args.only_analysis:
        cmd.append("--only-analysis")
        
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    process.wait()
except KeyboardInterrupt:
    print("\n[!] Experiment interrupted by user.")
    process.terminate()
except Exception as e:
    print(f"\n[!] Unexpected error: {e}")

if process.returncode == 0:
    print("\n" + "="*50)
    print("EXPERIMENT COMPLETE")
    print(f"Final Report: {results_path / 'report.md'}")
else:
    print(f"\n[!] Experiment finished with return code: {process.returncode}")
