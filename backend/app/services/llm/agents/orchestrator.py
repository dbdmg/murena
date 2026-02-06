from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from app.core.config import settings

# Constants from settings
MAX_ITEMS_FOR_LLM = settings.MAX_ITEMS_FOR_LLM
MAX_ITEMS_FOR_MAP = settings.MAX_ITEMS_FOR_MAP
MAX_LLM_CAP = settings.MAX_LLM_CAP

from app.services.llm.agents.schema import AgentContext


@dataclass
class OrchestratorResult:
    map_df: pd.DataFrame
    location: List[List[Union[str, float]]]
    status_msg: str
    gemini_responses: Dict[str, Any]
    where_clause: str
    context: AgentContext
    broker_summary: Optional[str] = None
    agent_trace: Optional[List[Dict[str, Any]]] = None
