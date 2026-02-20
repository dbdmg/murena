import os
import json
import pandas as pd
import torch
import requests
import re
from typing import Optional, List
from tqdm import tqdm

# Attempt to import transformers for local execution
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(BASE_DIR, "composed_queries.csv")
METADATA_FILE = os.path.join(BASE_DIR, "..", "backend", "app", "data", "db_metadata_lite.json")

# Output folder configuration
OUTPUT_DIR = os.path.join(BASE_DIR, "arctic_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "arctic_sql_results.csv")

MODEL_ID = "Snowflake/Arctic-Text2SQL-R1-7B"
API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"

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
    def __init__(self, mode="api", token=None):
        self.mode = mode
        self.token = token
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        
        if mode == "local":
            if not TRANSFORMERS_AVAILABLE:
                raise ImportError("Transformers library not found. Run 'pip install transformers torch' or use mode='api'")
            
            print(f"Loading model {MODEL_ID} locally...")
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            
            print(f"Using device: {self.device}")
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.float16 if self.device != "cpu" else torch.float32,
                trust_remote_code=True
            ).to(self.device)

    def generate(self, prompt: str) -> str:
        if self.mode == "api":
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            payload = {
                "inputs": prompt,
                "parameters": {"max_new_tokens": 512, "temperature": 0.1, "return_full_text": False}
            }
            response = requests.post(API_URL, headers=headers, json=payload)
            if response.status_code != 200:
                return f"Error API: {response.text}"
            
            result = response.json()
            if isinstance(result, list):
                return result[0].get("generated_text", "")
            return str(result)
        else:
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=1024,
                    do_sample=False,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            decoded = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Remove the prompt prefix
            return decoded[len(prompt)-len("<think>\n"):]

def main():
    # CONFIGURATION
    # Set to 'api' to use Hugging Face Inference API (needs HF_TOKEN)
    # Set to 'local' to use local resources (needs ~8-15GB VRAM/RAM)
    MODE = os.getenv("ARCTIC_MODE", "api") 
    HF_TOKEN = os.getenv("HF_TOKEN")
    
    if MODE == "api" and not HF_TOKEN:
        print("Warning: HF_TOKEN not found. API might fail if not logged in.")

    print(f"Running in {MODE} mode.")
    
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
    
    for query in tqdm(queries):
        prompt = format_prompt(query, schema)
        raw_output = engine.generate(prompt)
        
        sql = extract_sql(raw_output)
        
        results.append({
            "query": query,
            "sql": sql,
            "raw_reasoning": raw_output.split("</think>")[0].replace("<think>", "").strip() if "<think>" in raw_output else "N/A"
        })
        
        # Backup save
        if len(results) % 5 == 0:
            pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)

    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Execution complete! Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
