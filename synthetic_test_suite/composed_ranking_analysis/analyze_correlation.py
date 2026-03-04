import os
import json
import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Any

def main():
    import argparse
    from pathlib import Path
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=["gpt-oss-120b", "gpt-5-nano"], default="gpt-oss-120b", help="LLM model flavor")
    args = parser.parse_args()

    # Detect directories
    script_dir = Path(__file__).parent.absolute()
    results_root = script_dir.parent / "composed_results" / args.model
    
    if not results_root.exists():
        print(f"[ERROR] Results directory not found: {results_root}")
        return

    # Create model-specific output directory
    output_dir = script_dir / args.model
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[CONFIG] Analyzing model: {args.model}")
    analyze_weight_correlation(str(results_root), str(output_dir))

def analyze_weight_correlation(results_dir: str, output_dir: str):
    """
    Analyze the correlation between agent ranking (original_weights) and 
    their effectiveness (effective_weights > 0).
    """
    data = []
    
    # Load all json files in the results directory
    files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
    if not files:
        print(f"No JSON files found in {results_dir}")
        return
        
    print(f"Found {len(files)} result files.")
    
    for filename in files:
        filepath = os.path.join(results_dir, filename)
        try:
            with open(filepath, 'r') as f:
                res = json.load(f)
            
            ranking_logic = res.get('ranking_logic', {})
            original_weights = ranking_logic.get('original_weights', {})
            effective_weights = ranking_logic.get('effective_weights', {})
            
            if not original_weights or not effective_weights:
                continue
                
            # Sort agents by original weight to get their rank
            sorted_agents = sorted(original_weights.items(), key=lambda x: x[1], reverse=True)
            
            # Rank 1 is the highest weight
            agent_ranks = {agent: i + 1 for i, (agent, _) in enumerate(sorted_agents)}
            
            for agent, weight in original_weights.items():
                eff_weight = effective_weights.get(agent, 0.0)
                is_effective = 1 if eff_weight > 0 else 0
                rank = agent_ranks.get(agent)
                
                data.append({
                    'query': filename,
                    'agent': agent,
                    'original_weight': weight,
                    'rank': rank,
                    'is_effective': is_effective,
                    'effective_weight': eff_weight
                })
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    if not data:
        print("No data collected. Check JSON structure or directory path.")
        return

    df = pd.DataFrame(data)
    
    print("\n--- Summary Statistics ---")
    print(f"Total agent-query pairs: {len(df)}")
    print(f"Total effective responses: {df['is_effective'].sum()} ({(df['is_effective'].mean()*100):.2f}%)")
    
    # Calculate Correlation
    # 1. Point-biserial correlation
    pb_corr, pb_p = stats.pointbiserialr(df['is_effective'], df['original_weight'])
    
    # 2. Spearman correlation: Rank vs Is_Effective
    spearman_rank_corr, spearman_rank_p = stats.spearmanr(df['rank'], df['is_effective'])
    
    # 3. Spearman correlation: Weight vs Is_Effective
    spearman_weight_corr, spearman_weight_p = stats.spearmanr(df['original_weight'], df['is_effective'])

    print("\n--- Correlation Analysis ---")
    print(f"1. Weight (continuous) vs Effectiveness (binary):")
    print(f"   Point-biserial Correlation: {pb_corr:.4f} (p-value: {pb_p:.4g})")
    
    print(f"\n2. Weight (continuous) vs Effectiveness (binary):")
    print(f"   Spearman Correlation: {spearman_weight_corr:.4f} (p-value: {spearman_weight_p:.4g})")

    print(f"\n3. Agent Rank (1=highest) vs Effectiveness (binary):")
    print(f"   Spearman Correlation: {spearman_rank_corr:.4f} (p-value: {spearman_rank_p:.4g})")

    # 4. Correlation between weight and actual effective weight value
    spearman_eff_val_corr, spearman_eff_val_p = stats.spearmanr(df['original_weight'], df['effective_weight'])
    pearson_eff_val_corr, pearson_eff_val_p = stats.pearsonr(df['original_weight'], df['effective_weight'])

    print(f"\n4. Original Weight vs Effective Weight (continuous):")
    print(f"   Pearson Correlation: {pearson_eff_val_corr:.4f} (p-value: {pearson_eff_val_p:.4g})")
    print(f"   Spearman Correlation: {spearman_eff_val_corr:.4f} (p-value: {spearman_eff_val_p:.4g})")

    # Analysis per agent
    print("\n--- Effectiveness by Agent ---")
    agent_stats = df.groupby('agent')['is_effective'].agg(['count', 'sum', 'mean']).sort_values('mean', ascending=False)
    agent_stats.columns = ['Total Queries', 'Times Effective', 'Effectiveness Rate']
    print(agent_stats)
    
    # Average weight when effective vs not
    print("\n--- Average Original Weight by Effectiveness ---")
    avg_weight = df.groupby('is_effective')['original_weight'].mean()
    print(avg_weight)

    # Calculate Rank Effectiveness for summary and plots
    rank_effectiveness = df.groupby('rank')['is_effective'].mean()
    high_rank_eff = rank_effectiveness.iloc[0]
    # Handle cases where we have fewer than 5 ranks
    low_rank_eff = rank_effectiveness.iloc[-1] if not rank_effectiveness.empty else 0.1

    # --- Saving Results ---
    # Consolidate all results into a single dictionary
    results = {
        "summary": {
            "total_agent_query_pairs": int(len(df)),
            "total_effective_responses": int(df['is_effective'].sum()),
            "effectiveness_rate_percent": float(df['is_effective'].mean() * 100)
        },
        "correlation_analysis": {
            "point_biserial_weight_vs_effectiveness": {
                "correlation": float(pb_corr),
                "p_value": float(pb_p)
            },
            "spearman_weight_vs_effectiveness": {
                "correlation": float(spearman_weight_corr),
                "p_value": float(spearman_weight_p)
            },
            "spearman_rank_vs_effectiveness": {
                "correlation": float(spearman_rank_corr),
                "p_value": float(spearman_rank_p)
            },
            "original_vs_effective_weight": {
                "pearson": {
                    "correlation": float(pearson_eff_val_corr),
                    "p_value": float(pearson_eff_val_p)
                },
                "spearman": {
                    "correlation": float(spearman_eff_val_corr),
                    "p_value": float(spearman_eff_val_p)
                }
            }
        },
        "effectiveness_by_agent": agent_stats.reset_index().rename(columns={
            "index": "agent",
            "count": "total_queries",
            "sum": "times_effective",
            "mean": "effectiveness_rate"
        }).to_dict(orient='records'),
        "average_weight_by_effectiveness": {
            "not_effective": float(avg_weight.get(0, 0)),
            "effective": float(avg_weight.get(1, 0))
        },
        "effectiveness_by_rank": {str(k): float(v) for k, v in rank_effectiveness.items()},
        "key_findings": {
            "rank_1_vs_lowest_multiplier": float(high_rank_eff / low_rank_eff) if low_rank_eff > 0 else None
        }
    }

    # Save JSON
    json_path = os.path.join(output_dir, "ranking_correlation_analysis.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=4)
    
    print(f"\n[INFO] Analysis results saved to {json_path}")
    print("[INFO] CSV, text, and plot generation has been disabled as requested.")


if __name__ == "__main__":
    main()
