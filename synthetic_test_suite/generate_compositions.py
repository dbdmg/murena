import itertools
import os
import csv
import json

def generate_combinations(json_file: str, output_file: str) -> int:
    """
    Generates query compositions using total Cartesian product.
    
    Mandatory: tipologia_immobile
    Optional: all other keys can be present (with all values) or absent.
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Define keys and ordering according to template logic
    keys_order = [
        "tipologia_immobile",
        "punto_di_interesse",
        "metratura_totale",
        "classe_energetica",
        "progetto_destinazione_uso",
        "servizi_accessori"
    ]
    
    # Prepare option lists
    option_lists = []
    for key in keys_order:
        values = data.get(key, [])
        if key == "tipologia_immobile":
            # Mandatory: only the provided values
            option_lists.append(values)
        else:
            # Optional: values plus a 'None' state to represent absence
            option_lists.append(values + [None])
            
    all_compositions = []
    
    # Generate Cartesian product
    for combo in itertools.product(*option_lists):
        # Unpack combo (index coincides with keys_order)
        tipo, poi, metratura, classe, progetto, servizi = combo
        
        # Build query string piece by piece
        query = f"Cerca un {tipo}"
        
        if poi:
            query += f" vicino a {poi}"
        if metratura:
            query += f" con superficie {metratura}"
        if classe:
            query += f" in classe {classe}"
        if progetto:
            query += f", finalizzato a {progetto}"
        if servizi:
            query += f" e situato vicino a {servizi}"
            
        all_compositions.append(query)
            
    # Sort by character length (ascending)
    all_compositions.sort(key=len)

    # Write to CSV with status column
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['query', 'status'])
        for comp in all_compositions:
            writer.writerow([comp, 0])
    
    return len(all_compositions)

if __name__ == "__main__":
    base_path = "/Users/marcodeluca/Downloads/real-estate-ai/synthetic_test_suite"
    json_path = os.path.join(base_path, "query_variables_possibilities.json")
    output_path = os.path.join(base_path, "composed_queries.csv")
    
    count = generate_combinations(json_path, output_path)
    print(f"Generated {count} query compositions (Cartesian Product) in {output_path}")
