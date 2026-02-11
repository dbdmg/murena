
import json
import numpy as np
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Dict
from dataclasses import asdict

from .config import USE_CASE_CONFIGS, AVAILABLE_AGENTS
from .services.generator import SyntheticDataGenerator
from .services.evaluator import RankingEvaluator
from .schemas import RankingMetrics, ConsistencyMetrics

import pandas as pd
from app.core.config import settings

class SyntheticEvaluationTest:
    """Orchestratore test completo."""
    
    def __init__(self, use_case: str, num_immobili: int, num_poi: int, num_runs: int, ablation_mode: bool = False, disabled_agents: Optional[Set[str]] = None):
        self.use_case = use_case
        self.num_immobili = num_immobili
        self.num_poi = num_poi
        self.num_runs = num_runs
        self.ablation_mode = ablation_mode
        self.disabled_agents = disabled_agents or set()
        self.synthetic_dir = Path("synthetic_data")
        self.synthetic_dir.mkdir(exist_ok=True)
        self.results_dir = Path("test_results")
        self.results_dir.mkdir(exist_ok=True)
        self.ablation_dir = Path("ablation_results")
        self.ablation_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def step1_generate_dataset(self) -> bool:
        """Step 1: Carica dataset reale (Immobili)."""
        print("\n" + "🎯 STEP 1: CARICAMENTO DATASET REALE".center(80, "="))
        
        # Costruisci path assoluto per il dataset reale
        # settings.DATASET_FULL è relativo alla root del backend
        base_dir = Path(__file__).resolve().parent.parent.parent.parent # /backend
        dataset_path = base_dir / "backend" / settings.DATASET_FULL
        
        if not dataset_path.exists():
            # Fallback path se non trovato (es. setup locale diverso)
            dataset_path = Path("/Users/marcodeluca/Downloads/real-estate-ai/backend") / settings.DATASET_FULL
        
        if not dataset_path.exists():
            print(f"❌ Dataset non trovato: {dataset_path}")
            return False
            
        try:
            self.df_immobili = pd.read_parquet(dataset_path)
            # Ensure ID is string
            if "id" in self.df_immobili.columns:
                self.df_immobili["id"] = self.df_immobili["id"].astype(str)
                
            self.dataset_file = dataset_path
            
            # Per il dataset reale, i file POI e Distanze non vengono rigenerati qui
            # Ma assegniamo path validi esistenti o None
            self.poi_file = base_dir / "backend" / "data/FOLDER_STATIC_ROME/pois.json"
            self.distances_file = None
            
            print(f"✓ Dataset reale caricato: {self.dataset_file}")
            print(f"  - {len(self.df_immobili)} immobili")
            return True
        except Exception as e:
            print(f"❌ Errore caricamento dataset: {e}")
            return False
    
    def step2_create_ground_truth(self) -> bool:
        """Step 2: Crea ground truth automatico."""
        print("\\n" + "🎯 STEP 2: CREAZIONE GROUND TRUTH".center(80, "="))
        
        ground_truth_path = self.synthetic_dir / f"ground_truth_{self.use_case}_{self.timestamp}.json"
        
        available_ids = self.df_immobili['id'].tolist()[:20]
        
        config = USE_CASE_CONFIGS[self.use_case]
        
        ground_truth = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "description": f"Ground truth auto-generato per test {self.use_case}",
                "dataset_version": self.dataset_file.stem,
                "k": 10,
                "author": "test_script",
                "test_mode": True
            },
            "use_cases": {
                self.use_case: {
                    "description": f"Test case per {self.use_case}",
                    "target_audience": "Test",
                    "prompts": [
                        {
                            "prompt_id": f"{self.use_case}_test_{j+1:03d}",
                            "query": query,
                            "context": "Test automatico",
                            "expected_top10": [
                                {
                                    "rank": i + 1,
                                    "id": available_ids[(j * 10 + i) % len(available_ids)] if available_ids else f"IMM{i+1:03d}",
                                    "score_expected": 95 - (i * 5),
                                    "pros": [
                                        "Posizione strategica per destinazione d'uso",
                                        "Buona accessibilità mezzi pubblici",
                                        "Vicinanza servizi essenziali"
                                    ],
                                    "cons": [
                                        "Interventi di riqualificazione necessari",
                                        "Costi di manutenzione ordinaria",
                                        "Adeguamento normativo da completare"
                                    ],
                                    "comment": f"Valutazione esperto MEF - edificio dismesso candidato per riqualificazione {self.use_case}"
                                }
                                for i in range(10)
                            ]
                        }
                        for j, query in enumerate(config["test_queries"])
                    ]
                }
            }
        }
        
        with open(ground_truth_path, 'w', encoding='utf-8') as f:
            json.dump(ground_truth, f, indent=2, ensure_ascii=False)
        
        self.ground_truth_path = ground_truth_path
        
        print(f"✓ Ground truth creato: {ground_truth_path}")
        print(f"  - {len(config['test_queries'])} query generate per {self.use_case}")
        return True
    
    def step3_evaluate_ranking(self) -> bool:
        """Step 3: Valuta ranking quality."""
        print("\\n" + "🎯 STEP 3: VALUTAZIONE RANKING QUALITY".center(80, "="))
        
        if self.disabled_agents:
            import os
            os.environ["DISABLED_AGENTS"] = ",".join(self.disabled_agents)
            print(f"⚠️  Agents disabilitati: {', '.join(self.disabled_agents)}")
        
        evaluator = RankingEvaluator(
            ground_truth_path=str(self.ground_truth_path),
            dataset_file=self.dataset_file,
            k=10,
            use_case=self.use_case
        )
        
        with open(self.ground_truth_path, 'r', encoding='utf-8') as f:
            ground_truth_data = json.load(f)
        
        prompts = ground_truth_data["use_cases"][self.use_case]["prompts"]
        num_prompts = len(prompts)
        
        print(f"\\nValutazione {num_prompts} query per {self.use_case}...")
        
        all_ranking_metrics = []
        all_consistency_metrics = []
        results = {self.use_case: {}}
        
        for i, prompt_data in enumerate(prompts, 1):
            prompt_id = prompt_data["prompt_id"]
            print(f"\\n  [{i}/{num_prompts}] {prompt_id}")
            print(f"  Query: {prompt_data['query'][:80]}...")
            
            ranking_metrics, consistency_metrics = evaluator.evaluate_with_consistency(
                use_case=self.use_case,
                prompt_id=prompt_id,
                num_runs=self.num_runs
            )
            
            all_ranking_metrics.append(ranking_metrics)
            all_consistency_metrics.append(consistency_metrics)
            
            results[self.use_case][prompt_id] = {
                "ranking": asdict(ranking_metrics),
                "consistency": asdict(consistency_metrics) if consistency_metrics else None
            }
            
            print(f"  Recall: {ranking_metrics.recall_at_k:.2%} | NDCG: {ranking_metrics.ndcg_at_k:.3f}")
        
        if self.disabled_agents:
            import os
            if "DISABLED_AGENTS" in os.environ:
                del os.environ["DISABLED_AGENTS"]
        
        self.all_ranking_metrics = all_ranking_metrics
        self.all_consistency_metrics = all_consistency_metrics
        
        if self.ablation_mode:
            config_name = "baseline" if not self.disabled_agents else f"without_{'_'.join(sorted(self.disabled_agents))}"
            result_file = self.ablation_dir / f"ablation_{config_name}_{self.timestamp}.json"
        else:
            result_file = self.results_dir / f"test_result_{self.timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.result_file = result_file
        
        print(f"✓ Valutazione completata su {num_prompts} query")
        print(f"📝 Log dettagliati degli agenti (input/output) salvati in: {evaluator.agent_logs_dir}")
        return True
    
    def step4_analyze_results(self) -> bool:
        """Step 4: Analizza risultati."""
        print("\\n" + "🎯 STEP 4: ANALISI RISULTATI".center(80, "="))
        
        print("\\n" + "="*80)
        print("RISULTATI FINALI - MEDIE SU TUTTE LE QUERY")
        print("="*80)
        
        avg_recall = np.mean([m.recall_at_k for m in self.all_ranking_metrics])
        avg_precision = np.mean([m.precision_at_k for m in self.all_ranking_metrics])
        avg_f1 = np.mean([m.f1_at_k for m in self.all_ranking_metrics])
        avg_ndcg = np.mean([m.ndcg_at_k for m in self.all_ranking_metrics])
        avg_mrr = np.mean([m.mrr for m in self.all_ranking_metrics])
        avg_latency = np.mean([m.latency_ms for m in self.all_ranking_metrics])
        
        print(f"\\n📊 Ranking Metrics (media su {len(self.all_ranking_metrics)} query):")
        print(f"    Recall@10:    {avg_recall:.2%}")
        print(f"    Precision@10: {avg_precision:.2%}")
        print(f"    F1@10:        {avg_f1:.2%}")
        print(f"    NDCG@10:      {avg_ndcg:.3f}")
        print(f"    MRR:          {avg_mrr:.3f}")
        print(f"    Latency:      {avg_latency:.0f}ms")
        
        consistency_with_data = [c for c in self.all_consistency_metrics if c is not None]
        if consistency_with_data:
            avg_cv = np.mean([c.coefficient_variation for c in consistency_with_data])
            avg_jaccard = np.mean([c.jaccard_similarity_avg for c in consistency_with_data])
            avg_pos_var = np.mean([c.avg_position_variance for c in consistency_with_data])
            
            print(f"\\n    🔬 Consistency (media {self.num_runs} runs per query):")
            print(f"      CV:           {avg_cv:.3f}", end="")
            if avg_cv < 0.1: print(" ✅ EXCELLENT")
            elif avg_cv < 0.2: print(" ✓ GOOD")
            else: print(" ⚠️ MODERATE")
            
            print(f"      Jaccard Avg:  {avg_jaccard:.3f}", end="")
            if avg_jaccard > 0.8: print(" ✅ STRONG")
            elif avg_jaccard > 0.6: print(" ✓ GOOD")
            else: print(" ⚠️ WEAK")
            
            print(f"      Pos Variance: {avg_pos_var:.2f}")
        else:
            avg_cv = 0.0
            avg_jaccard = 0.0
            avg_pos_var = 0.0
        
        self.ranking_metrics = RankingMetrics(
            prompt_id="aggregate",
            query="aggregate",
            predicted_count=0,
            expected_count=0,
            matched_count=0,
            recall_at_k=avg_recall,
            precision_at_k=avg_precision,
            f1_at_k=avg_f1,
            ndcg_at_k=avg_ndcg,
            mrr=avg_mrr,
            matched_ids=[],
            missing_ids=[],
            extra_ids=[],
            position_deltas={},
            success=True,
            error_msg=None,
            latency_ms=avg_latency
        )
        
        if consistency_with_data:
            self.consistency_metrics = ConsistencyMetrics(
                prompt_id="aggregate",
                num_runs=self.num_runs,
                avg_matched_count=0,
                std_matched_count=0,
                coefficient_variation=avg_cv,
                jaccard_similarity_avg=avg_jaccard,
                jaccard_similarity_min=0,
                jaccard_similarity_max=0,
                avg_position_variance=avg_pos_var,
                avg_recall=avg_recall,
                avg_precision=avg_precision,
                avg_ndcg=avg_ndcg,
                avg_mrr=avg_mrr,
                runs_metrics=[]
            )
        else:
            self.consistency_metrics = None
        
        print(f"\\n✓ Risultati salvati: {self.result_file}")
        
        return True
    
    def run_full_test(self) -> bool:
        """Esegue test completo."""
        print("\\n" + "🚀 SYNTHETIC EVALUATION - TEST COMPLETO".center(80, "="))
        print(f"Use Case: {self.use_case}")
        print(f"Immobili: {self.num_immobili}")
        print(f"POI per categoria: {self.num_poi}")
        print(f"Consistency Runs: {self.num_runs}")
        if self.ablation_mode:
            print(f"Ablation Mode: {'Baseline' if not self.disabled_agents else f'Disabled: {self.disabled_agents}'}")
        print(f"Timestamp: {self.timestamp}")
        
        steps = [
            ("Generazione Dataset", self.step1_generate_dataset),
            ("Creazione Ground Truth", self.step2_create_ground_truth),
            ("Valutazione Ranking", self.step3_evaluate_ranking),
            ("Analisi Risultati", self.step4_analyze_results)
        ]
        
        for i, (name, step_func) in enumerate(steps, 1):
            print(f"\\n\\n{'#'*80}")
            print(f"# STEP {i}/{len(steps)}: {name}")
            print(f"{'#'*80}")
            
            success = step_func()
            
            if not success:
                print(f"\\n❌ Test fallito allo step {i}: {name}")
                return False
        
        print("\\n\\n" + "="*80)
        print("✅ TEST COMPLETO COMPLETATO CON SUCCESSO!")
        print("="*80)
        if self.ablation_mode:
            print(f"\\n📁 Risultati salvati in: {self.ablation_dir}")
        else:
            print(f"\\n📁 Risultati salvati in: {self.results_dir}")
        print(f"📊 File risultato: {self.result_file.name}")
        
        return True
    
    def run_full_ablation(self) -> bool:
        """Esegue ablation study completo testando ogni agent."""
        print("\\n" + "🔬 ABLATION STUDY - TEST TUTTI GLI AGENT".center(80, "="))
        print(f"Testing {len(AVAILABLE_AGENTS)} agents")
        print(f"Use Case: {self.use_case}")
        print(f"Runs per config: {self.num_runs}")
        print("="*80)
        
        all_results = {}
        
        print("\\n\\n" + "="*80)
        print("BASELINE - Tutti gli agent attivi")
        print("="*80)
        
        baseline_tester = SyntheticEvaluationTest(
            use_case=self.use_case,
            num_immobili=self.num_immobili,
            num_poi=self.num_poi,
            num_runs=self.num_runs,
            ablation_mode=True,
            disabled_agents=set()
        )
        
        if not baseline_tester.run_full_test():
            print("❌ Baseline test fallito")
            return False
        
        all_results["baseline"] = {
            "disabled_agents": [],
            "ranking_metrics": asdict(baseline_tester.ranking_metrics),
            "consistency_metrics": asdict(baseline_tester.consistency_metrics) if baseline_tester.consistency_metrics else None
        }
        
        for agent in AVAILABLE_AGENTS:
            print("\\n\\n" + "="*80)
            print(f"TEST WITHOUT: {agent}")
            print("="*80)
            
            agent_tester = SyntheticEvaluationTest(
                use_case=self.use_case,
                num_immobili=self.num_immobili,
                num_poi=self.num_poi,
                num_runs=self.num_runs,
                ablation_mode=True,
                disabled_agents={agent}
            )
            
            agent_tester.dataset_file = baseline_tester.dataset_file
            agent_tester.ground_truth_path = baseline_tester.ground_truth_path
            agent_tester.df_immobili = baseline_tester.df_immobili
            
            success = agent_tester.step3_evaluate_ranking() and agent_tester.step4_analyze_results()
            
            if success:
                all_results[f"without_{agent}"] = {
                    "disabled_agents": [agent],
                    "ranking_metrics": asdict(agent_tester.ranking_metrics),
                    "consistency_metrics": asdict(agent_tester.consistency_metrics) if agent_tester.consistency_metrics else None
                }
            else:
                print(f"⚠️  Test fallito per {agent}")
        
        self._generate_ablation_report(all_results)
        
        return True
    
    def _generate_ablation_report(self, all_results: Dict):
        """Genera report comparativo ablation study."""
        print("\\n\\n" + "="*80)
        print("📊 ABLATION STUDY - REPORT COMPARATIVO")
        print("="*80)
        
        baseline = all_results.get("baseline")
        if not baseline:
            print("❌ Baseline non trovato")
            return
        
        baseline_recall = baseline["ranking_metrics"]["recall_at_k"]
        baseline_ndcg = baseline["ranking_metrics"]["ndcg_at_k"]
        baseline_latency = baseline["ranking_metrics"]["latency_ms"]
        
        print(f"\\n🎯 Baseline Performance:")
        print(f"   Recall@10: {baseline_recall:.2%}")
        print(f"   NDCG@10:   {baseline_ndcg:.3f}")
        print(f"   Latency:   {baseline_latency:.0f}ms")
        
        if baseline.get("consistency_metrics"):
            baseline_cv = baseline["consistency_metrics"]["coefficient_variation"]
            baseline_jaccard = baseline["consistency_metrics"]["jaccard_similarity_avg"]
            print(f"   CV:        {baseline_cv:.3f}")
            print(f"   Jaccard:   {baseline_jaccard:.3f}")
        
        print(f"\\n🔍 Agent Impact Analysis:\\n")
        
        impact_data = []
        
        for agent in AVAILABLE_AGENTS:
            config_key = f"without_{agent}"
            
            if config_key not in all_results:
                continue
            
            config = all_results[config_key]
            metrics = config["ranking_metrics"]
            
            recall = metrics["recall_at_k"]
            ndcg = metrics["ndcg_at_k"]
            latency = metrics["latency_ms"]
            
            recall_delta = recall - baseline_recall
            ndcg_delta = ndcg - baseline_ndcg
            latency_delta = latency - baseline_latency
            
            if abs(recall_delta) > 0.3 or abs(ndcg_delta) > 0.3:
                criticality = "🔴 CRITICAL"
            elif abs(recall_delta) > 0.15 or abs(ndcg_delta) > 0.15:
                criticality = "🟡 IMPORTANT"
            else:
                criticality = "🟢 OPTIONAL"
            
            impact_data.append({
                "agent": agent,
                "criticality": criticality,
                "recall": recall,
                "recall_delta": recall_delta,
                "ndcg": ndcg,
                "ndcg_delta": ndcg_delta,
                "latency": latency,
                "latency_delta": latency_delta
            })
            
            print(f"{criticality} {agent}")
            print(f"   Recall: {recall:.2%} ({recall_delta:+.2%})")
            print(f"   NDCG:   {ndcg:.3f} ({ndcg_delta:+.3f})")
            print(f"   Latency: {latency:.0f}ms ({latency_delta:+.0f}ms)\\n")
        
        impact_data.sort(key=lambda x: abs(x["recall_delta"]) + abs(x["ndcg_delta"]), reverse=True)
        
        print(f"\\n📈 Agent Ranking by Impact:\\n")
        for i, data in enumerate(impact_data, 1):
            print(f"{i}. {data['agent']}: Recall {data['recall_delta']:+.2%}, NDCG {data['ndcg_delta']:+.3f}")
        
        report_file = self.ablation_dir / f"ablation_report_{self.timestamp}.json"
        report_data = {
            "timestamp": self.timestamp,
            "use_case": self.use_case,
            "baseline": baseline,
            "configurations": all_results,
            "impact_analysis": impact_data
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\\n✓ Report salvato: {report_file}")
