from abc import ABC, abstractmethod
import re

from app.utils.decorators import handle_agent_error


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    @handle_agent_error()
    def run(self, **kwargs):
        """Esegue l'agente restituendo un risultato strutturato."""
        raise NotImplementedError

    def render_template(self, template: str, **kwargs) -> str:
        """Sostituisce {key} con value ignorando le parentesi graffe del JSON.
        
        Usa una regex per trovare solo i segnaposto semplici come {query} o {statistics},
        evitando di interpretare le parentesi graffe dei blocchi JSON che spesso causano KeyError.
        """
        if not template:
            return ""
            
        def replace_match(match):
            key = match.group(1)
            # Se la chiave è nel dizionario, la sostituiamo, altrimenti lasciamo il match originale
            return str(kwargs.get(key, match.group(0)))
            
        return re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_match, template)
