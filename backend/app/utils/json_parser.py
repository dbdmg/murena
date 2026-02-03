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

    # 3. Tentativo di parsing
    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError:
        # Fallback: prova a fixare errori comuni (es. trailing commas)
        # Questo è complesso da fare bene con regex, per ora ritorniamo None se fallisce
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
