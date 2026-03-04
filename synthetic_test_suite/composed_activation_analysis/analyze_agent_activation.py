import json
import argparse
from pathlib import Path
from typing import Dict, List, Set, Any

def load_mapping(mapping_path: Path) -> Dict[str, str]:
    """
    Loads the keyword-to-agent mapping from a JSON file.
    
    Args:
        mapping_path: The path to the JSON mapping file.
        
    Returns:
        A dictionary mapping keywords to agent names.
    """
    with open(mapping_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_query(query: str, mapping: Dict[str, str]) -> Set[str]:
    """
    Identifies which agents are expected to be activated based on query keywords.
    
    Args:
        query: The user query string.
        mapping: The keyword-to-agent mapping dictionary.
        
    Returns:
        A set of expected agent names.
    """
    expected_agents = set()
    query_lower = query.lower()
    for keyword, agent in mapping.items():
        if keyword.lower() in query_lower:
            expected_agents.add(agent)
    return expected_agents

def main():
    """
    Main execution logic for analyzing agent activation discrepancies.
    Reads results from a model directory and compares actual activation against a template.
    """
    parser = argparse.ArgumentParser(description="Analyze agent activation discrepancies based on query keywords.")
    parser.add_argument("--model", type=str, choices=["gpt-oss-120b", "gpt-5-nano"], default="gpt-oss-120b", help="LLM model flavor.")
    args = parser.parse_args()

    script_dir = Path(__file__).parent.absolute()
    # Now script is inside 'composed_activation_analysis'
    base_dir = script_dir.parent
    mapping_path = script_dir / "agent_mapping.json"
    results_dir = base_dir / "composed_results" / args.model
    output_dir = script_dir / args.model
    output_dir.mkdir(parents=True, exist_ok=True)

    if not mapping_path.exists():
        print(f"Mapping file not found: {mapping_path}")
        return

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return

    mapping = load_mapping(mapping_path)
    
    json_files = sorted(list(results_dir.glob("*.json")))
    print(f"Analyzing {len(json_files)} results for model: {args.model}")

    discrepancies: List[Dict[str, Any]] = []
    total_processed = 0
    
    # Per-agent metrics initialization
    unique_agents = sorted(list(set(mapping.values())))
    agent_metrics = {agent: {"tp": 0, "fp": 0, "fn": 0} for agent in unique_agents}
    
    # Per-query metrics accumulation
    total_jaccard = 0.0
    perfect_matches = 0

    for f in json_files:
        try:
            with open(f, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                query_text = data.get("query", "")
                ranking_logic = data.get("ranking_logic", {})
                eff_weights = ranking_logic.get("effective_weights", {})

                expected = analyze_query(query_text, mapping)
                # Actual agents are those that provided requirements (effective_weight > 0)
                actual = {agent for agent, weight in eff_weights.items() if weight > 0}

                # Calculate per-agent TP, FP, FN
                for agent in unique_agents:
                    is_expected = agent in expected
                    is_actual = agent in actual
                    
                    if is_expected and is_actual:
                        agent_metrics[agent]["tp"] += 1
                    elif not is_expected and is_actual:
                        agent_metrics[agent]["fp"] += 1
                    elif is_expected and not is_actual:
                        agent_metrics[agent]["fn"] += 1

                # Per-query metrics
                if actual == expected:
                    perfect_matches += 1
                
                intersection = expected.intersection(actual)
                union = expected.union(actual)
                jaccard = len(intersection) / len(union) if union else 1.0
                total_jaccard += jaccard

                if actual != expected:
                    extra = list(actual - expected)
                    missing = list(expected - actual)
                    discrepancies.append({
                        "file": f.name,
                        "query": query_text,
                        "expected": sorted(list(expected)),
                        "actual": sorted(list(actual)),
                        "extra": sorted(extra),
                        "missing": sorted(missing),
                        "jaccard": round(jaccard, 3)
                    })
                
                total_processed += 1
        except Exception as e:
            print(f"Failed to process {f.name}: {e}")

    # Calculate final agent metrics
    summary_per_agent = {}
    for agent, counts in agent_metrics.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        summary_per_agent[agent] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1, 3),
            "tp": tp,
            "fp": fp,
            "fn": fn
        }

    # Summary metrics
    global_metrics = {
        "model": args.model,
        "total_queries": total_processed,
        "perfect_match_rate": round(perfect_matches / total_processed, 3) if total_processed > 0 else 0.0,
        "mean_jaccard_index": round(total_jaccard / total_processed, 3) if total_processed > 0 else 0.0,
        "mismatch_count": len(discrepancies)
    }

    # Save metrics and discrepancies to a file
    output_file = output_dir / "activation_analysis_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": global_metrics,
            "agent_metrics": summary_per_agent,
            "discrepancies": discrepancies
        }, f, indent=4, ensure_ascii=False)

    # Print summary to console
    print("\n" + "="*80)
    print(f"ACTIVATION METRICS SUMMARY - Model: {args.model}")
    print("="*80)
    print(f"Total queries:         {total_processed}")
    print(f"Perfect Match Rate:    {global_metrics['perfect_match_rate']:.1%}")
    print(f"Mean Jaccard Index:    {global_metrics['mean_jaccard_index']:.3f}")
    print(f"Total Mismatches:      {len(discrepancies)}")
    
    print("\nPer-Agent Synthesis (F1-Score):")
    for agent, metrics in summary_per_agent.items():
        print(f"  - {agent:20}: {metrics['f1_score']:.3f} (P: {metrics['precision']:.2f}, R: {metrics['recall']:.2f})")
    
    print("\n" + "="*80)
    print(f"Detailed report saved to: {output_file}")
    print("="*80)

if __name__ == "__main__":
    main()
