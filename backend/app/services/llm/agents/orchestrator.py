from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import sqlparse
import tabulate

from app.core.config import settings

# Constants from settings
MAX_ITEMS_FOR_LLM = settings.MAX_ITEMS_FOR_LLM
MAX_ITEMS_FOR_MAP = settings.MAX_ITEMS_FOR_MAP
MAX_LLM_CAP = settings.MAX_LLM_CAP

from app.core.constants import APE_SCORE_LEGEND

from app.data.loaders import get_coordinates
from app.data.processors import calculate_travel_times_df
from app.services.llm.agents.ape_agent import ApeAgent
from app.services.llm.agents.consistency_agent import ConsistencyAgent
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.evaluation_agent import EvaluationAgent
from app.services.llm.agents.location_agent import LocationAgent
from app.services.llm.agents.needs_metric_agent import NeedsMetricAgent
from app.services.llm.agents.normative_agent import NormativeAgent
from app.services.llm.agents.poi_amenity_agent import PoiAmenityAgent
from app.services.llm.agents.poi_category_agent import PoiCategoryAgent
from app.services.llm.agents.schema import (
    AgentContext,
    EvaluationAgentResponse,
    NeedsMetricPlan,
)
from app.services.llm.agents.sql_agent import SQLAgent
from app.services.llm.agents.typology_agent import TypologyAgent


@dataclass
class OrchestratorResult:
    map_df: pd.DataFrame
    location: List[List[Union[str, float]]]
    status_msg: str
    gemini_responses: Dict[str, Any]
    where_clause: str
    context: AgentContext
    broker_summary: Optional[str] = None
