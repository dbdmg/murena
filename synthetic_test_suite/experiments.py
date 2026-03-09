import asyncio
import csv
import json
import itertools
import logging
from contextvars import ContextVar
import os
import sys
import time
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional

import numpy as np
import pandas as pd
from scipy import stats

try:
    import sqlglot
    from sqlglot import exp
    HAS_SQLGLOT = True
except ImportError:
    HAS_SQLGLOT = False

# --- 1. SETTINGS & ENVIRONMENT SETUP ---

current_script_path = Path(__file__).resolve()
suite_path = current_script_path.parent
base_dir = suite_path.parent
backend_dir = base_dir / "backend"
sys.path.append(str(backend_dir))

# Added subfolder for results
results_path = suite_path / "results"
results_path.mkdir(parents=True, exist_ok=True)

# Global execution log
execution_csv_path = results_path / "execution_log.csv"

# Execution ID logic to link all logs to a single test suite execution
is_child = "SYNTHETIC_RUN_ID" in os.environ
RUN_ID = os.environ.get("SYNTHETIC_RUN_ID", f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
os.environ["SYNTHETIC_RUN_ID"] = RUN_ID

# CSV Logging Infrastructure
query_ctx: ContextVar[str] = ContextVar("query_ctx", default="SYSTEM")
experiment_ctx: ContextVar[str] = ContextVar("experiment_ctx", default="N/A")

import io
import csv

def format_csv_line(row: List[Any]) -> str:
    """Helper to generate a properly quoted CSV line."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="")
    writer.writerow(row)
    return output.getvalue()

class CsvLoggingFilter(logging.Filter):
    def filter(self, record):
        record.query_id = query_ctx.get()
        record.experiment_id = experiment_ctx.get()
        return True

class CsvFormatter(logging.Formatter):
    def format(self, record):
        query_id = getattr(record, 'query_id', 'SYSTEM')
        experiment_id = getattr(record, 'experiment_id', 'N/A')
        msg = record.getMessage().strip()
        timestamp = self.formatTime(record, self.datefmt)
        return format_csv_line([timestamp, RUN_ID, experiment_id, query_id, record.levelname, record.name, msg])

def with_query_context(func):
    """Decorator to set query context for async functions."""
    import functools
    @functools.wraps(func)
    async def wrapper(query, *args, **kwargs):
        token = query_ctx.set(query)
        try:
            return await func(query, *args, **kwargs)
        finally:
            query_ctx.reset(token)
    return wrapper

# Clear existing file and write header
if not is_child:
    if execution_csv_path.exists(): execution_csv_path.unlink()
    with open(execution_csv_path, "w", encoding='utf-8') as f:
        f.write(format_csv_line(["timestamp", "run_id", "experiment", "query", "level", "logger", "message"]) + "\n")

def log_output(msg):
    logging.info(msg)

BASELINE_MODEL = "gpt-5.4"
EVALUATION_MODEL = "gpt-5.4"

# Configure standard logging to file with CSV format
handler = logging.FileHandler(str(execution_csv_path), encoding='utf-8')
handler.addFilter(CsvLoggingFilter())
handler.setFormatter(CsvFormatter(datefmt='%Y-%m-%d %H:%M:%S'))
logging.root.addHandler(handler)
logging.root.setLevel(logging.INFO)

# Model-specific concurrency limits to prevent quota issues (429)
# Models not listed here will use the global --max-concurrent value.
MODEL_CONCURRENCY_LIMITS = {
    "gpt-5.4": 5,
    "gpt-5-nano": 5,
    "gpt-oss-120b": 48,
    "ollama-gemma3-27b": 48,
    "ollama-deepseek-r1-8b": 48,
}

def get_model_concurrency(model_name: str, default_val: int) -> int:
    """Returns the specific limit for a model if defined, else the global default."""
    return MODEL_CONCURRENCY_LIMITS.get(model_name, default_val)

from app.core.config import settings
from app.services.analysis_service import analysis_service
from app.services.real_estate_service import RealEstateService
from app.data.loaders import load_and_merge_data
from app.utils.json_parser import safe_extract_json
from tests.model_config import apply_model_config

# Patch settings
for attr in ["DATASET_FULL", "APE_DETAILED_DATA_PATH", "STATIC_DIR", "DATA_DIR", "APE_DIR", "META_DIR", "AGENT_LOGS_DIR"]:
    val = getattr(settings, attr, None)
    if val and isinstance(val, str) and not os.path.isabs(val):
        setattr(settings, attr, str(backend_dir / val))

try:
    from loguru import logger
    # Brute force removal of all existing handlers to prevent conflicts
    logger.remove()
    
    def loguru_csv_format(record):
        # Escape curly braces in message to prevent Loguru's internal formatters from re-evaluating them
        msg = record["message"].strip().replace("{", "{{").replace("}", "}}")
        q_id = query_ctx.get()
        e_id = experiment_ctx.get()
        timestamp = record["time"].strftime('%Y-%m-%d %H:%M:%S')
        lvl = record["level"].name
        name = record["name"]
        return format_csv_line([timestamp, RUN_ID, e_id, q_id, lvl, name, msg]) + "\n"
    
    logger.add(str(execution_csv_path), level="INFO", format=loguru_csv_format, encoding='utf-8')
except ImportError:
    pass

# --- 2. ANALYTICS UTILS ---

async def preload_data():
    dataset_path = Path(settings.DATASET_FULL)
    if dataset_path.exists():
        df = load_and_merge_data(str(dataset_path))
        RealEstateService._dataset_cache["full"] = df
        analysis_service._base_dataset_cache["full"] = df
    return True

def get_data_stats():
    df = RealEstateService._dataset_cache.get("full")
    if df is None: return {}
    num_cols = df.select_dtypes(include=[np.number]).columns
    return {col.upper(): {"min": float(df[col].min()), "max": float(df[col].max())} for col in num_cols}

def calculate_iou(ids_a, ids_b):
    set_a, set_b = set(ids_a), set(ids_b)
    if not set_a and not set_b: return 1.0
    u = len(set_a.union(set_b))
    return len(set_a.intersection(set_b)) / u if u > 0 else 0.0

def extract_sql_conditions(sql: str) -> Set[str]:
    if not sql: return set()
    if HAS_SQLGLOT:
        try:
            parsed = sqlglot.parse_one(sql)
            where = parsed.find(exp.Where)
            if where:
                predicates = []
                def walk(node):
                    if isinstance(node, (exp.And, exp.Or)):
                        for arg in node.args.values():
                            if arg: walk(arg)
                    elif isinstance(node, (exp.Binary, exp.In, exp.Between)):
                        predicates.append(node.sql().upper())
                walk(where.this)
                if predicates: return set(predicates)
        except: pass
    return set()

def calculate_sql_iou(sql_a, sql_b):
    cond_a, cond_b = extract_sql_conditions(sql_a), extract_sql_conditions(sql_b)
    if not cond_a and not cond_b: return 1.0
    u = len(cond_a.union(cond_b))
    return len(cond_a.intersection(cond_b)) / u if u > 0 else 0.0

def check_sql_ood(sql, data_stats):
    if not sql or not HAS_SQLGLOT: return []
    ood = []
    try:
        parsed = sqlglot.parse_one(sql)
        for condition in parsed.find_all(exp.Binary):
            col = condition.left.name.upper() if isinstance(condition.left, exp.Column) else None
            try:
                val = float(condition.right.this) if isinstance(condition.right, exp.Literal) and condition.right.is_number else None
                if col in data_stats and val is not None:
                    if val < data_stats[col]["min"] or val > data_stats[col]["max"]:
                        ood.append(f"{col}({val})")
            except: pass
    except: pass
    return ood

# --- 3. EXECUTION DISPATCHERS ---

@with_query_context
async def run_query(query, architecture="multiagent", disabled=None, use_knowledge=True):
    log_output(f"[QUERY] Searching: {query}")
    try:
        agent = analysis_service._init_graph_agent()
        agent.architecture = architecture
        start_t = time.time()
        res = await analysis_service.run_analysis(
            run_id=f"test_{datetime.now().strftime('%H%M%S')}",
            query=query, dataset_key="full", map_limit=15000, llm_limit=25,
            analysis_mode="agent", disabled_agents=disabled, use_data_knowledge=use_knowledge,
            allow_relaxation=False
        )
        duration = round((time.time() - start_t) * 1000, 2)
        buildings = res.get("buildings", [])
        buildings_dicts = [b.model_dump() if hasattr(b, "model_dump") else b for b in buildings]
        ranking = [{"id": str(b.get("id")), "score": float(round(b.get("score", 0.0), 1))} for b in buildings_dicts[:10]]
        trace = res.get("agent_trace", [])
        ranking_data = next((safe_extract_json(t.get("output")) if isinstance(t.get("output"), str) else t.get("output") for t in trace if "ranking" in t.get("agent_name", "").lower()), {})
        
        # Calculate effective weights based only on agents that actually contributed (ran in ranking mode)
        eff_weights = {}
        if ranking_data:
            init_w = ranking_data.get("weights", {})
            # A contributing agent is one that produced a ranking output in the trace
            contributing_agent_keys = {
                t.get("agent_name", "").split("-")[0] 
                for t in trace 
                if t.get("agent_mode") == "ranking" and "-" in t.get("agent_name", "")
            }
            # Only keep valid agent keys that had a non-zero initial weight
            active_f = [a for a in contributing_agent_keys if a in init_w and init_w[a] > 0]
            s_w = sum(init_w.get(a, 0) for a in active_f)
            if s_w > 0:
                eff_weights = {a: round(init_w[a]/s_w, 2) for a in active_f}
        
        # Extract evaluations from gemini_responses (more reliable than trace for final results)
        evaluations = res.get("gemini_responses", {}).get("evaluation", {}).get("results", [])
        
        # Get full data for the first evaluated building for verification (Internal use only, not saved)
        building_info = {}
        if evaluations and res.get("buildings"):
            top_id = evaluations[0].get("id")
            for b_dict in buildings_dicts:
                if str(b_dict.get("id")) == top_id:
                    building_info = b_dict
                    break

        results_pack = {
            "query": query, 
            "results_count": res.get("results_count", 0),
            "execution_time_ms": duration, 
            "final_sql": res.get("filters_applied", {}).get("final_sql", ""),
            "ranking": ranking, 
            "ranking_logic": {"effective_weights": eff_weights},
            "evaluations": evaluations
        }
        
        final_sql = res.get("filters_applied", {}).get("final_sql", "")
        log_output(f"  -> Found {res.get('results_count', 0)} buildings in {duration}ms")
        if final_sql: log_output(f"  -> SQL: {final_sql[:100]}...")
        
        return results_pack
    except Exception as e: 
        log_output(f"  [!] Error: {str(e)}")
        return {"error": str(e)}

async def process_batch(indices, df, out_dir, sem, arch="multiagent", disabled=None, use_knowledge=True, lock=None, csv_path=None, col=None, trial=None, batch_name=""):
    """Process a batch of queries with real-time progress updates and caching."""
    total = len(indices)
    completed = 0
    tasks = []
    
    suffix = f"_tr{trial}" if trial else ""

    for idx in indices:
        async def task(i=idx):
            nonlocal completed
            query = df.at[i, "query"]
            filename = f"query_{i+1:03d}{suffix}.json"
            target_path = out_dir / filename

            # Set context vars immediately so every log within this task
            # (and any asyncio subtask created by run_analysis) inherits the
            # correct query/experiment identifiers from the very start.
            q_token = query_ctx.set(query)
            e_token = experiment_ctx.set(batch_name)
            try:
                # Cache check
                if target_path.exists():
                    if lock and col and df.at[i, col] == 0:
                        async with lock:
                            df.at[i, col] = 1
                    completed += 1
                    return

                async with sem:
                    res = await run_query(query, architecture=arch, disabled=disabled, use_knowledge=use_knowledge)
                    completed += 1
                    status = "OK" if "error" not in res else "ERR"

                    if "error" not in res:
                        with open(target_path, "w") as f: json.dump(res, f, indent=4)
                        if lock and col:
                            async with lock:
                                df.at[i, col] = 1
                    elif lock and col:
                        async with lock:
                            df.at[i, col] = 2  # Error status

                    if lock and csv_path:
                        async with lock: df.to_csv(csv_path, index=False)

                    if total > 0:
                        log_output(f"[{batch_name}] Progress: {completed}/{total} ({status})")
            finally:
                query_ctx.reset(q_token)
                experiment_ctx.reset(e_token)

        tasks.append(task())
    await asyncio.gather(*tasks)

# --- 4. ANALYTICS ENGINES ---

def analyze_activation(results_dir, mapping, model_name):
    agents = sorted(list(set(mapping.values())))
    metrics = {a: {"tp": 0, "fp": 0, "fn": 0} for a in agents}
    total_j, perfect = 0.0, 0
    files = list(results_dir.glob("*.json"))
    for f in files:
        with open(f) as jf:
            data = json.load(jf)
            query = data.get("query", "").lower()
            actual = {a for a, w in data.get("ranking_logic", {}).get("effective_weights", {}).items() if w > 0}
            expected = {a for k, a in mapping.items() if k.lower() in query}
            for a in agents:
                is_ex, is_ac = a in expected, a in actual
                if is_ex and is_ac: metrics[a]["tp"] += 1
                elif not is_ex and is_ac: metrics[a]["fp"] += 1
                elif is_ex and not is_ac: metrics[a]["fn"] += 1
            if actual == expected: perfect += 1
            u = expected.union(actual)
            total_j += (len(expected.intersection(actual))/len(u) if u else 1.0)
    
    summary = {"model": model_name, "perfect_rate": round(perfect/len(files), 3) if files else 0, "mean_jaccard": round(total_j/len(files), 3) if files else 0, "mismatches": len(files)-perfect}
    agent_metrics = {a: {"precision": round(m["tp"]/(m["tp"]+m["fp"]), 3) if (m["tp"]+m["fp"])>0 else 0, "recall": round(m["tp"]/(m["tp"]+m["fn"]), 3) if (m["tp"]+m["fn"])>0 else 0} for a, m in metrics.items()}
    for a in agent_metrics: agent_metrics[a]["f1"] = round(2*agent_metrics[a]["precision"]*agent_metrics[a]["recall"]/(agent_metrics[a]["precision"]+agent_metrics[a]["recall"]) if (agent_metrics[a]["precision"]+agent_metrics[a]["recall"])>0 else 0, 3)
    return {"summary": summary, "agent_metrics": agent_metrics}

def analyze_iou_stats(results_dir):
    ids_list = []
    total, analyzed = 0, 0
    for f in sorted(results_dir.glob("*.json")):
        total += 1
        with open(f) as jf:
            data = json.load(jf)
            ids_list.append([str(i["id"]) for i in data.get("ranking", [])])
            analyzed += 1
    if not ids_list: return {"zero_iou": "0.0%", "analyzed_rate": "0.0%"}
    ious = [calculate_iou(ids_list[i], ids_list[j]) for i in range(len(ids_list)) for j in range(i+1, len(ids_list))]
    return {"zero_iou": f"{np.mean(np.array(ious) == 0)*100:.2f}%" if ious else "100.0%", "analyzed_rate": f"{analyzed/total*100:.2f}%"}

def analyze_architecture_comparison(agent_dir, baseline_dir):
    sql_ious, ranking_ious = [], []
    agent_files = {f.name: f for f in agent_dir.glob("query_*.json") if "_tr" not in f.name}
    baseline_files = {f.name: f for f in baseline_dir.glob("query_*.json")}
    for name, f_a in agent_files.items():
        if name in baseline_files:
            with open(f_a) as fa, open(baseline_files[name]) as fb:
                da, db = json.load(fa), json.load(fb)
                sql_ious.append(calculate_sql_iou(da.get("final_sql", ""), db.get("final_sql", "")))
                ranking_ious.append(calculate_iou([str(r['id']) for r in da.get('ranking', [])], [str(r['id']) for r in db.get('ranking', [])]))
    return {"mean_sql_iou": round(np.mean(sql_ious), 3) if sql_ious else 0, "mean_ranking_iou": round(np.mean(ranking_ious), 3) if ranking_ious else 0, "sample_size": len(sql_ious)}

def analyze_ranking_impact(multiagent_dir, no_ranking_dir):
    ious = []
    ma_files = {f.name: f for f in multiagent_dir.glob("query_*.json") if "_tr" not in f.name}
    nr_files = {f.name: f for f in no_ranking_dir.glob("query_*.json")}
    for name, f_ma in ma_files.items():
        if name in nr_files:
            with open(f_ma) as fa, open(nr_files[name]) as fb:
                da, db = json.load(fa), json.load(fb)
                ious.append(calculate_iou([str(r['id']) for r in da.get('ranking', [])], [str(r['id']) for r in db.get('ranking', [])]))
    return {"mean_iou": round(np.mean(ious), 3) if ious else 1.0, "impact": round(1.0 - np.mean(ious), 3) if ious else 0.0}

def analyze_knowledge_impact(multiagent_dir, no_knowledge_dir, data_stats):
    ious, ood_w, ood_wo, total = [], 0, 0, 0
    ma_files = {f.name: f for f in multiagent_dir.glob("query_*.json") if "_tr" not in f.name}
    nk_files = {f.name: f for f in no_knowledge_dir.glob("query_*.json")}
    for name, f_ma in ma_files.items():
        if name in nk_files:
            total += 1
            with open(f_ma) as fa, open(nk_files[name]) as fb:
                da, db = json.load(fa), json.load(fb)
                ious.append(calculate_iou([str(r['id']) for r in da.get('ranking', [])], [str(r['id']) for r in db.get('ranking', [])]))
                if check_sql_ood(da.get("final_sql", ""), data_stats): ood_w += 1
                if check_sql_ood(db.get("final_sql", ""), data_stats): ood_wo += 1
    return {"mean_ranking_iou": round(np.mean(ious), 3) if ious else 1.0, "ood_rate_with": round(ood_w/total, 3) if total else 0, "ood_rate_without": round(ood_wo/total, 3) if total else 0}

def analyze_consistency(consistency_dir):
    trial_ious = {}
    for f in consistency_dir.glob("query_*_tr*.json"):
        q_idx = f.name.split("_")[1]
        if q_idx not in trial_ious: trial_ious[q_idx] = []
        with open(f) as jf: trial_ious[q_idx].append([str(r['id']) for r in json.load(jf).get('ranking', [])])
    
    avg_ious = []
    for q_idx, rankings in trial_ious.items():
        if len(rankings) < 2: continue
        avg_ious.append(np.mean([calculate_iou(rankings[i], rankings[j]) for i in range(len(rankings)) for j in range(i+1, len(rankings))]))
    return {"mean_self_iou": round(np.mean(avg_ious), 3) if avg_ious else 1.0}

async def evaluate_with_judge(model_key, results_dir):
    """LLM-as-a-judge to evaluate pros/cons quality."""
    from app.services.llm.langchain_client import get_llm
    
    # Configure settings for the judge model
    apply_model_config(settings, EVALUATION_MODEL)
    judge_llm = get_llm() # Uses configured EVALUATION_MODEL
    
    samples = []
    for f in list(results_dir.glob("*.json"))[:5]: 
        with open(f) as jf:
            data = json.load(jf)
            if data.get("evaluations"):
                samples.append({
                    "query": data["query"], 
                    "evaluation": data["evaluations"][0],
                    "building": data.get("evaluated_building_data", {})
                })
    
    if not samples: return {"score": 0, "samples": 0}
    
    scores = []
    for s in samples:
        query = s["query"]
        ev = s["evaluation"]
        b = s["building"]
        
        prompt = f"""
        Valuta se i PRO e CONTRO generati dall'AI sono FACT-BASED (basati sui dati reali) e rilevanti per la query.
        
        QUERY UTENTE: {query}
        
        DATI ORIGINALI IMMOBILE (Verità):
        {json.dumps(b, indent=2, ensure_ascii=False)}
        
        PRO GENERATI: {ev.get('pros')}
        CONTRO GENERATI: {ev.get('cons')}
        TESTO ANALISI: {ev.get('evaluation_text')}
        
        COMPITI:
        1. Accuracy: I punti citati esistono davvero nei dati? (es. se dice 'vicino al verde', la colonna 'verde' ha uno score alto?)
        2. Relevance: I punti sono importanti per quello che ha chiesto l'utente?
        
        Assegna un punteggio da 1 a 5. Restituisci SOLO un JSON: {{"score": float}}
        """
        try:
            res = await judge_llm.ainvoke(prompt)
            score_data = safe_extract_json(res.content if hasattr(res, 'content') else res)
            if score_data and "score" in score_data:
                scores.append(float(score_data["score"]))
        except: pass
        
    # Restore original model settings
    apply_model_config(settings, model_key)
    return {"score": round(np.mean(scores), 2) if scores else 0, "samples": len(scores)}

def analyze_correlation(results_dir):
    data = []
    for f in results_dir.glob("*.json"):
        with open(f) as jf:
            res = json.load(jf)
            orig, eff = res.get('ranking_logic', {}).get('original_weights', {}), res.get('ranking_logic', {}).get('effective_weights', {})
            ranks = {a: i + 1 for i, (a, _) in enumerate(sorted(orig.items(), key=lambda x: x[1], reverse=True))}
            for a, w in orig.items(): data.append({'rank': ranks.get(a), 'is_effective': 1 if eff.get(a, 0) > 0 else 0, 'agent': a})
    if not data: return {}
    df = pd.DataFrame(data)
    rho, pval = stats.spearmanr(df['rank'], df['is_effective'])
    return {"spearman": {"rho": round(rho, 4), "p_value": float(pval)}, "rank_effectiveness": df.groupby('rank')['is_effective'].mean().to_dict(), "agent_effectiveness": df.groupby('agent')['is_effective'].agg(['sum', 'mean']).reset_index().to_dict(orient='records')}

# --- 5. REPORT GENERATOR ---

def generate_report(bench, sens, models, progress=None):
    """Generate markdown report with optional live progress dashboard."""
    report_md = f"# Comprehensive Analysis Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    
    if progress:
        report_md += "## 📡 Live Execution Dashboard\n"
        dashboard = "| Model | Phase 1 (Bench) | Phase 2 (Sens) | Active Task |\n| :--- | :---: | :---: | :--- |\n"
        for m, p in progress.items():
            dashboard += f"| **{m}** | {p['benchmark']} | {p['sensitivity']} | `{p['current_task']}` |\n"
        report_md += dashboard + "\n---\n"

    completed = [m for m in models if m in bench and "activation" in bench[m]]
    if not completed: 
        return report_md + "\n*Waiting for the first model to complete Phase 1 analysis...*\n"

    global_perf = "\n### Global Performance\n| Model | Perfect Rate | Mean Jaccard | Mismatches |\n| :--- | :---: | :---: | :---: |\n"
    agent_perf = "\n### Agent Performance\n| Agent | Model | Precision | Recall | F1 |\n| :--- | :--- | :---: | :---: | :---: |\n"
    arch_perf = "\n### Architecture Comparison\n| Model | SQL IoU | Ranking IoU | Baseline |\n| :--- | :---: | :---: | :--- |\n"
    impact_perf = "| Model | Ranking Impact (1-IoU) | Knowledge (OOD w/o stats) | Consistency | Eval Quality (Judge) |\n| :--- | :---: | :---: | :---: | :---: |\n"
    sensitivity_md = ""

    for mod in completed:
        s = bench[mod]["activation"]["summary"]
        global_perf += f"| {mod} | {s['perfect_rate']:.3f} | {s['mean_jaccard']:.3f} | {s['mismatches']} |\n"
        for ag, met in bench[mod]["activation"]["agent_metrics"].items():
            agent_perf += f"| {ag} | {mod} | {met['precision']:.3f} | {met['recall']:.3f} | {met['f1']:.3f} |\n"
        
        ac = bench[mod]["arch_comp"]
        arch_perf += f"| {mod} | {ac['mean_sql_iou']:.3f} | {ac['mean_ranking_iou']:.3f} | {ac.get('baseline_model', 'Self')} |\n"
        
        ri = bench[mod].get("ranking_impact", {})
        ki = bench[mod].get("knowledge_impact", {})
        co = bench[mod].get("consistency", {})
        eq = bench[mod].get("eval_quality", {})
        impact_perf += f"| {mod} | {ri.get('impact', 0):.3f} | {ki.get('ood_rate_without', 0)*100:.1f}% | {co.get('mean_self_iou', 0):.3f} | {eq.get('score', 0)}/5 |\n"

    comp_sens = [m for m in completed if m in sens]
    if comp_sens:
        sensitivity_md = "\n### Sensitivity Analysis (1 - IoU)\n| Agent | " + " | ".join(comp_sens) + " |\n| :--- |" + " :---: |" * len(comp_sens) + "\n"
        agents_map = {"no_location": "Location", "no_poi": "Proximity", "no_property_technical": "Building", "no_ape": "Energy", "no_normative": "Regulatory"}
        for k, display in agents_map.items():
            sensitivity_md += f"| {display} | " + " | ".join([f"{sens[m]['sensitivity'].get(k, 0):.3f}" for m in comp_sens]) + " |\n"

    return f"""# Comprehensive Analysis Report ({datetime.now().strftime('%H:%M:%S')})

## 1. Routing & Activation
{global_perf}
{agent_perf}

## 2. Structural & Impact Benchmarks
{arch_perf}
{impact_perf}

## 3. Component Sensitivity
{sensitivity_md}
"""

# --- 6. MAIN WORKFLOW ---

def generate_compositions(json_path, output_path, ablation=False):
    with open(json_path) as f: data = json.load(f)
    keys = ["tipologia_immobile", "punto_di_interesse", "metratura_totale", "classe_energetica", "progetto_destinazione_uso", "servizi_accessori"]
    opts = [data[k] if (k=="tipologia_immobile" or ablation) else data[k]+[None] for k in keys]
    queries = []
    for c in itertools.product(*opts):
        t, p, m, cl, pr, s = c
        q = f"Cerca un {t}"
        if p: q += f" vicino a {p}"
        if m: q += f" con superficie {m}"
        if cl: q += f" in classe {cl}"
        if pr: q += f", finalizzato a {pr}"
        if s: q += f" e situato vicino a {s}"
        queries.append(q)
    queries.sort(key=len)
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        if ablation:
            writer.writerow(['query', 'status_all_enabled', 'status_no_ranking', 'status_no_knowledge', 'status_no_poi', 'status_no_normative', 'status_no_location', 'status_no_ape', 'status_no_property_technical'])
            for q in queries: writer.writerow([q] + [0]*8)
        else:
            writer.writerow(['query', 'status'])
            for q in queries: writer.writerow([q, 0])


async def compute_consensus_results(model: str, df: pd.DataFrame, out_root: Path):
    """Determine the most frequent result among trials and populate the 'full' config directory."""
    cons_dir = out_root / "consistency"
    full_dir = out_root / "full"
    full_dir.mkdir(parents=True, exist_ok=True)
    
    log_output(f"[*] Computing consensus for {model}...")
    
    for i in range(len(df)):
        results = []
        for tr in [1, 2, 3]:
            tr_file = cons_dir / f"query_{i+1:03d}_tr{tr}.json"
            if tr_file.exists():
                with open(tr_file) as f: results.append(json.load(f))
        
        if not results: continue

        # Simple consensus: Compare ranking IDs
        def get_rank_sig(res):
            return tuple(r.get("id") for r in res.get("ranking", []))
        
        signatures = [get_rank_sig(r) for r in results]
        # Find most frequent signature
        most_common_sig = max(set(signatures), key=signatures.count)
        
        # Pick the first result that matches the most common signature
        winner = next(r for r in results if get_rank_sig(r) == most_common_sig)
        
        target_file = full_dir / f"query_{i+1:03d}.json"
        with open(target_file, "w") as f:
            json.dump(winner, f, indent=4)

async def sync_sensitivity_with_benchmark(df_sens: pd.DataFrame, df_bench: pd.DataFrame, model_key: str):
    """Reuse benchmark results for sensitivity common configurations to avoid re-runs."""
    # Maps query text to benchmark index
    query_to_bench_idx = {row['query']: i for i, row in df_bench.iterrows()}
    
    configurations_to_sync = [
        ("all_enabled", "full"),
        ("no_ranking", "no_ranking"),
        ("no_knowledge", "no_knowledge")
    ]
    
    bench_root = results_path / "outputs" / "benchmarks" / model_key
    sens_root = results_path / "outputs" / "sensitivity" / model_key
    
    for sens_cid, bench_cid in configurations_to_sync:
        sens_col = f"status_{model_key.replace('-', '_')}_{sens_cid}"
        bench_col = f"status_{model_key.replace('-', '_')}_{bench_cid}"
        
        if bench_col not in df_bench.columns: continue
        if sens_col not in df_sens.columns: df_sens[sens_col] = 0
        
        bench_dir = bench_root / bench_cid
        sens_dir = sens_root / sens_cid
        sens_dir.mkdir(parents=True, exist_ok=True)
        
        for i, row in df_sens.iterrows():
            query = row['query']
            if query in query_to_bench_idx:
                b_idx = query_to_bench_idx[query]
                # Check if benchmark is done
                if df_bench.at[b_idx, bench_col] == 1:
                    bench_file = bench_dir / f"query_{b_idx+1:03d}.json"
                    sens_file = sens_dir / f"query_{i+1:03d}.json"
                    if bench_file.exists() and not sens_file.exists():
                        # Symbolic link or copy. Copy is safer for portability.
                        import shutil
                        shutil.copy(bench_file, sens_file)
                    if sens_file.exists():
                        df_sens.at[i, sens_col] = 1

async def run_single_model_suite(model: str, max_concurrent: int):
    """Execution logic for a single model with optimized non-redundant workflow."""
    # Initialize environment
    pos_json = suite_path / "query_variables_possibilities.json"
    mapping_json = suite_path / "agent_mapping.json"
    with open(mapping_json) as f: mapping = json.load(f)
    
    await preload_data()
    data_stats = get_data_stats()
    sem = asyncio.Semaphore(max_concurrent)
    csv_lock = asyncio.Lock()

    log_output(f"\n" + "="*50)
    log_output(f"=== [START] MODEL: {model} ===")
    log_output(f"="*50)
    
    bench_csv = results_path / "combinatorial_queries_suite.csv"
    sens_csv = results_path / "sensitivity_queries_suite.csv"
    if not bench_csv.exists(): generate_compositions(pos_json, bench_csv)
    if not sens_csv.exists(): generate_compositions(pos_json, sens_csv, ablation=True)

    df_bench = pd.read_csv(bench_csv)
    df_sens = pd.read_csv(sens_csv)

    apply_model_config(settings, model)
    out_root_bench = results_path / "outputs" / "benchmarks" / model
    out_root_sens = results_path / "outputs" / "sensitivity" / model

    # --- PHASE 1: BENCHMARK BASICS & CONSISTENCY ---
    log_output("[*] Phase 1: Running Baseline, Core Ablations and Consistency Trials...")
    tasks = []

    # 1. Baseline
    if BASELINE_MODEL == model:
        col = f"status_{model.replace('-', '_')}_baseline"
        if col not in df_bench.columns: df_bench[col] = 0
        # Retry both never run (0) and previously failed (2) queries
        pending = df_bench[df_bench[col].isin([0, 2])].index.tolist()
        if pending:
            tasks.append(process_batch(pending, df_bench, out_root_bench / "baseline", sem, arch="baseline", lock=csv_lock, csv_path=bench_csv, col=col, batch_name=f"{model}-BASELINE"))

    # 2. Core Configs (Ablations only, 'full' will be driven by consensus)
    configs = {"no_ranking": (["ranking"], True), "no_knowledge": (None, False)}
    for cid, (dis, kn) in configs.items():
        out_dir = out_root_bench / cid
        out_dir.mkdir(parents=True, exist_ok=True)
        col = f"status_{model.replace('-', '_')}_{cid}"
        if col not in df_bench.columns: df_bench[col] = 0
        # Retry both never run (0) and previously failed (2) queries
        pending = df_bench[df_bench[col].isin([0, 2])].index.tolist()
        if pending:
            tasks.append(process_batch(pending, df_bench, out_dir, sem, disabled=dis, use_knowledge=kn, lock=csv_lock, csv_path=bench_csv, col=col, batch_name=f"{model}-{cid.upper()}"))

    # 3. Consistency Trials (Used to populate 'full')
    for tr in [1, 2, 3]:
        out_dir = out_root_bench / "consistency"
        out_dir.mkdir(parents=True, exist_ok=True)
        col = f"status_{model.replace('-', '_')}_consistency_tr{tr}"
        if col not in df_bench.columns: df_bench[col] = 0
        # Retry both never run (0) and previously failed (2) queries
        pending = df_bench[df_bench[col].isin([0, 2])].index.tolist()
        if pending:
            tasks.append(process_batch(pending, df_bench, out_dir, sem, lock=csv_lock, csv_path=bench_csv, col=col, trial=tr, batch_name=f"{model}-CONS-TR{tr}"))

    if tasks:
        await asyncio.gather(*tasks)

    # --- PHASE 2: CONSENSUS & SYNC ---
    # Determine the 'full' configuration result from the consensus of trials
    await compute_consensus_results(model, df_bench, out_root_bench)
    # Update status_full based on whether files were created
    full_col = f"status_{model.replace('-', '_')}_full"
    if full_col not in df_bench.columns: df_bench[full_col] = 0
    full_dir = out_root_bench / "full"
    for i in range(len(df_bench)):
        if (full_dir / f"query_{str(i).zfill(3)}.json").exists():
            df_bench.at[i, full_col] = 1
    df_bench.to_csv(bench_csv, index=False)

    # Sync sensitivity with benchmark counterparts
    await sync_sensitivity_with_benchmark(df_sens, df_bench, model)
    df_sens.to_csv(sens_csv, index=False)

    # --- PHASE 3: SENSITIVITY ABLATIONS ---
    log_output("[*] Phase 3: Running remaining sensitivity ablations...")
    tasks = []
    # Note: all_enabled, no_ranking, no_knowledge were already synced
    sens_configs = [
        ("no_poi", ["poi"], True), 
        ("no_normative", ["normative"], True), 
        ("no_location", ["location"], True), 
        ("no_ape", ["ape"], True), 
        ("no_property_technical", ["property_technical"], True)
    ]
    
    for cid, dis, kn in sens_configs:
        col = f"status_{model.replace('-', '_')}_{cid}"
        if col not in df_sens.columns: df_sens[col] = 0
        out_dir = out_root_sens / cid
        out_dir.mkdir(parents=True, exist_ok=True)
        # Retry both never run (0) and previously failed (2) queries
        pending = df_sens[df_sens[col].isin([0, 2])].index.tolist()
        if pending:
            tasks.append(process_batch(pending, df_sens, out_dir, sem, disabled=dis, use_knowledge=kn, lock=csv_lock, csv_path=sens_csv, col=col, batch_name=f"{model}-SENS-{cid.upper()}"))

    if tasks:
        await asyncio.gather(*tasks)
    
    log_output(f"=== [COMPLETE] Queries for {model} finished. ===")

async def conductor_main(max_concurrent: int, only_analysis: bool = False):
    """Main orchestrator that manages model processes and generates final reports."""
    pos_json = suite_path / "query_variables_possibilities.json"
    mapping_json = suite_path / "agent_mapping.json"
    with open(mapping_json) as f: mapping = json.load(f)
    await preload_data()
    data_stats = get_data_stats()

    models = ["gpt-5-nano", "gpt-oss-120b", "ollama-gemma3-27b", "ollama-deepseek-r1-8b"]
    
    # 1. PREPARE SUITES
    if not only_analysis:
        bench_csv = results_path / "combinatorial_queries_suite.csv"
        if not bench_csv.exists(): generate_compositions(pos_json, bench_csv)
        sens_csv = results_path / "sensitivity_queries_suite.csv"
        if not sens_csv.exists(): generate_compositions(pos_json, sens_csv, ablation=True)

        # 2. RUN BASELINE FIRST (if it exists in the list)
        if BASELINE_MODEL in models:
            m_concurrency = get_model_concurrency(BASELINE_MODEL, max_concurrent)
            log_output(f"[CONDUCTOR] Ensuring baseline '{BASELINE_MODEL}' is ready (max_concurrent={m_concurrency})...")
            proc = await asyncio.create_subprocess_exec(sys.executable, __file__, "--model", BASELINE_MODEL, "--max-concurrent", str(m_concurrency))
            await proc.wait()
            models_to_run = [m for m in models if m != BASELINE_MODEL]
        else:
            models_to_run = models

        # 3. RUN OTHER MODELS IN PARALLEL
        log_output(f"[CONDUCTOR] Launching {len(models_to_run)} model benchmark processes...")
        processes = []
        for m in models_to_run:
            m_concurrency = get_model_concurrency(m, max_concurrent)
            log_output(f"[CONDUCTOR] -> Starting {m} (max_concurrent={m_concurrency})")
            p = await asyncio.create_subprocess_exec(sys.executable, __file__, "--model", m, "--max-concurrent", str(m_concurrency))
            processes.append(p)
        
        await asyncio.gather(*(p.wait() for p in processes))

    # 4. AGGREGATE ANALYSIS & GENERATE REPORT
    log_output("[CONDUCTOR] All processes finished. Running final analysis...")
    
    benchmark_results = {}
    sensitivity_results = {}

    for model in models:
        out_root = results_path / "outputs" / "benchmarks" / model
        out_sens = results_path / "outputs" / "sensitivity" / model
        
        if not (out_root / "full").exists():
            log_output(f"[!] Warning: No results found for {model}. Skipping analysis.")
            continue

        # Run model-specific analysis
        log_output(f"[*] Analyzing results for {model}...")
        
        # Benchmark Analysis
        benchmark_results[model] = {
            "activation": analyze_activation(out_root / "full", mapping, model),
            "iou": analyze_iou_stats(out_root / "full"),
            "arch_comp": analyze_architecture_comparison(out_root / "full", results_path / "outputs" / "benchmarks" / (BASELINE_MODEL or model) / "baseline"),
            "ranking_impact": analyze_ranking_impact(out_root / "full", out_root / "no_ranking"),
            "knowledge_impact": analyze_knowledge_impact(out_root / "full", out_root / "no_knowledge", data_stats),
            "consistency": analyze_consistency(out_root / "consistency"),
            "eval_quality": await evaluate_with_judge(model, out_root / "full")
        }
        benchmark_results[model]["arch_comp"]["baseline_model"] = BASELINE_MODEL or model

        # Sensitivity Analysis
        sens_configs = ["no_ranking", "no_knowledge", "no_poi", "no_normative", "no_location", "no_ape", "no_property_technical"]
        sens_vals = {}
        all_enabled_dir = out_sens / "all_enabled"
        if all_enabled_dir.exists():
            base_ref = {f.name: [r['id'] for r in json.load(open(f))['ranking']] for f in all_enabled_dir.glob("*.json")}
            for cid in sens_configs:
                cfg_dir = out_sens / cid
                if cfg_dir.exists():
                    cfg_res = {f.name: [r['id'] for r in json.load(open(f))['ranking']] for f in cfg_dir.glob("*.json")}
                    ious = [calculate_iou(base_ref[n], cfg_res[n]) for n in cfg_res if n in base_ref]
                    sens_vals[cid] = 1.0 - np.mean(ious) if ious else 0
        
        sensitivity_results[model] = {"sensitivity": sens_vals}

    # Final report
    report = generate_report(benchmark_results, sensitivity_results, models)
    with open(results_path / "report.md", "w") as f:
        f.write(report)
    
    log_output(f"\nWorkflow complete. Final report: {results_path / 'report.md'}")
    log_output(f"Detailed execution log: {execution_csv_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Test Suite - Parallel Runner")
    parser.add_argument("--model", type=str, help="Run only a specific model")
    parser.add_argument("--only-analysis", action="store_true", help="Only run analysis on existing results")
    parser.add_argument("--max-concurrent", type=int, default=48, help="Max concurrent queries per model")
    args = parser.parse_args()

    if args.model:
        # Use model-specific concurrency if the user didn't explicitly override it from CLI
        # (Assuming 48 is the default to detect 'unspecified' state)
        m_concurrency = args.max_concurrent
        if m_concurrency == 48:
            m_concurrency = get_model_concurrency(args.model, 48)
            
        # Run a single model suite (to be called as a subprocess or manually)
        asyncio.run(run_single_model_suite(args.model, m_concurrency))
    else:
        # Launch the conductor
        asyncio.run(conductor_main(args.max_concurrent, args.only_analysis))
