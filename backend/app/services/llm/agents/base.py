from abc import ABC, abstractmethod

from app.utils.decorators import handle_agent_error


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    @handle_agent_error()
    def run(self, **kwargs):
        """Esegue l'agente restituendo un risultato strutturato."""
        raise NotImplementedError
