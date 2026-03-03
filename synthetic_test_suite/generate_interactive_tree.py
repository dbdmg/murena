import json
import os

def generate_html_tree():
    base_path = "/Users/marcodeluca/Downloads/real-estate-ai/synthetic_test_suite"
    possibilities_path = os.path.join(base_path, "query_variables_possibilities.json")
    results_dir = os.path.join(base_path, "composed_results/gpt-5-nano")
    output_html = os.path.join(base_path, "interactive_query_tree.html")
    
    with open(possibilities_path, 'r') as f:
        possibilities = json.load(f)
    
    variables_order = [
        "tipologia_immobile",
        "punto_di_interesse",
        "metratura_totale",
        "progetto_destinazione_uso",
        "classe_energetica",
        "servizi_accessori"
    ]
    
    results_data = []
    for i in range(1, 487):
        filename = f"query_{i:03d}.json"
        filepath = os.path.join(results_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                query_text = data['query']
                choices = {}
                for var in variables_order:
                    choices[var] = "None"
                    for val in possibilities[var]:
                        if val.lower() in query_text.lower():
                            choices[var] = val
                            break
                results_data.append({
                    "name": f"Query {i:03d}",
                    "choices": choices,
                    "count": data.get('results_count', 0),
                    "relaxation": data.get('relaxation_applied', False)
                })

    def build_tree(items, vars_idx):
        if vars_idx >= len(variables_order):
            item = items[0]
            relax_info = " (RELAXED)" if item['relaxation'] else ""
            return {"name": f"Count: {item['count']}{relax_info}", "relaxation": item['relaxation']}
        
        current_var = variables_order[vars_idx]
        children = []
        possible_vals = possibilities[current_var] + (["None"] if current_var != "tipologia_immobile" else [])
        
        for val in possible_vals:
            subset = [item for item in items if item['choices'][current_var] == val]
            if subset:
                child_node = build_tree(subset, vars_idx + 1)
                node_name = f"{current_var}: {val}"
                
                # If the child node is a final count node, merge it for brevity
                if "children" not in child_node:
                    node_name += f" → {child_node['name']}"
                    children.append({
                        "name": node_name,
                        "relaxation": child_node.get('relaxation', False)
                    })
                else:
                    children.append({
                        "name": node_name,
                        "children": child_node["children"]
                    })
        
        return {"children": children}

    tree_data = {"name": "Query Space", "children": build_tree(results_data, 0)["children"]}

    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Query Composition Tree</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background: #0f172a; color: #f8fafc; margin: 0; overflow: hidden; }}
        .node circle {{ fill: #38bdf8; stroke: #0ea5e9; stroke-width: 1.5px; cursor: pointer; }}
        .node text {{ font-size: 10px; fill: #e2e8f0; pointer-events: none; }}
        .link {{ fill: none; stroke: #334155; stroke-width: 1px; stroke-opacity: 0.6; }}
        .relaxed-node circle {{ fill: #ef4444 !important; stroke: #dc2626 !important; }}
        .relaxed-text {{ fill: #f87171 !important; font-weight: 600; font-size: 11px !important; }}
        .header {{ position: absolute; top: 20px; left: 20px; z-index: 10; background: rgba(15, 23, 42, 0.8); padding: 10px; border-radius: 8px; }}
        h1 {{ margin: 0; font-size: 20px; color: #38bdf8; }}
        p {{ margin: 4px 0 0; font-size: 12px; color: #94a3b8; }}
        .legend {{ position: absolute; bottom: 20px; left: 20px; background: rgba(30, 41, 59, 0.9); padding: 12px; border-radius: 8px; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
        .legend-item {{ display: flex; align-items: center; margin: 6px 0; font-size: 12px; }}
        .dot {{ width: 10px; height: 10px; border-radius: 50%; margin-right: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Query Composition Explorer</h1>
        <p>Visualizing gpt-5-nano results Across 486 Permutations</p>
    </div>
    <div class="legend">
        <div class="legend-item"><div class="dot" style="background: #38bdf8;"></div> Valid result</div>
        <div class="legend-item"><div class="dot" style="background: #ef4444;"></div> Relaxed query</div>
        <div class="legend-item" style="color: #94a3b8; font-style: italic; margin-top: 8px;">Scroll to zoom, drag to pan</div>
    </div>
    <svg id="tree-viz"></svg>

    <script>
        const data = {json.dumps(tree_data)};
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select("#tree-viz")
            .attr("width", width)
            .attr("height", height)
            .call(d3.zoom().on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }}))
            .append("g");
            
        const g = svg.append("g").attr("transform", "translate(150, 20)");
        
        // Dynamic height based on node count to prevent overlap
        const tree = d3.tree().nodeSize([20, 280]);
        const root = d3.hierarchy(data);
        tree(root);
        
        const link = g.selectAll(".link")
            .data(root.links())
            .enter().append("path")
            .attr("class", "link")
            .attr("d", d3.linkHorizontal()
                .x(d => d.y)
                .y(d => d.x));
                
        const node = g.selectAll(".node")
            .data(root.descendants())
            .enter().append("g")
            .attr("class", d => "node" + (d.data.relaxation ? " relaxed-node" : ""))
            .attr("transform", d => `translate(${{d.y}},${{d.x}})`);
            
        node.append("circle").attr("r", 3.5);
        
        node.append("text")
            .attr("dy", ".31em")
            .attr("x", d => d.children ? -10 : 10)
            .attr("text-anchor", d => d.children ? "end" : "start")
            .text(d => d.data.name)
            .attr("class", d => d.data.relaxation ? "relaxed-text" : "");
            
    </script>
</body>
</html>
"""
    with open(output_html, 'w') as f:
        f.write(html_template)
    print(f"Generated {output_html}")

if __name__ == "__main__":
    generate_html_tree()
