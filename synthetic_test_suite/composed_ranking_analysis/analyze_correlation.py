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
    # 1. Save CSV
    csv_path = os.path.join(output_dir, "agent_effectiveness_data.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[INFO] Data saved to {csv_path}")

    # 2. Save Summary Stats
    summary_path = os.path.join(output_dir, "ranking_effectiveness_summary.txt")
    with open(summary_path, "w") as f:
        f.write("--- RANKING VS EFFECTIVENESS ANALYSIS ---\n")
        f.write(f"Spearman Correlation (Rank vs Is_Effective): {spearman_rank_corr:.4f}\n")
        f.write(f"p-value: {spearman_rank_p:.4g}\n")
        f.write("(Note: Negative correlation means higher rank [smaller number 1, 2...] correlates with being effective)\n\n")
        
        f.write("--- Effectiveness Probability by Rank Position ---\n")
        for rank, prob in rank_effectiveness.items():
            f.write(f"Rank {rank}: {prob:.2%} probability of contributing requirements\n")
            
        if low_rank_eff > 0:
            f.write(f"\n[KEY FINDING] An agent in Rank 1 is {high_rank_eff/low_rank_eff:.1f}x more likely to contribute than an agent in the lowest Rank.\n")
        
        f.write("\n--- Effectiveness per Agent (Baseline) ---\n")
        f.write(agent_stats.to_string())
    print(f"[INFO] Summary saved to {summary_path}")

    # --- Plotting ---
    try:
        import matplotlib.pyplot as plt
        
        # Set a clean style
        plt.rcParams.update({'font.size': 10, 'figure.figsize': (10, 6)})
        
        # Plot 1: Effectiveness Rate per Agent
        plt.figure()
        agent_stats['Effectiveness Rate'].plot(kind='bar', color='skyblue', alpha=0.8)
        plt.title('Effectiveness Rate by Agent')
        plt.ylabel('Rate (0-1)')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "effectiveness_per_agent.png"))
        
        # Plot 2: Original Weight Distribution by Effectiveness
        plt.figure()
        data_to_plot = [df[df['is_effective'] == 0]['original_weight'], 
                        df[df['is_effective'] == 1]['original_weight']]
        plt.boxplot(data_to_plot, labels=['Not Effective', 'Effective'])
        plt.title('Original Weight Distribution by Effectiveness')
        plt.ylabel('Original Weight')
        plt.grid(axis='y', linestyle='--', alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "weight_distribution_by_effectiveness.png"))
        
        # Plot 3: Scatter Plot Original vs Effective Weight
        plt.figure()
        plt.scatter(df['original_weight'], df['effective_weight'], alpha=0.3, color='forestgreen')
        plt.title('Original Weight vs Effective Weight')
        plt.xlabel('Original Weight')
        plt.ylabel('Effective Weight')
        plt.grid(True, linestyle='--', alpha=0.5)
        max_val = max(df['original_weight'].max(), df['effective_weight'].max())
        plt.plot([0, max_val], [0, max_val], 'r--', alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "original_vs_effective_weight.png"))
        
        # Plot 4: Effectiveness by Rank
        plt.figure()
        rank_effectiveness.plot(kind='bar', color='salmon', alpha=0.8)
        plt.title('Effectiveness Rate by Agent Rank')
        plt.xlabel('Agent Rank (1 = Highest Weight)')
        plt.ylabel('Effectiveness Rate (0-1)')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "effectiveness_by_rank.png"))
        
        print(f"[INFO] Plots saved to {output_dir}")
        print("\n--- Effectiveness by Rank ---")
        print(rank_effectiveness)
    except Exception as e:
        print(f"[ERROR] Plotting failed: {e}")

if __name__ == "__main__":
    main()
