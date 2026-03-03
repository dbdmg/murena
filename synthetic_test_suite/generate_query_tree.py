import json
import os
import pandas as pd
from rich.tree import Tree
from rich.console import Console
from rich.style import Style

def generate_tree():
    base_path = "/Users/marcodeluca/Downloads/real-estate-ai/synthetic_test_suite"
    possibilities_path = os.path.join(base_path, "query_variables_possibilities.json")
    results_dir = os.path.join(base_path, "composed_results/gpt-5-nano")
    
    with open(possibilities_path, 'r') as f:
        possibilities = json.load(f)
    
    # Define order of variables for tree levels
    # User said tipologia_immobile is NOT optional.
    variables_order = [
        "tipologia_immobile",
        "punto_di_interesse",
        "metratura_totale",
        "progetto_destinazione_uso",
        "classe_energetica",
        "servizi_accessori"
    ]
    
    # Load all results
    results_data = []
    for i in range(1, 487):
        filename = f"query_{i:03d}.json"
        filepath = os.path.join(results_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                
                # Identify variables
                query_text = data['query']
                choices = {}
                for var in variables_order:
                    choices[var] = "None"
                    for val in possibilities[var]:
                        if val.lower() in query_text.lower():
                            choices[var] = val
                            break
                
                results_data.append({
                    "id": i,
                    "choices": choices,
                    "count": data.get('results_count', 0),
                    "relaxation": data.get('relaxation_applied', False)
                })

    # Group into tree
    def build_nested_dict(items, vars_list):
        if not vars_list:
            return items[0] # Leaf data
        
        current_var = vars_list[0]
        remaining_vars = vars_list[1:]
        
        grouped = {}
        # Get all possible values for this variable (include "None")
        possible_vals = possibilities[current_var] + (["None"] if current_var != "tipologia_immobile" else [])
        
        for val in possible_vals:
            subset = [item for item in items if item['choices'][current_var] == val]
            if subset:
                grouped[val] = build_nested_dict(subset, remaining_vars)
        
        return grouped

    tree_dict = build_nested_dict(results_data, variables_order)

    # Use Rich to display
    console = Console(width=200)
    root = Tree("[bold blue]Query Composition Tree[/bold blue]")

    def add_to_rich_tree(rich_node, current_dict, level):
        if level >= len(variables_order):
            # It's leaf data
            count = current_dict['count']
            relax = current_dict['relaxation']
            color = "red" if relax else "green"
            relax_str = "[bold red]RELAXED[/bold red]" if relax else "[dim green]no-relax[/dim green]"
            rich_node.add(f"[cyan]Results:[/cyan] [bold]{count}[/bold] | {relax_str}")
            return

        var_name = variables_order[level]
        # Sort values: "None" at the end if present
        keys = sorted(current_dict.keys(), key=lambda x: (x == "None", x))
        
        for val in keys:
            branch_label = f"[yellow]{var_name}:[/yellow] [white]{val}[/white]"
            if val == "None":
                branch_label = f"[dim yellow]{var_name}:[/dim yellow] [dim white]N/A[/dim white]"
            
            sub_node = rich_node.add(branch_label)
            add_to_rich_tree(sub_node, current_dict[val], level + 1)

    add_to_rich_tree(root, tree_dict, 0)
    console.print(root)

    # Statistical Summary
    total_queries = len(results_data)
    relaxed_queries = [r for r in results_data if r['relaxation']]
    avg_results = sum(r['count'] for r in results_data) / total_queries
    max_results = max(r['count'] for r in results_data)
    min_results = min(r['count'] for r in results_data)

    print("\n" + "="*50)
    print("SUMMARY STATISTICS")
    print("="*50)
    print(f"Total Queries: {total_queries}")
    print(f"Total Relaxed Queries: {len(relaxed_queries)} ({len(relaxed_queries)/total_queries:.1%})")
    print(f"Average Results Count: {avg_results:.1f}")
    print(f"Max Results: {max_results}")
    print(f"Min Results: {min_results}")
    
    if relaxed_queries:
        print("\nRelaxed Queries Details:")
        for r in relaxed_queries:
            choice_str = ", ".join([f"{k}: {v}" for k,v in r['choices'].items() if v != "None"])
            print(f"- Query {r['id']:03d}: {choice_str} -> {r['count']} results")
    else:
        print("\nNo relaxation observed in any query.")
    print("="*50)

if __name__ == "__main__":
    generate_tree()
