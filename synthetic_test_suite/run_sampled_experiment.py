import pandas as pd
import os
import subprocess
import sys
import json
from pathlib import Path

# Setup paths
suite_path = Path("/home/mdeluca/real-estate-ai/synthetic_test_suite")
results_path = suite_path / "results_sampled"
results_path.mkdir(parents=True, exist_ok=True)

# Define the 6 incremental queries
# We use Palazzo Nuovo and typical residential variables
queries = [
    "Cerca un abitazione",
    "Cerca un abitazione vicino a Palazzo Nuovo",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a co-housing",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a co-housing e situato vicino a palestre e centri sportivi",
    "Cerca un immobile vicino a Porta Susa con superficie tra 50 e 80 mq in classe F o G, finalizzato a co-housing e situato vicino a mezzi di trasporto",
    "Cerca un abitazione vicino a Palazzo Nuovo con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a centro per anziani e situato vicino a mezzi di trasporto"
]

print(f"[*] Prepared 6 incremental queries:")
for i, q in enumerate(queries, 1):
    print(f"  {i}. {q}")

# Create combinatorial CSV
df_bench = pd.DataFrame({"query": queries, "status": [0]*len(queries)})
df_bench.to_csv(results_path / "combinatorial_queries_suite.csv", index=False)

# Create sensitivity CSV (all queries x all ablation variables)
sens_cols = [
    'query', 'status_all_enabled', 'status_no_ranking', 'status_no_knowledge',
    'status_no_poi', 'status_no_normative', 'status_no_location',
    'status_no_ape', 'status_no_property_technical'
]
df_sens = pd.DataFrame({"query": queries})
for col in sens_cols[1:]:
    df_sens[col] = 0
df_sens.to_csv(results_path / "sensitivity_queries_suite.csv", index=False)

# Set environment variable for custom results directory
env = os.environ.copy()
env["EXPERIMENT_RESULTS_DIR"] = str(results_path)
# Ensure backend and site-packages are in PYTHONPATH
backend_dir = "/home/mdeluca/real-estate-ai/backend"
if "PYTHONPATH" in env:
    env["PYTHONPATH"] = f"{backend_dir}:{suite_path}:{env['PYTHONPATH']}"
else:
    env["PYTHONPATH"] = f"{backend_dir}:{suite_path}"

# Run the full conductor
print(f"\n[*] Launching 'experiments.py' on sampled queries...")
print(f"[*] Results will be saved in: {results_path}")
print("-" * 50)

try:
    # Use --max-concurrent 4 to avoid hitting rate limits too hard since we have multiple models in parallel
    process = subprocess.Popen(
        [sys.executable, str(suite_path / "experiments.py"), "--max-concurrent", "10"],
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
