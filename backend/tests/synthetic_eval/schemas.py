from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class RankingMetrics:
    """Metriche per singolo prompt."""
    prompt_id: str
    query: str
    predicted_count: int
    expected_count: int
    matched_count: int
    recall_at_k: float
    precision_at_k: float
    f1_at_k: float
    ndcg_at_k: float
    mrr: float
    matched_ids: List[str]
    missing_ids: List[str]
    extra_ids: List[str]
    position_deltas: Dict[str, int]
    success: bool
    error_msg: Optional[str]
    latency_ms: float


@dataclass
class ConsistencyMetrics:
    """Metriche di consistenza tra multiple run."""
    prompt_id: str
    num_runs: int
    avg_matched_count: float
    std_matched_count: float
    coefficient_variation: float
    jaccard_similarity_avg: float
    jaccard_similarity_min: float
    jaccard_similarity_max: float
    avg_position_variance: float
    avg_recall: float
    avg_precision: float
    avg_ndcg: float
    avg_mrr: float
    runs_metrics: List[Dict[str, Any]]
