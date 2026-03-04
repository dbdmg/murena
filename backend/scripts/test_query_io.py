"""
Test script for a specific real estate query.
Captures input and output for Property Technical Agent and SQL Agent.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Setup and environment
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv
load_dotenv(BACKEND_ROOT / ".env")

# Ensure required environment variables for tracing are set if needed
# os.environ["RUN_REAL_LLM_TESTS"] = "1"

from app.services.analysis_service import AnalysisService

async def test_specific_query() -> None:
    """
    Esegue una query immobiliare specifica e salva l'output dell'agente in un file JSON.
    
    Il file viene salvato nella directory 'backend/scripts/outputs' utilizzando un
    nome file basato sull'ID dell'esecuzione (timestamp).
    """
    # Assicura che la directory di lavoro sia la root del backend
    os.chdir(BACKEND_ROOT)
    
    # Technical restatement: "Agente per l'analisi tecnica e Agente SQL"
    query = "Seleziona gli immobili vicino a Porta Susa per destinarli a studentato strutturato in 20 micro alloggi con superficie compresa tra 50 e 80 metri quadrati ciascuno e vicinanza a servizi di trasporto urbano"
    run_id = f"test_io_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    service = AnalysisService()
    
    try:
        results = await service.run_analysis(
            run_id=run_id,
            query=query,
            dataset_key="full",
            map_limit=10,
            llm_limit=5,
            analysis_mode="agent"
        )
        
        # Estrai la trace dell'agent (senza filtri per debug)
        agent_trace = results.get("agent_trace", [])
        
        # Struttura l'output finale come JSON
        output_json = {
            "query": query,
            "run_id": run_id,
            "status": results.get("status"),
            "agent_io": agent_trace,
            "gemini_responses": results.get("gemini_responses"),
            "summary": {
                "results_count": results.get("results_count"),
                "relaxation_applied": results.get("relaxation_applied", False)
            }
        }
        
        # Salva l'output su file invece di stamparlo su console
        output_dir = BACKEND_ROOT / "scripts" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{run_id}.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_json, f, indent=2, ensure_ascii=False)
            
        print(f"Risultati salvati in: {output_file}")
            
    except Exception as e:
        error_json = {
            "status": "error",
            "error_message": str(e),
            "query": query
        }
        
        # Salva l'errore su file
        output_dir = BACKEND_ROOT / "scripts" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{run_id}_error.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(error_json, f, indent=2, ensure_ascii=False)
            
        print(f"Errore salvato in: {output_file}")

if __name__ == "__main__":
    asyncio.run(test_specific_query())
