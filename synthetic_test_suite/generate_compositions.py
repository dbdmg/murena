import itertools
import os
import csv

def generate_combinations(input_file: str, output_file: str) -> int:
    """
    Generates all possible combinations of subqueries and saves them to a CSV file.
    
    Args:
        input_file: Path to the file containing subqueries.
        output_file: Path to the output CSV file.
        
    Returns:
        The total number of generated compositions.
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        # Read lines and strip leading line numbers/whitespace
        lines = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Remove line number prefix if present (e.g., "1: ")
            if ':' in line.split(' ')[0]:
                line = line.split(':', 1)[-1].strip()
            lines.append(line)
    
    subqueries = [line.strip() for line in lines]
    all_compositions = []
    
    # Generate powerset excluding the empty set (2^n - 1)
    for r in range(1, len(subqueries) + 1):
        for combo in itertools.combinations(subqueries, r):
            # Join fragments exactly with a space
            query = " ".join(combo)
            all_compositions.append(query)
            
    # Write to CSV with status column
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['query', 'status'])
        for comp in all_compositions:
            writer.writerow([comp, 0])
    
    return len(all_compositions)

if __name__ == "__main__":
    base_path = "/Users/marcodeluca/Downloads/real-estate-ai/synthetic_test_suite"
    input_path = os.path.join(base_path, "subqueries.txt")
    output_path = os.path.join(base_path, "composed_queries.csv")
    
    count = generate_combinations(input_path, output_path)
    print(f"Generated {count} query compositions in {output_path}")
