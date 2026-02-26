import json
import re
import json_repair
import ast
from typing import Any, Optional, Type, TypeVar
from app.utils.logger import logger

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

    # 3. Parsing progressivo
    # Alcuni LLM restituiscono stringhe con escape eccessivi (es. \', \") o in formato Python literal.
    
    # 3a. Tentativo di "unescape" se la stringa sembra contenere molti escape di apici
    if '\\\'' in cleaned_text or '\\"' in cleaned_text:
        try:
            # decode('unicode_escape') risolve \', \", \\, \n ecc.
            # Lo facciamo con cautela trasformando prima in bytes
            cleaned_text = cleaned_text.encode('utf-8').decode('unicode_escape')
        except Exception:
            pass

    try:
        # 3b. Prova json_repair (molto robusto per JSON/Python-like)
        data = json_repair.loads(cleaned_text)
    except Exception:
        data = None

    # 3c. Fallback estremo: ast.literal_eval (se è un dizionario/lista Python valido)
    if not data or (not isinstance(data, (dict, list))):
        if cleaned_text and cleaned_text[0] in ('{', '['):
            try:
                # literal_eval è sicuro (non esegue codice) e ottimo per {'a': 'b'}
                data = ast.literal_eval(cleaned_text)
            except Exception:
                pass
            
    if not data:
        if cleaned_text and cleaned_text[0] in ('{', '['):
            logger.error(f"Fallimento totale nel parsing JSON di: {cleaned_text[:100]}...")
        else:
            # Non è un JSON, potrebbe essere una query SQL in chiaro o un testo discorsivo
            logger.debug(f"Testo non in formato JSON: {cleaned_text[:100]}...")
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
