import base64
import json
import os
from pathlib import Path
from typing import Any, List, Dict

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from app.core.config import AGENT_MODELS, USE_MOCK_NORMATIVE_AGENT
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import NormativeAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse, get_langfuse_callback
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage


DEFAULT_SYSTEM = """
ANALIZZA la documentazione normativa fornita ed ESTRAI SOLO i requisiti relativi a superfici e dimensioni che sono DIRETTAMENTE PERTINENTI alla query dell'utente.

IMPORTANTE:
- Analizza SOLO il testo fornito
- NON cercare informazioni esterne
- NON fare supposizioni
- Usa SOLO valori presenti nella documentazione
- Restituisci ESCLUSIVAMENTE JSON - niente testo aggiuntivo

JSON richiesto:
{{
  "requisiti": [
    {{
      "categoria": "superfici_minime_massime|requisiti_a_persona|altezze_dimensioni_verticali|dimensioni_minime_locali|superfici_obbligatorie|altro",
      "tipo": "descrizione specifica del requisito",
      "valore": numero,
      "unita": "unità",
      "normativa": "riferimento legislativo",
      "ambito": "contesto di applicazione",
      "descrizione": "spiegazione breve del requisito"
    }}
  ]
}}

REGOLE:
- Ogni requisito deve avere una categoria appropriata
- Valori numerici ESATTI dalla documentazione
- Includi una descrizione chiara per ogni requisito
- SOLO JSON - niente altro testo
"""

DEFAULT_USER = """Documentazione Normativa:
{normative_documents}

Query dell'utente: {query}"""


def _load_normative_documents() -> tuple[str, list[str], List[Dict[str, Any]]]:
    """
    Carica tutti i documenti normativi dalla cartella docs/knowledge/normativa/
    Restituisce una tupla: (testo_concatenato, lista_percorsi_file, lista_immagini_base64)
    """
    # Trova la directory backend (4 livelli sopra questo file: agents -> llm -> services -> app -> backend)
    backend_dir = Path(__file__).parent.parent.parent.parent.parent
    normative_dir = backend_dir / "docs" / "knowledge" / "normativa"
    
    if not normative_dir.exists():
        return "Nessun documento normativo disponibile.", [], []
    
    documents = []
    sources = []
    images = []
    
    # Leggi tutti i file nella cartella
    for file_path in normative_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in [".txt", ".md", ".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
            try:
                # Leggiamo file di testo
                if file_path.suffix.lower() in [".txt", ".md"]:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        documents.append(f"--- Documento: {file_path.name} ---\n{content}\n")
                        sources.append(str(file_path.relative_to(normative_dir.parent.parent.parent)))
                # Per immagini, le convertiamo in base64 per l'LLM
                elif file_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
                    with open(file_path, "rb") as f:
                        image_data = base64.b64encode(f.read()).decode('utf-8')
                        # Determina il tipo MIME
                        mime_type = f"image/{file_path.suffix.lower()[1:]}"
                        if file_path.suffix.lower() in [".jpg", ".jpeg"]:
                            mime_type = "image/jpeg"
                        images.append({
                            "name": file_path.name,
                            "data": image_data,
                            "mime_type": mime_type
                        })
                        documents.append(f"--- Immagine: {file_path.name} (inclusa per analisi visiva) ---\n")
                        sources.append(str(file_path.relative_to(normative_dir.parent.parent.parent)))
                # Per PDF e documenti Office, includiamo solo il riferimento
                elif file_path.suffix.lower() in [".pdf", ".doc", ".docx"]:
                    documents.append(f"--- Documento: {file_path.name} (file binario - richiede elaborazione separata) ---\n")
                    sources.append(str(file_path.relative_to(normative_dir.parent.parent.parent)))
            except Exception as e:
                continue
    
    if not documents:
        return "Nessun documento normativo disponibile.", [], []
    
    return "\n\n".join(documents), sources, images


def _extract_json(text: str) -> Any:
    """Prova ad estrarre un JSON dalla risposta del modello."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text)
    except Exception:
        pass

    start_positions = [text.find("{"), text.find("[")]
    start_positions = [p for p in start_positions if p != -1]
    if not start_positions:
        return None
    start = min(start_positions)
    for end in range(len(text), start, -1):
        fragment = text[start:end]
        try:
            return json.loads(fragment)
        except Exception:
            continue
    return None


class NormativeAgent(BaseAgent):
    name = "normative-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("normative_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)
        
        # Load system and user prompts separately
        self.system_prompt = get_system_prompt("normative_agent", DEFAULT_SYSTEM)
        self.user_template = get_user_template("normative_agent", DEFAULT_USER)

    @log_llm_usage
    @handle_agent_error(
        fallback_value=NormativeAgentResult(raw_text="Error", normative_info="{}", sources=[], prompt=None)
    )
    def run(self, query: str) -> NormativeAgentResult:
        if USE_MOCK_NORMATIVE_AGENT:
            mock_json = {
                "requisiti": [
                    {
                        "categoria": "superfici_minime_massime",
                        "tipo": "locale abitativo",
                        "valore": 14,
                        "unita": "mq",
                        "normativa": "D.M. 5/7/1975",
                        "ambito": "per alloggi",
                        "descrizione": "Superficie minima per locali abitativi"
                    },
                    {
                        "categoria": "requisiti_a_persona",
                        "tipo": "per persona",
                        "valore": 8,
                        "unita": "mq/persona",
                        "normativa": "Regolamento Regionale",
                        "ambito": "strutture ricettive",
                        "descrizione": "Spazio minimo per persona in strutture ricettive"
                    },
                    {
                        "categoria": "altezze_dimensioni_verticali",
                        "tipo": "altezza locale interno",
                        "valore": 2.7,
                        "unita": "m",
                        "normativa": "D.M. 5/7/1975",
                        "ambito": "locali abitabili",
                        "descrizione": "Altezza minima interna dei locali abitabili"
                    }
                ]
            }
            return NormativeAgentResult(
                raw_text=json.dumps(mock_json, indent=2, ensure_ascii=False),
                normative_info=json.dumps(mock_json, ensure_ascii=False),
                sources=["https://mock-normativa.it", "https://mock-comune.torino.it"],
                prompt=PromptRecord(
                    system="N/D",
                    user=query,
                ),
            )
        
        # Carica i documenti normativi
        normative_docs, sources, images = _load_normative_documents()
        
        # Prepara gli input per il prompt
        prompt_inputs = {
            "query": query,
            "normative_documents": normative_docs
        }
        
        # Format user prompt with variables
        user_text = self.user_template.format(**prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"
        
        # Se ci sono immagini, usa il formato multimodale
        if images:
            # Costruisci il messaggio con testo e immagini
            content = [
                {"type": "text", "text": full_text}
            ]
            
            # Aggiungi tutte le immagini
            for img in images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['mime_type']};base64,{img['data']}"
                    }
                })
            
            message = HumanMessage(content=content)
            
            # Per il caso multimodale, creiamo una chain senza callbacks per evitare conflitti
            chain = self.llm | JsonOutputParser()
            parsed_data = chain.invoke([message])
        else:
            # Formato tradizionale solo testo
            prompt_template = PromptTemplate.from_template(self.user_template)
            chain = prompt_template | self.llm | JsonOutputParser()
            
            # Invoca l'LLM
            parsed_data = invoke_with_langfuse(chain, prompt_inputs)
        
        # L'output parser restituisce già un dict JSON
        normative_info = json.dumps(parsed_data, ensure_ascii=False)
        
        return NormativeAgentResult(
            raw_text=json.dumps(parsed_data, indent=2, ensure_ascii=False),
            normative_info=normative_info,
            sources=sources,
            prompt=PromptRecord(
                system=self.system_prompt,
                user=user_text,
                full_text=full_text,
            ),
        )