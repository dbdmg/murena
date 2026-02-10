import json
import re
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def safe_extract_json(text: str, schema: Optional[Type[T]] = None) -> Any:
    """
    Estrae un JSON valido da una stringa, con pulizia e validazione opzionale.

    Args:
        text: La stringa di input (es. output LLM)
        schema: (Opzionale) Classe Pydantic per validare e parsare il JSON

    Returns:
        Il dizionario/lista parsato, oppure un'istanza del modello Pydantic.
        Restituisce None se il parsing fallisce.
    """
    if not text:
        return None

    cleaned_text = text.strip()

    # 1. Rimuovi blocchi markdown ```json ... ```
    if "```" in cleaned_text:
        # Cerca pattern ```json ... ``` o solo ``` ... ```
        match = re.search(r"```(?:json)?(.*?)```", cleaned_text, re.DOTALL)
        if match:
            cleaned_text = match.group(1).strip()

    # 2. Rimuovi eventuali prefissi/suffissi non JSON
    # Cerca il primo '{' o '[' e l'ultimo '}' o ']'
    # Questo è un approccio euristico semplice
    first_brace = cleaned_text.find("{")
    first_bracket = cleaned_text.find("[")

    start_idx = -1
    if first_brace != -1 and first_bracket != -1:
        start_idx = min(first_brace, first_bracket)
    elif first_brace != -1:
        start_idx = first_brace
    elif first_bracket != -1:
        start_idx = first_bracket

    if start_idx != -1:
        # Cerca l'ultimo carattere di chiusura corrispondente
        # Non è perfetto ma copre il 99% dei casi LLM
        last_brace = cleaned_text.rfind("}")
        last_bracket = cleaned_text.rfind("]")
        end_idx = max(last_brace, last_bracket)

        if end_idx > start_idx:
            cleaned_text = cleaned_text[start_idx : end_idx + 1]

    # 3. Tentativo di parsing con pulizia progressiva
    # Sostituiamo caratteri di controllo problematici prima del parsing
    cleaned_text = re.sub(r'[\x00-\x1F\x7F]', '', cleaned_text)

    try:
        data = json.loads(cleaned_text)
    except (json.JSONDecodeError, Exception) as e:
        # Fallback 1: Fix errori comuni degli LLM
        try:
            # 1. Rimuoviamo escape non necessari che gli LLM mettono spesso (es. \' o \ )
            fixed_text = re.sub(r"\\([' ])", r"\1", cleaned_text)
            
            # 2. Sostituiamo backslash che non sono seguiti da caratteri validi di escape JSON
            fixed_text = re.sub(r'\\(?![tnrfbu"/]|u[0-9a-fA-F]{4})', r'\\\\', fixed_text)
            
            # 3. Gestione trailing commas
            fixed_text = re.sub(r',\s*([\]}])', r'\1', fixed_text)
            
            # 4. Caso specifico: newline non escaped dentro stringhe
            # Questo è complicato da fare con regex senza rompere il JSON, 
            # proviamo almeno a normalizzare le newline
            fixed_text = fixed_text.replace('\n', '\\n').replace('\r', '\\r')
            # Ma poi dobbiamo ripristinare quelle che erano fuori dalle stringhe... 
            # In realtà json.loads gestisce bene le newline tra i campi se sono \n reali.
            
            data = json.loads(fixed_text)
        except Exception:
            # Fallback 2: Pulizia più aggressiva
            try:
                # Ripristiniamo il testo originale e facciamo solo le sostituzioni base
                basic_fix = cleaned_text.replace('\\', '\\\\') # Escapiamo tutto e poi ripristiniamo i necessari? No.
                # Tentativo disperato: rimuovere tutto ciò che non è ASCII? No.
                
                # Prova a rimuovere commenti // o /* */ se presenti
                no_comments = re.sub(r'//.*?\n|/\*.*?\*/', '', cleaned_text, flags=re.S)
                data = json.loads(no_comments)
            except Exception:
                return None
        except Exception:
            return None

    # 4. Validazione Pydantic (se schema fornito)
    if schema:
        try:
            return schema.model_validate(data)
        except Exception:
            # Se la validazione fallisce, potremmo ritornare None o i dati raw
            # Per sicurezza ritorniamo None, così il chiamante sa che non è conforme
            return None

    return data
