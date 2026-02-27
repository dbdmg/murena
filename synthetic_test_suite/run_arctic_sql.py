import os
import json
import pandas as pd
import numpy as np
import torch
import requests
import re
import duckdb
from typing import Optional, List
from tqdm import tqdm
import concurrent.futures

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(BASE_DIR, "composed_queries.csv")
METADATA_FILE = os.path.join(BASE_DIR, "..", "backend", "app", "data", "db_metadata_lite.json")

# Output folder configuration
OUTPUT_DIR = os.path.join(BASE_DIR, "arctic_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "arctic_sql_results.csv")

MODEL_ID = "a-kore/Arctic-Text2SQL-R1-7B"
OLLAMA_URL = "http://localhost:11434/api/generate"

def load_metadata(path: str) -> str:
    """Loads and formats metadata into a SQL-friendly schema string."""
    if not os.path.exists(path):
        return "-- Metadata file not found. Please check paths."
        
    with open(path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    
    schema_parts = ["CREATE TABLE IMMOBILI ("]
    columns = meta.get("sql_filtering_rules", {}).get("filterable_columns", [])
    
    col_defs = []
    for col in columns:
        col_info = meta.get(col, {})
        desc = col_info.get("description", "")
        values = col_info.get("values", [])
        
        # Determine a simple type
        if any(x in col for x in ["superficie", "latitudine", "longitudine", "epglnren"]):
            col_type = "FLOAT"
        elif col in ["sanita", "mobilita", "verde", "sport", "commerciale", "educazione"]:
            col_type = "INTEGER"
        elif "score" in col:
            col_type = "FLOAT"
        else:
            col_type = "VARCHAR"
            
        comment = f" -- {desc}" if desc else ""
        if values:
            comment += f" Allowed values: {', '.join(map(str, values[:10]))}"
            if len(values) > 10:
                comment += "..."
                
        col_defs.append(f"  {col} {col_type}{comment}")
    
    schema_parts.append(",\n".join(col_defs))
    schema_parts.append(");")
    
    # Add help context for specific functions
    context = "\n-- DuckDB Custom Functions:\n-- haversine_km(lat1, lon1, lat2, lon2): Calculates distance (km) between two points.\n"
    
    return "\n".join(schema_parts) + context

def format_prompt(query: str, schema: str) -> str:
    """Formats the prompt for the R1-style Text2SQL model."""
    return f"""<|im_start|>system
You are a Text-to-SQL expert. Generate valid DuckDB SQL based on the provided schema.
Use only the columns present in the schema.
Always reason before providing the SQL in the <think> block.
<|im_end|>
<|im_start|>user
### Database Schema:
{schema}

### Question:
{query}

### Response:
<think>
"""

def extract_sql(response: str) -> str:
    """Extracts SQL from the model response."""
    # Handle Reasoning model output
    content = response
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    
    # Clean markdown
    content = re.sub(r"```sql\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"```\s*", "", content)
    
    # Find first SELECT
    match = re.search(r"(SELECT\s+.*)", content, re.IGNORECASE | re.DOTALL)
    if match:
        sql = match.group(1).strip()
        if ";" in sql:
            sql = sql.split(";")[0].strip()
        return sql
    
    return content.strip()

class ArcticInference:
    def __init__(self, mode="ollama", token=None):
        self.mode = mode

    def generate(self, prompt: str) -> str:
        payload = {
            "model": MODEL_ID,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 1024
            }
        }
        try:
            response = requests.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except requests.exceptions.RequestException as e:
            return f"Error API: {e}"

def main():
    # CONFIGURATION
    # Run using local Ollama model
    MODE = "ollama"
    HF_TOKEN = None

    print(f"Running in {MODE} mode using model {MODEL_ID}.")
    
    print(f"Loading metadata from {METADATA_FILE}...")
    schema = load_metadata(METADATA_FILE)
    
    print(f"Loading queries from {QUERIES_FILE}...")
    if not os.path.exists(QUERIES_FILE):
        print(f"Error: {QUERIES_FILE} not found.")
        return
        
    df = pd.read_csv(QUERIES_FILE)
    queries = df["query"].tolist()
    
    # For a quicker test, you can slice the queries: queries = queries[:10]
    
    try:
        engine = ArcticInference(mode=MODE, token=HF_TOKEN)
    except Exception as e:
        print(f"Initialization failed: {e}")
        return

    results = []
    print(f"Processing {len(queries)} queries...")
    
    def process_query(query):
        prompt = format_prompt(query, schema)
        raw_output = engine.generate(prompt)
        sql = extract_sql(raw_output)
        
        num_rows = -1
        try:
            def haversine_km(lat1, lon1, lat2, lon2):
                R = 6371  # Earth radius in km
                lat1, lon1, lat2, lon2 = map(
                    np.radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
                )
                dlon, dlat = lon2 - lon1, lat2 - lat1
                a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
                c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
                return R * c

            dataset_path = os.path.abspath(os.path.join(BASE_DIR, "..", "backend", "data", "FOLDER_META", "immobili_with_meta_and_ape_full_cleaned.parquet"))
            with duckdb.connect(database=":memory:") as con:
                con.create_function("haversine_km", haversine_km, return_type="FLOAT")
                con.execute(f"CREATE VIEW IMMOBILI AS SELECT * FROM '{dataset_path}'")
                res = con.execute(sql).fetchdf()
                num_rows = len(res)
        except Exception as e:
            num_rows = -1

        return {
            "query": query,
            "sql": sql,
            "num_rows": num_rows,
            "raw_reasoning": raw_output.split("</think>")[0].replace("<think>", "").strip() if "<think>" in raw_output else "N/A"
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_query = {executor.submit(process_query, q): q for q in queries}
        for i, future in enumerate(tqdm(concurrent.futures.as_completed(future_to_query), total=len(queries)), 1):
            try:
                res = future.result()
                results.append(res)
            except Exception as exc:
                print(f"Query generated an exception: {exc}")
                
            # Backup save
            if i % 5 == 0:
                pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)

    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
    print(f"\n Execution complete! Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
