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
import argparse
import sys
from pathlib import Path

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(BASE_DIR, "text2sql_queries.csv")
METADATA_FILE = os.path.join(BASE_DIR, "..", "backend", "app", "data", "db_metadata_lite.json")

# Output folder configuration
OUTPUT_DIR = os.path.join(BASE_DIR, "arctic_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "arctic_sql_results.csv")

MODEL_ID = "a-kore/Arctic-Text2SQL-R1-7B:latest"
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
    context = "\n-- DuckDB Custom Functions:\n-- haversine_km(lat1, lon1, lat2, lon2): Calculates distance (km) between two points. If distance is not specified, assume a default of 3 km.\n"
    
    return "\n".join(schema_parts) + context

def get_system_message(schema: str) -> str:
    """Returns the system message for API models."""
    return f"""You are a Text-to-SQL expert. Generate valid DuckDB SQL based on the provided schema.
Always use "SELECT *" instead of explicitly listing columns in the SELECT clause.
Use only the columns present in the schema for filtering and ordering.
Do NOT invent new tables or JOINs. The query must operate ONLY on the `IMMOBILI` table.
Do NOT use the LIMIT clause in your SQL queries.
Always include an ORDER BY clause. If the user query involves geographical information (like a point of interest or a specific location), order the results by distance using the haversine_km function. Otherwise, order by id.
Always reason before providing the SQL in the <think> block.
Return ONLY a valid JSON object after the <think> block, with the following format: {{"sql": "your SQL query here"}}. Do not include markdown formatting (like ```json), preamble, or postscript."""

def get_user_message(query: str, schema: str) -> str:
    """Returns the user message for API models."""
    return f"""### Database Schema:
{schema}

### Question:
{query}

### Response:
<think>
"""

def format_prompt(query: str, schema: str) -> str:
    """Formats the prompt for the R1-style Text2SQL local model."""
    sys_msg = get_system_message(schema)
    usr_msg = get_user_message(query, schema)
    return f"<|im_start|>system\n{sys_msg}\n<|im_end|>\n<|im_start|>user\n{usr_msg}"


def extract_sql(response: str) -> str:
    """Extracts SQL from the model response."""
    # Handle Reasoning model output
    content = response
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    
    # Clean markdown
    content = re.sub(r"```json\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"```\s*", "", content)
    content = content.strip()
    
    try:
        # Attempt to parse json
        json_match = re.search(r"(\{.*\})", content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
            if "sql" in parsed:
                return parsed["sql"].strip()
    except json.JSONDecodeError:
        pass
        
    # Fallback to regex extraction
    match = re.search(r"(SELECT\s+.*)", content, re.IGNORECASE | re.DOTALL)
    if match:
        sql = match.group(1).strip()
        if ";" in sql:
            sql = sql.split(";")[0].strip()
        return sql
    
    return content.strip()

class ArcticInference:
    def __init__(self, mode="ollama", model_name=MODEL_ID, token=None):
        self.mode = mode
        self.model_name = model_name

    def generate(self, query: str, schema: str) -> str:
        if self.mode == "ollama":
            prompt = format_prompt(query, schema)
            payload = {
                "model": self.model_name,
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
        else:
            # API Mode
            import sys
            from pathlib import Path
            base_dir = Path(__file__).resolve().parent.parent
            backend_dir = base_dir / "backend"
            if str(backend_dir) not in sys.path:
                sys.path.append(str(backend_dir))
                
            from app.services.llm.langchain_client import get_llm
            from langchain_core.messages import SystemMessage, HumanMessage
            
            llm = get_llm(model_name=self.model_name, temperature=0.1)
            sys_msg = SystemMessage(content=get_system_message(schema))
            usr_msg = HumanMessage(content=get_user_message(query, schema))
            
            try:
                response = llm.invoke([sys_msg, usr_msg])
                return response.content
            except Exception as e:
                return f"Error API: {e}"

def main():
    # CONFIGURATION
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=["open-weights", "gpt-5-nano"], default="open-weights", help="LLM model flavor")
    args, _ = parser.parse_known_args()

    # Determine mode and model
    if args.model == "gpt-5-nano":
        MODE = "api"
        # Patch sys.path for settings
        import sys
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent.parent
        backend_dir = base_dir / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.append(str(backend_dir))
            
        from app.core.config import settings
        settings.set_llm_model(args.model)
        active_model_id = settings.OPENAI_MODEL_FAST
    else:
        MODE = "ollama"
        active_model_id = MODEL_ID

    HF_TOKEN = None

    print(f"Running in {MODE} mode using model {active_model_id}.")

    
    print(f"Loading metadata from {METADATA_FILE}...")
    schema = load_metadata(METADATA_FILE)
    
    print(f"Loading queries from {QUERIES_FILE}...")
    if not os.path.exists(QUERIES_FILE):
        print(f"Error: {QUERIES_FILE} not found.")
        return
        
    df = pd.read_csv(QUERIES_FILE)
    
    if "status" not in df.columns:
        df["status"] = 0
        
    pending_mask = df["status"] == 0
    pending_indices = df[pending_mask].index.tolist()
    queries_to_process = [(idx, df.at[idx, "query"]) for idx in pending_indices]
    
    # For a quicker test, you can slice the queries: queries = queries[:10]
    
    try:
        engine = ArcticInference(mode=MODE, model_name=active_model_id, token=HF_TOKEN)
    except Exception as e:
        print(f"Initialization failed: {e}")
        return

    results = []
    print(f"Processing {len(queries_to_process)} queries (out of {len(df)} total)...")
    
    def process_query(idx, query):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                raw_output = engine.generate(query, schema)
                sql = extract_sql(raw_output)
                
                num_rows = -1
                
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
                
                # If query results are successful, break loop
                if num_rows >= 0:
                    break
            except Exception as e:
                num_rows = -1
                # If execution fails, continue loop to retry

        return {
            "idx": idx,
            "query": query,
            "sql": sql if 'sql' in locals() else "",
            "num_rows": num_rows
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_query = {executor.submit(process_query, idx, q): (idx, q) for idx, q in queries_to_process}
        for i, future in enumerate(tqdm(concurrent.futures.as_completed(future_to_query), total=len(queries_to_process)), 1):
            try:
                res = future.result()
                results.append(res)
                
                # Update status in original CSV DataFrame
                idx_to_update = res["idx"]
                if res["num_rows"] >= 0:
                    df.at[idx_to_update, "status"] = 1
                else:
                    df.at[idx_to_update, "status"] = 2
                    
            except Exception as exc:
                idx, q = future_to_query[future]
                print(f"Query {idx} generated an exception: {exc}")
                df.at[idx, "status"] = 2
                
            # Backup save
            if i % 5 == 0:
                pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
                df.to_csv(QUERIES_FILE, index=False)

    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
    df.to_csv(QUERIES_FILE, index=False)
    print(f"\n Execution complete! Results saved to {OUTPUT_FILE}")
    print(f" Statuses updated in {QUERIES_FILE}")

if __name__ == "__main__":
    main()
