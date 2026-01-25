"""
Quick comparison of two run exports - focus on top 10 and consistency
"""
import json

run1_path = "run_exports/20260125_205513_run_1769.json"
run2_path = "run_exports/20260125_205658_run_1769.json"

print("="*80)
print("RUN CONSISTENCY COMPARISON")
print("="*80)

# Load both runs
with open(run1_path, "r", encoding="utf-8") as f:
    run1 = json.load(f)

with open(run2_path, "r", encoding="utf-8") as f:
    run2 = json.load(f)

print(f"\n📊 METRICS COMPARISON:")
print(f"\n{'Metric':<35} {'Run 1':<20} {'Run 2':<20} {'Match'}")
print("-"*85)

m1 = run1['metrics']
m2 = run2['metrics']

metrics_to_compare = [
    ('total_buildings', 'Total buildings'),
    ('ape_data_available', 'APE data available'),
    ('ape_percentage', 'APE %'),
    ('low_energy_class_count', 'Low energy (F/G)'),
]

for key, label in metrics_to_compare:
    v1 = m1[key]
    v2 = m2[key]
    match = "✅" if v1 == v2 else "❌"
    print(f"{label:<35} {str(v1):<20} {str(v2):<20} {match}")

# Compare SQL queries
sql1 = run1['agent_outputs']['sql_generation']['sql_query']
sql2 = run2['agent_outputs']['sql_generation']['sql_query']

print(f"\n🔍 SQL CONSISTENCY:")
if sql1 == sql2:
    print("  ✅ SQL queries are IDENTICAL")
else:
    print("  ⚠️ SQL queries are DIFFERENT")
    
    # Check for key filters
    filters_to_check = [
        ('BETWEEN', 'superficie filter'),
        ('tipologia_bene_immobile IN', 'tipologia filter'),
        ('haversine_km', 'distance filter'),
    ]
    
    print("\n  Filter presence:")
    for pattern, label in filters_to_check:
        in1 = pattern in sql1
        in2 = pattern in sql2
        match = "✅" if in1 == in2 else "❌"
        print(f"    {label:<25} Run1:{in1}  Run2:{in2}  {match}")

# Compare TOP 10 results
print(f"\n🏆 TOP 10 COMPARISON:")

buildings1 = run1['full_results']['buildings'][:10]
buildings2 = run2['full_results']['buildings'][:10]

# Compare IDs
ids1 = [b['id'] for b in buildings1]
ids2 = [b['id'] for b in buildings2]

common_ids = set(ids1) & set(ids2)
overlap_pct = len(common_ids) / 10 * 100

print(f"\n  ID Overlap: {len(common_ids)}/10 ({overlap_pct:.0f}%)")
print(f"  Common IDs: {sorted(common_ids)}")

# Show top 10 details
print(f"\n  TOP 10 DETAILS:")
print(f"\n  {'Rank':<6} {'Run 1 ID':<15} {'Surface':<10} {'Classe':<8} | {'Run 2 ID':<15} {'Surface':<10} {'Classe':<8}")
print("  " + "-"*80)

for i in range(10):
    b1 = buildings1[i]
    b2 = buildings2[i]
    
    surf1 = f"{b1.get('superficie_di_riferimento_mq', 'N/A')}"
    surf2 = f"{b2.get('superficie_di_riferimento_mq', 'N/A')}"
    
    classe1 = b1.get('classe_energetica_ape', 'N/A') or 'N/A'
    classe2 = b2.get('classe_energetica_ape', 'N/A') or 'N/A'
    
    match = "✅" if b1['id'] == b2['id'] else ""
    
    print(f"  {i+1:<6} {b1['id']:<15} {surf1:<10} {classe1:<8} | {b2['id']:<15} {surf2:<10} {classe2:<8} {match}")

# Check for small surfaces in top 10
print(f"\n📏 SMALL SURFACE CHECK (< 25m²):")
small1 = [b for b in buildings1 if b.get('superficie_di_riferimento_mq', 999) < 25]
small2 = [b for b in buildings2 if b.get('superficie_di_riferimento_mq', 999) < 25]

print(f"  Run 1: {len(small1)}/10 under 25m²")
print(f"  Run 2: {len(small2)}/10 under 25m²")

if small1 or small2:
    print(f"\n  ⚠️ WARNING: Small surfaces found in top 10!")
    for b in small1 + small2:
        print(f"    - ID {b['id']}: {b.get('superficie_di_riferimento_mq')}m²")
else:
    print(f"  ✅ No small surfaces in top 10")

print(f"\n{'='*80}")
print("ANALYSIS COMPLETE")
print(f"{'='*80}\n")
