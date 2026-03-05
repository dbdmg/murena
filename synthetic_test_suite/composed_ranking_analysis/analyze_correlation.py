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
    parser.add_argument("--model", type=str, choices=["gpt-oss-120b", "gpt-5-nano"], default="gpt-oss-120b", help="llm model flavor")
    args = parser.parse_args()

    # Detect directories
    script_dir = Path(__file__).parent.absolute()
    results_root = script_dir.parent / "composed_results" / args.model
    
    if not results_root.exists():
        print(f"[error] results directory not found: {results_root}")
        return

    # create model-specific output directory
    output_dir = script_dir / args.model
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[config] analyzing model: {args.model}")
    analyze_weight_correlation(str(results_root), str(output_dir))

def analyze_weight_correlation(results_dir: str, output_dir: str):
    """
    analyze the distribution of original and effective weights, and the correlation 
    between agent ranking and their effectiveness.
    """
    data = []
    
    # Load all json files in the results directory
    files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
    if not files:
        print(f"No JSON files found in {results_dir}")
        return
        
    print(f"found {len(files)} result files.")
    
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
            print(f"error processing {filename}: {e}")

    if not data:
        print("No data collected. Check JSON structure or directory path.")
        return

    df = pd.DataFrame(data)
    
    print("\n--- summary statistics ---")
    print(f"total agent-query pairs: {len(df)}")
    print(f"total effective responses: {df['is_effective'].sum()} ({(df['is_effective'].mean()*100):.2f}%)")
    
    # calculate correlation
    # 1. point-biserial correlation
    pb_corr, pb_p = stats.pointbiserialr(df['is_effective'], df['original_weight'])
    
    # 2. spearman correlation: rank vs is_effective
    spearman_rank_corr, spearman_rank_p = stats.spearmanr(df['rank'], df['is_effective'])
    
    # 3. spearman correlation: weight vs is_effective
    spearman_weight_corr, spearman_weight_p = stats.spearmanr(df['original_weight'], df['is_effective'])

    print("\n--- correlation analysis ---")
    print(f"1. weight (continuous) vs effectiveness (binary):")
    print(f"   point-biserial correlation: {pb_corr:.4f} (p-value: {pb_p:.4g})")
    
    print(f"\n2. weight (continuous) vs effectiveness (binary) (spearman):")
    print(f"   spearman correlation: {spearman_weight_corr:.4f} (p-value: {spearman_weight_p:.4g})")

    print(f"\n3. agent rank (1=highest) vs effectiveness (binary):")
    print(f"   spearman correlation: {spearman_rank_corr:.4f} (p-value: {spearman_rank_p:.4g})")

    # 4. correlation between weight and actual effective weight value
    spearman_eff_val_corr, spearman_eff_val_p = stats.spearmanr(df['original_weight'], df['effective_weight'])
    pearson_eff_val_corr, pearson_eff_val_p = stats.pearsonr(df['original_weight'], df['effective_weight'])

    print(f"\n4. original weight vs effective weight (continuous):")
    print(f"   pearson correlation: {pearson_eff_val_corr:.4f} (p-value: {pearson_eff_val_p:.4g})")
    print(f"   spearman correlation: {spearman_eff_val_corr:.4f} (p-value: {spearman_eff_val_p:.4g})")

    # analysis per agent
    print("\n--- effectiveness by agent ---")
    agent_stats = df.groupby('agent')['is_effective'].agg(['count', 'sum', 'mean']).sort_values('mean', ascending=False)
    agent_stats.columns = ['total queries', 'times effective', 'effectiveness rate']
    print(agent_stats)
    
    # average weight when effective vs not
    print("\n--- average original weight by effectiveness ---")
    avg_weight = df.groupby('is_effective')['original_weight'].mean()
    print(avg_weight)

    # weight distribution statistics
    orig_dist = df['original_weight'].describe()
    eff_dist = df['effective_weight'].describe()
    
    print("\n--- weight distribution statistics ---")
    print("original weights:")
    print(orig_dist)
    print("\neffective weights:")
    print(eff_dist)
    
    zero_eff_count = int((df['effective_weight'] == 0).sum())
    print(f"\neffective weights zeros: {zero_eff_count} ({(zero_eff_count/len(df)*100):.2f}%)")
    
    non_zero_eff_df = df[df['effective_weight'] > 0]
    if not non_zero_eff_df.empty:
        print("\neffective weights (non-zero only):")
        print(non_zero_eff_df['effective_weight'].describe())

    # calculate rank effectiveness for summary and plots
    rank_effectiveness = df.groupby('rank')['is_effective'].mean()
    high_rank_eff = rank_effectiveness.iloc[0]
    # handle cases where we have fewer than 5 ranks
    low_rank_eff = rank_effectiveness.iloc[-1] if not rank_effectiveness.empty else 0.1

    # --- saving results ---
    # consolidate all results into a single dictionary
    results = {
        "summary": {
            "total_agent_query_pairs": int(len(df)),
            "total_effective_responses": int(df['is_effective'].sum()),
            "effectiveness_rate_percent": float(df['is_effective'].mean() * 100)
        },
        "weight_distribution": {
            "original_weights": {k: float(v) for k, v in orig_dist.items()},
            "effective_weights": {k: float(v) for k, v in eff_dist.items()},
            "effective_weights_zero_count": zero_eff_count,
            "effective_weights_zero_percent": float(zero_eff_count / len(df) * 100),
            "non_zero_effective_weights": {k: float(v) for k, v in non_zero_eff_df['effective_weight'].describe().items()} if not non_zero_eff_df.empty else {}
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
            "total queries": "total_queries",
            "times effective": "times_effective",
            "effectiveness rate": "effectiveness_rate"
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

    # save json
    json_path = os.path.join(output_dir, "ranking_correlation_analysis.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=4)
    
    print(f"\n[info] analysis results saved to {json_path}")
    print("[info] csv, text, and plot generation has been disabled as requested.")


if __name__ == "__main__":
    main()
