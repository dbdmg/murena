from typing import Dict, Any, List
from pathlib import Path

def generate_report(benchmark_results: Dict[str, Any], sensitivity_results: Dict[str, Any], models: List[str]) -> str:
    """Generates a comprehensive Markdown report of all experimental results."""
    report_md = "# Experimental Evaluation Report: Real Estate AI Agentic Framework\n\n"
    report_md += "This report summarizes the performance, robustness, and architectural fidelity of the multi-agent framework.\n\n"
    
    for mod in models:
        if mod not in benchmark_results: continue
        
        report_md += f"## Model: {mod}\n\n"
        
        # 1. Architectural Fidelity
        report_md += "### 1. Architectural Fidelity (Agent Activation)\n"
        act = benchmark_results[mod].get("activation", {})
        report_md += f"| Metric | Value |\n| :--- | :---: |\n"
        report_md += f"| Mean Activation Precision | {act.get('mean_precision', 0):.3f} |\n"
        report_md += f"| Mean Activation Recall | {act.get('mean_recall', 0):.3f} |\n"
        report_md += f"| Mean Activation F1 | {act.get('mean_f1', 0):.3f} |\n\n"
        
        # 2. Ranking Stability (IoU)
        report_md += "### 2. Ranking Stability & Consistency\n"
        iou = benchmark_results[mod].get("iou", {})
        cons = benchmark_results[mod].get("consistency", {})
        report_md += f"| Metric | Value |\n| :--- | :---: |\n"
        report_md += f"| Intra-Model IoU (across trials) | {iou.get('mean_iou', 0):.3f} |\n"
        report_md += f"| Self-Consistency Rate | {cons.get('consistency_rate', 0):.1%} |\n\n"
        
        # 3. Ablation & Sensitivity
        report_md += "### 3. Component Sensitivity (IoU against All-Enabled)\n"
        sens = sensitivity_results.get(mod, {}).get("sensitivity", {})
        report_md += "| Component Disabled | Impact (IoU) |\n| :--- | :---: |\n"
        for comp, val in sens.items():
            report_md += f"| {comp.replace('_', ' ').title()} | {val:.3f} |\n"
        report_md += "\n"
        
        # 4. Performance
        report_md += "### 4. Performance Analysis\n"
        perf = benchmark_results[mod].get("performance", {})
        report_md += f"| Metric | Value |\n| :--- | :---: |\n"
        report_md += f"| Average Latency | {perf.get('mean_ms', 0)/1000:.2f}s |\n"
        report_md += f"| Sample Size | {perf.get('sample_size', 0)} |\n\n"
        
        report_md += "---\n\n"
        
    return report_md
