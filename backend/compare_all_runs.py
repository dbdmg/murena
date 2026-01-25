"""
Compare THREE runs to check consistency with temperature=0.1
"""
import json
import glob
import os

# Find the 3 most recent JSON files
json_files = sorted(glob.glob("run_exports/*.json"), key=os.path.getmtime, reverse=True)[:3]

if len(json_files) < 3:
    print("❌ Need at least 3 runs to compare!")
    exit(1)

print("="*80)
print("THREE-WAY RUN CONSISTENCY ANALYSIS")
print("="*80)
print(f"\nComparing:")
for i, f in enumerate(json_files):
    print(f"  Run {i+1}: {os.path.basename(f)}")

# Load all three
runs = []
for f in json_files:
    with open(f, "r", encoding="utf-8") as file:
        runs.append(json.load(file))

# Compare SQL queries
print(f"\n🔍 SQL CONSISTENCY:")
sqls = [r['agent_outputs']['sql_generation']['sql_query'] for r in runs]

all_identical = sqls[0] == sqls[1] == sqls[2]
if all_identical:
    print("  ✅ ALL THREE SQL queries are IDENTICAL")
else:
    print("  ❌ SQL queries DIFFER across runs")
    print(f"\n  Run 1 == Run 2: {sqls[0] == sqls[1]}")
    print(f"  Run 1 == Run 3: {sqls[0] == sqls[2]}")
    print(f"  Run 2 == Run 3: {sqls[1] == sqls[2]}")
    
    # Show key differences
    print("\n  Key filter presence:")
    filters_to_check = [
        ('superficie_di_riferimento_mq BETWEEN', 'Superficie filter'),
        ('tipologia_bene_immobile IN', 'Tipologia filter'),
        ('haversine_km', 'Distance filter'),
    ]
    
    for pattern, label in filters_to_check:
        presence = [pattern in sql for sql in sqls]
        all_same = all(presence) or not any(presence)
        status = "✅" if all_same else "⚠️"
        print(f"    {status} {label:<25} R1:{presence[0]}  R2:{presence[1]}  R3:{presence[2]}")

# Compare TOP 10 overlaps
print(f"\n🏆 TOP 10 CONSISTENCY:")

top10_ids = []
for r in runs:
    buildings = r['full_results']['buildings'][:10]
    ids = [b['id'] for b in buildings]
    top10_ids.append(set(ids))

# Pairwise overlaps
overlap_12 = len(top10_ids[0] & top10_ids[1])
overlap_13 = len(top10_ids[0] & top10_ids[2])
overlap_23 = len(top10_ids[1] & top10_ids[2])

# All three
overlap_all = len(top10_ids[0] & top10_ids[1] & top10_ids[2])

print(f"\n  Pairwise overlaps:")
print(f"    Run 1 ∩ Run 2: {overlap_12}/10 ({overlap_12*10}%)")
print(f"    Run 1 ∩ Run 3: {overlap_13}/10 ({overlap_13*10}%)")
print(f"    Run 2 ∩ Run 3: {overlap_23}/10 ({overlap_23*10}%)")
print(f"\n  All three: {overlap_all}/10 ({overlap_all*10}%) common IDs")

# Show top 10 side by side
print(f"\n  TOP 10 SIDE-BY-SIDE:")
print(f"\n  {'Rank':<6} {'Run 1 ID':<15} {'Run 2 ID':<15} {'Run 3 ID':<15} {'All Same'}")
print("  " + "-"*70)

for i in range(10):
    id1 = runs[0]['full_results']['buildings'][i]['id']
    id2 = runs[1]['full_results']['buildings'][i]['id']
    id3 = runs[2]['full_results']['buildings'][i]['id']
    
    all_same = "✅" if id1 == id2 == id3 else ""
    
    print(f"  {i+1:<6} {id1:<15} {id2:<15} {id3:<15} {all_same}")

# Check metrics variance
print(f"\n📊 METRICS VARIANCE:")
metrics = ['total_buildings', 'ape_data_available', 'ape_percentage', 'low_energy_class_count']

for metric in metrics:
    values = [r['metrics'][metric] for r in runs]
    all_same = values[0] == values[1] == values[2]
    status = "✅" if all_same else "⚠️"
    print(f"  {status} {metric:<30} R1:{values[0]:<10} R2:{values[1]:<10} R3:{values[2]:<10}")

# Small surface check
print(f"\n📏 SMALL SURFACES IN TOP 10:")
for i, r in enumerate(runs):
    buildings = r['full_results']['buildings'][:10]
    small = [b for b in buildings if b.get('superficie_di_riferimento_mq', 999) < 25]
    print(f"  Run {i+1}: {len(small)}/10 under 25m²")
    
print(f"\n{'='*80}")
print("CONCLUSION:")
print(f"{'='*80}")

if overlap_all >= 7:
    print("✅ GOOD: 70%+ consistency in top 10 across all runs")
elif overlap_all >= 5:
    print("⚠️ MODERATE: 50-70% consistency - some variance expected")
else:
    print("❌ POOR: <50% consistency - temperature may need adjustment")

print(f"\n{'='*80}\n")
