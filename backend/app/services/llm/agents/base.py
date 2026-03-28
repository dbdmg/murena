from abc import ABC, abstractmethod
import re

from app.utils.decorators import handle_agent_error


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    @handle_agent_error()
    def run(self, **kwargs):
        """Executes the agent returning a structured result."""
        raise NotImplementedError

    def render_template(self, template: str, **kwargs) -> str:
        """Replaces {key} with value while ignoring JSON curly braces.
        
        Uses a regex to find only simple placeholders like {query} or {statistics},
        avoiding interpretation of curly braces in JSON blocks which often cause KeyError.
        """
        if not template:
            return ""
            
        def replace_match(match):
            key = match.group(1)
            # Se la chiave è nel dizionario, la sostituiamo, altrimenti lasciamo il match originale
            return str(kwargs.get(key, match.group(0)))
            
        return re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_match, template)
