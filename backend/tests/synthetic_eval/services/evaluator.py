
import json
import os
import time
import uuid
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Any
from itertools import combinations
from dataclasses import asdict

from app.services.llm.langchain_client import flush_langfuse
from app.services.analysis_service import analysis_service
from app.services.agent_logger import AgentLogger

from ..schemas import RankingMetrics, ConsistencyMetrics

class RankingEvaluator:
    """Valutatore qualità ranking con ground truth."""
    
    def __init__(self, ground_truth_path: str, dataset_file: Path, k: int = 10, use_case: str = ""):
        self.ground_truth_path = Path(ground_truth_path)
        self.dataset_file = dataset_file
        self.k = k
        self.use_case = use_case
        
        with open(self.ground_truth_path, "r") as f:
            self.ground_truth = json.load(f)
        
        self.results_dir = Path("ranking_evaluation_results")
        self.results_dir.mkdir(exist_ok=True)
        
        # Crea logger per tracciare gli agenti
        self.agent_logs_dir = Path(__file__).parent.parent.parent / "agent_logs" # Adjust path relative to this file
        self.agent_logs_dir.mkdir(exist_ok=True, parents=True) # Ensure parents exist
        
        # Override global settings to prevent writing to data/agent_logs
        from app.core.config import settings
        settings.AGENT_LOGS_DIR = str(self.agent_logs_dir)
        
        from app.services.agent_logger import AgentLogger, set_active_evaluation_logger
        self.agent_logger = AgentLogger(self.agent_logs_dir)
        set_active_evaluation_logger(self.agent_logger)
    
    def run_prediction(self, query: str, prompt_id: str = "", run_number: int = 1) -> Tuple[List[str], float, Optional[str]]:
        """Esegue predizione e ritorna lista ID ordinati."""
        session_id = f"synthetic_eval_{self.dataset_file.stem}_{hash(query) % 10000}"
        
        os.environ["LANGFUSE_SESSION_ID"] = session_id
        os.environ["LANGFUSE_USER_ID"] = "ranking_eval_user"
        os.environ["LANGFUSE_TAGS"] = "synthetic_eval,ranking_test"

        def mock_set_progress(progress_data):
            pass
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.agent_logger.start_evaluation(self.use_case, prompt_id, run_number, timestamp, user_query=query)
        
        start_time = time.time()
        
        print(f" Running query with session_id: {session_id}")
        if self.agent_logger.current_log_file:
            print(f" Agent logs: {self.agent_logger.current_log_file}")
        
        try:
            self._setup_agent_logging_hooks()
            
            if str(self.dataset_file).endswith('.parquet'):
                synthetic_dataset = pd.read_parquet(str(self.dataset_file))
            else:
                synthetic_dataset = pd.read_csv(str(self.dataset_file))
            
            run_id = str(uuid.uuid4())
            
            result = asyncio.run(analysis_service.run_analysis(
                run_id=run_id,
                query=query,
                dataset_key="full",
                map_limit=15000,
                llm_limit=10,
                analysis_mode="agent",
                progress_callback=mock_set_progress,
                dataset=synthetic_dataset
            ))
            
            latency_ms = (time.time() - start_time) * 1000
            
            buildings = result.get("buildings", [])
            if buildings:
                map_df = pd.DataFrame([b.model_dump() for b in buildings])
                if 'final_ranking_score' in map_df.columns:
                    map_df = map_df.rename(columns={'final_ranking_score': 'evaluation_score'})
            else:
                map_df = None
            
            if map_df is not None and len(map_df) > 0:
                if "evaluation_score" in map_df.columns:
                    sorted_df = map_df.sort_values("evaluation_score", ascending=False)
                else:
                    sorted_df = map_df
                
                ids = sorted_df["id"].head(self.k).tolist()
                self.agent_logger.end_evaluation(success=True)
                return ids, latency_ms, None
            else:
                self.agent_logger.end_evaluation(success=False, error_msg="No results returned")
                return [], latency_ms, "No results returned"
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.agent_logger.end_evaluation(success=False, error_msg=str(e))
            return [], latency_ms, str(e)
        
        finally:
            try:
                flush_langfuse()
            except:
                pass
            
            try:
                self._restore_agent_hooks()
            except:
                pass
    
    def _setup_agent_logging_hooks(self):
        """Configura hooks per catturare input/output degli agenti."""
        os.environ["_AGENT_LOGGER_ACTIVE"] = "true"
        
        try:
            from app.services.llm.agents.location_agent import LocationAgent
            from app.services.llm.agents.property_technical_agent import PropertyTechnicalAgent
            from app.services.llm.agents.ape_agent import ApeAgent
            from app.services.llm.agents.poi_agent import PoiAgent
            from app.services.llm.agents.ranking_agent import RankingAgent
            from app.services.llm.agents.normative_agent import NormativeAgent
            from app.services.llm.agents.sql_agent import SQLAgent
            from app.services.llm.agents.evaluation_agent import EvaluationAgent
            # Gli agenti sono ora loggati direttamente dal GraphOrchestratorAgent tramite _log_execution
            # che propaga i log al logger globale attivo. Disabilitiamo gli hooks per evitare duplicati.
            agent_classes = []
            
            if not hasattr(self, '_original_run_methods'):
                self._original_run_methods = {}
            
            for agent_class in agent_classes:
                agent_name = agent_class.name if hasattr(agent_class, 'name') else agent_class.__name__
                
                if agent_class not in self._original_run_methods:
                    self._original_run_methods[agent_class] = agent_class.run
                
                def create_logged_run(original_run, captured_agent_name, captured_logger):
                    def logged_run(self_agent, **kwargs):
                        agent_start = time.time()
                        input_data = kwargs.copy()
                        
                        try:
                            result = original_run(self_agent, **kwargs)
                            execution_time = (time.time() - agent_start) * 1000
                            
                            if hasattr(result, 'prompt') and result.prompt:
                                input_data = result.prompt.model_dump()
                            
                            captured_logger.log_agent_execution(
                                agent_name=captured_agent_name,
                                input_data=input_data,
                                output_data=result,
                                execution_time_ms=execution_time,
                                agent_mode=kwargs.get("mode", "filtering"),
                                metadata={}
                            )
                            
                            return result
                        except Exception as e:
                            execution_time = (time.time() - agent_start) * 1000
                            captured_logger.log_agent_execution(
                                agent_name=captured_agent_name,
                                input_data=input_data,
                                output_data={"error": str(e), "error_type": type(e).__name__},
                                execution_time_ms=execution_time,
                                agent_mode=kwargs.get("mode", "filtering"),
                                metadata={"error": True}
                            )
                            raise
                    return logged_run
                
                agent_class.run = create_logged_run(
                    self._original_run_methods[agent_class],
                    agent_name,
                    self.agent_logger
                )
            
            print(f" Agent logging hooks attivati per {len(agent_classes)} agenti")
            
        except Exception as e:
            print(f" Impossibile configurare agent hooks: {e}")
            import traceback
            traceback.print_exc()
    
    def _restore_agent_hooks(self):
        """Ripristina i metodi originali degli agenti."""
        if hasattr(self, '_original_run_methods'):
            for agent_class, original_run in self._original_run_methods.items():
                agent_class.run = original_run
            print(f" Agent hooks ripristinati")
    
    def calculate_ndcg(self, predicted_ids: List[str], expected_items: List[Dict]) -> float:
        """Calcola NDCG."""
        if not predicted_ids or not expected_items:
            return 0.0
        
        relevance_map = {item["id"]: item["score_expected"] / 100.0 for item in expected_items}
        
        dcg = sum(relevance_map.get(pred_id, 0.0) / np.log2(i + 2) for i, pred_id in enumerate(predicted_ids))
        
        ideal_relevances = sorted(relevance_map.values(), reverse=True)[:len(predicted_ids)]
        idcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(ideal_relevances))
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def calculate_mrr(self, predicted_ids: List[str], expected_ids: List[str]) -> float:
        """Calcola MRR."""
        for i, pred_id in enumerate(predicted_ids, start=1):
            if pred_id in expected_ids:
                return 1.0 / i
        return 0.0
    
    def jaccard_similarity(self, set1: set, set2: set) -> float:
        """Calcola Jaccard similarity."""
        if not set1 and not set2:
            return 1.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def evaluate_with_consistency(self, use_case: str, prompt_id: str, num_runs: int) -> Tuple[RankingMetrics, Optional[ConsistencyMetrics]]:
        """Valuta prompt con test di consistenza."""
        # Get expected
        use_case_data = self.ground_truth["use_cases"][use_case]
        prompt_data = next(p for p in use_case_data["prompts"] if p["prompt_id"] == prompt_id)
        expected_items = prompt_data["expected_top10"][:self.k]
        expected_ids = [item["id"] for item in expected_items]
        query = prompt_data["query"]
        
        session_id = f"synthetic_eval_{self.dataset_file.stem}_{hash(query) % 10000}"
        
        print(f"\\n{'='*80}")
        print(f"Evaluating: {prompt_id}")
        if num_runs > 1:
            print(f"Consistency Test: {num_runs} runs")
        print(f"Query: {query}")
        print(f"Expected Top-{self.k}: {expected_ids}")
        print(f"{'='*80}")
        
        if num_runs == 1:
            # Single run
            predicted_ids, latency_ms, error_msg = self.run_prediction(query, prompt_id=prompt_id, run_number=1)
            flush_langfuse()
            
            matched_ids = [pid for pid in predicted_ids if pid in expected_ids]
            missing_ids = [eid for eid in expected_ids if eid not in predicted_ids]
            extra_ids = [pid for pid in predicted_ids if pid not in expected_ids]
            
            recall = len(matched_ids) / len(expected_ids) if expected_ids else 0.0
            precision = len(matched_ids) / len(predicted_ids) if predicted_ids else 0.0
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            ndcg = self.calculate_ndcg(predicted_ids, expected_items)
            mrr = self.calculate_mrr(predicted_ids, expected_ids)
            
            position_deltas = {}
            for item in expected_items:
                eid = item["id"]
                if eid in predicted_ids:
                    position_deltas[eid] = predicted_ids.index(eid) + 1 - item["rank"]
            
            print(f"\\n Metrics:")
            print(f"  Matched: {len(matched_ids)}/{len(expected_ids)}")
            print(f"  Recall@{self.k}: {recall:.2%}")
            print(f"  NDCG@{self.k}: {ndcg:.3f}")
            
            metrics = RankingMetrics(
                prompt_id=prompt_id,
                query=query,
                predicted_count=len(predicted_ids),
                expected_count=len(expected_ids),
                matched_count=len(matched_ids),
                recall_at_k=recall,
                precision_at_k=precision,
                f1_at_k=f1,
                ndcg_at_k=ndcg,
                mrr=mrr,
                matched_ids=matched_ids,
                missing_ids=missing_ids,
                extra_ids=extra_ids,
                position_deltas=position_deltas,
                success=error_msg is None,
                error_msg=error_msg,
                latency_ms=latency_ms
            )
            return metrics, None
        
        else:
            # Multiple runs
            print(f"\\nEsecuzione {num_runs} run...")
            all_results = []
            all_metrics = []
            
            for i in range(num_runs):
                run_session_id = f"{session_id}_run_{i+1}"
                trace_name = f"synthetic_eval_run_{i+1}"
                
                os.environ["LANGFUSE_SESSION_ID"] = run_session_id
                os.environ["LANGFUSE_TRACE_NAME"] = trace_name
                
                print(f"  Run {i+1}/{num_runs} - Session ID: {run_session_id}, Trace Name: {trace_name}...", end=" ", flush=True)
                
                predicted_ids, latency_ms, error_msg = self.run_prediction(query, prompt_id=prompt_id, run_number=i+1)
                flush_langfuse()
                
                if error_msg:
                    print(f" Error")
                    continue
                
                matched_ids = [pid for pid in predicted_ids if pid in expected_ids]
                recall = len(matched_ids) / len(expected_ids) if expected_ids else 0.0
                precision = len(matched_ids) / len(predicted_ids) if predicted_ids else 0.0
                ndcg = self.calculate_ndcg(predicted_ids, expected_items)
                mrr = self.calculate_mrr(predicted_ids, expected_ids)
                
                print(f" {len(matched_ids)}/{len(expected_ids)} matched ({latency_ms:.0f}ms)")
                
                all_results.append((predicted_ids, latency_ms))
                all_metrics.append({
                    "run_number": i + 1,
                    "predicted_ids": predicted_ids,
                    "matched_count": len(matched_ids),
                    "recall": recall,
                    "precision": precision,
                    "ndcg": ndcg,
                    "mrr": mrr,
                    "latency_ms": latency_ms
                })
            
            if len(all_results) < 2:
                print(f"  Troppo pochi run successo")
                return RankingMetrics(
                    prompt_id=prompt_id, query=query, predicted_count=0, expected_count=len(expected_ids),
                    matched_count=0, recall_at_k=0.0, precision_at_k=0.0, f1_at_k=0.0, ndcg_at_k=0.0,
                    mrr=0.0, matched_ids=[], missing_ids=expected_ids, extra_ids=[], position_deltas={},
                    success=False, error_msg="Insufficient runs", latency_ms=0.0
                ), None
            
            # Calcola consistency
            matched_counts = [m["matched_count"] for m in all_metrics]
            avg_matched = np.mean(matched_counts)
            std_matched = np.std(matched_counts)
            cv = std_matched / avg_matched if avg_matched > 0 else 0.0
            
            jaccard_scores = []
            for (ids1, _), (ids2, _) in combinations(all_results, 2):
                jaccard_scores.append(self.jaccard_similarity(set(ids1), set(ids2)))
            
            js_avg = np.mean(jaccard_scores) if jaccard_scores else 0.0
            js_min = np.min(jaccard_scores) if jaccard_scores else 0.0
            js_max = np.max(jaccard_scores) if jaccard_scores else 0.0
            
            id_positions = {}
            for predicted_ids, _ in all_results:
                for i, pid in enumerate(predicted_ids):
                    if pid not in id_positions:
                        id_positions[pid] = []
                    id_positions[pid].append(i + 1)
            
            position_variances = [np.var(positions) for positions in id_positions.values() if len(positions) >= 2]
            avg_pos_variance = np.mean(position_variances) if position_variances else 0.0
            
            avg_recall = np.mean([m["recall"] for m in all_metrics])
            avg_precision = np.mean([m["precision"] for m in all_metrics])
            avg_ndcg = np.mean([m["ndcg"] for m in all_metrics])
            avg_mrr = np.mean([m["mrr"] for m in all_metrics])
            
            print(f"\\n Count Metrics:")
            print(f"  Avg Matched: {avg_matched:.2f} ± {std_matched:.2f}")
            print(f"  CV: {cv:.3f}", end="")
            if cv < 0.1: print("  EXCELLENT")
            elif cv < 0.2: print("  GOOD")
            else: print("  MODERATE")
            
            print(f"\\n Jaccard Similarity:")
            print(f"  Avg: {js_avg:.3f}")
            
            consistency = ConsistencyMetrics(
                prompt_id=prompt_id,
                num_runs=len(all_results),
                avg_matched_count=avg_matched,
                std_matched_count=std_matched,
                coefficient_variation=cv,
                jaccard_similarity_avg=js_avg,
                jaccard_similarity_min=js_min,
                jaccard_similarity_max=js_max,
                avg_position_variance=avg_pos_variance,
                avg_recall=avg_recall,
                avg_precision=avg_precision,
                avg_ndcg=avg_ndcg,
                avg_mrr=avg_mrr,
                runs_metrics=all_metrics
            )
            
            # Return metriche medie
            ranking_metrics = RankingMetrics(
                prompt_id=prompt_id,
                query=query,
                predicted_count=int(avg_matched),
                expected_count=len(expected_ids),
                matched_count=int(avg_matched),
                recall_at_k=avg_recall,
                precision_at_k=avg_precision,
                f1_at_k=0.0,
                ndcg_at_k=avg_ndcg,
                mrr=avg_mrr,
                matched_ids=all_metrics[0]["predicted_ids"], # Use first run as representative
                missing_ids=[],
                extra_ids=[],
                position_deltas={},
                success=True,
                error_msg=None,
                latency_ms=all_metrics[0]["latency_ms"]
            )
            
            return ranking_metrics, consistency
