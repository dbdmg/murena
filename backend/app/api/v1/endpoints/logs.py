from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from pathlib import Path
import json
import os
import logging

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Percorso dei log - armonizzato con quanto visto in RankingEvaluator
POSSIBLE_LOGS_DIRS = [
    Path(settings.AGENT_LOGS_DIR),
    Path("tests/agent_logs"),
    Path("agent_logs")
]

class NoteUpdate(BaseModel):
    index: int
    notes: str

class UpdateNotesRequest(BaseModel):
    filename: str
    notes: List[NoteUpdate]

@router.post("/update-notes")
async def update_notes(request: UpdateNotesRequest):
    """Aggiorna le note in un file JSON di log esistente."""
    
    filename = request.filename
    if not filename.endswith(".json"):
        filename += ".json"
        
    target_file = None
    for log_dir in POSSIBLE_LOGS_DIRS:
        potential_path = log_dir / filename
        if potential_path.exists():
            target_file = potential_path
            break
            
    if not target_file:
        # Tenta una ricerca ricorsiva se non trovato nei posti standard
        # (Attenzione alle performance se le cartelle sono giganti, ma qui parliamo di log)
        logger.warning(f"File {filename} non trovato nei percorsi standard. Ricerca in corso...")
        for root, dirs, files in os.walk("."):
            if filename in files:
                target_file = Path(root) / filename
                break
    
    if not target_file:
        raise HTTPException(
            status_code=404, 
            detail=f"File {filename} non trovato. Assicurarsi che l'esecuzione della pipeline sia terminata."
        )
    
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "agent_executions" not in data:
            raise HTTPException(status_code=400, detail="Formato JSON non valido: manca 'agent_executions'")
            
        # Applichiamo le note
        executions = data["agent_executions"]
        for note_update in request.notes:
            if 0 <= note_update.index < len(executions):
                executions[note_update.index]["notes"] = note_update.notes
            else:
                logger.warning(f"Indice nota {note_update.index} fuori range per {filename}")
        
        # Salvataggio atomico (opzionale, semplifichiamo qui)
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Note aggiornate con successo in {target_file}")
        return {"status": "success", "file": str(target_file)}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Errore durante la lettura del JSON (file corrotto?)")
    except Exception as e:
        logger.error(f"Errore durante l'aggiornamento delle note: {e}")
        raise HTTPException(status_code=500, detail=str(e))
