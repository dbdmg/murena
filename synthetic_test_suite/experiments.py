import asyncio
import csv
import json
import itertools
import logging
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

logging.basicConfig(level=logging.ERROR)
base_dir = Path("/Users/marcodeluca/Downloads/real-estate-ai")
backend_dir = base_dir / "backend"
sys.path.append(str(backend_dir))

from app.core.config import settings
from app.services.analysis_service import analysis_service
from app.services.real_estate_service import RealEstateService
from app.data.loaders import load_and_merge_data
from app.utils.json_parser import safe_extract_json

# Patch settings
for attr in ["DATASET_FULL", "APE_DETAILED_DATA_PATH", "STATIC_DIR", "DATA_DIR", "APE_DIR", "META_DIR", "AGENT_LOGS_DIR"]:
    val = getattr(settings, attr, None)
    if val and isinstance(val, str) and not os.path.isabs(val):
        setattr(settings, attr, str(backend_dir / val))

try:
    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
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

async def run_query(query, architecture="multiagent", disabled=None, use_knowledge=True):
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
        ranking = [{"id": str(getattr(b, "id", b.get("id"))), "score": float(round(getattr(b, "score", b.get("score", 0.0)), 1))} for b in res.get("buildings", [])[:10]]
        trace = res.get("agent_trace", [])
        ranking_data = next((safe_extract_json(t.get("output")) if isinstance(t.get("output"), str) else t.get("output") for t in trace if "ranking" in t.get("agent_name", "").lower()), {})
        
        eff_weights = {}
        if ranking_data:
            init_w = ranking_data.get("weights", {})
            active_f = [a for a, w in init_w.items() if w > 0]
            s_w = sum(init_w.get(a, 0) for a in active_f)
            if s_w > 0:
                eff_weights = {a: round(init_w[a]/s_w, 2) for a in init_w}
        
        # Extract evaluations and their corresponding building data
        evaluations = []
        building_info = {}
        for t in trace:
            if "evaluation" in t.get("agent_name", "").lower():
                out = safe_extract_json(t.get("output")) if isinstance(t.get("output"), str) else t.get("output")
                if isinstance(out, dict) and "results" in out:
                    evaluations = out["results"]
                break
        
        # Get full data for the top evaluated buildings
        if evaluations and res.get("buildings"):
            top_id = evaluations[0].get("id")
            for b in res.get("buildings"):
                b_id = str(b.id if hasattr(b, "id") else b.get("id"))
                if b_id == top_id:
                    building_info = b.model_dump() if hasattr(b, "model_dump") else b
                    break

        return {
            "query": query, "results_count": res.get("results_count", 0),
            "relaxation_applied": res.get("relaxation_applied", False),
            "execution_time_ms": duration, "final_sql": res.get("filters_applied", {}).get("final_sql", ""),
            "ranking": ranking, "ranking_logic": {"effective_weights": eff_weights},
            "evaluations": evaluations,
            "evaluated_building_data": building_info
        }
    except Exception as e: return {"error": str(e)}

async def process_batch(indices, df, out_dir, sem, arch="multiagent", disabled=None, use_knowledge=True, lock=None, csv_path=None, col=None, trial=None, batch_name=""):
    """Process a batch of queries with real-time progress updates."""
    total = len(indices)
    completed = 0
    tasks = []
    
    for idx in indices:
        async def task(i=idx):
            nonlocal completed
            async with sem:
                res = await run_query(df.at[i, "query"], architecture=arch, disabled=disabled, use_knowledge=use_knowledge)
                completed += 1
                status = "OK" if "error" not in res else "ERR"
                
                if "error" not in res:
                    suffix = f"_tr{trial}" if trial else ""
                    filename = f"query_{i+1:03d}{suffix}.json"
                    with open(out_dir / filename, "w") as f: json.dump(res, f, indent=4)
                    if lock:
                        async with lock:
                            df.at[i, col] = 1
                            df.to_csv(csv_path, index=False)
                elif lock:
                    async with lock:
                        df.at[i, col] = 2
                        df.to_csv(csv_path, index=False)
                
                if total > 0:
                    print(f"  [{batch_name}] Progress: {completed}/{total} ({status})", end="\r")
                    if completed == total: print() # New line when batch ends

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
            if data.get("relaxation_applied"): continue
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

async def evaluate_with_judge(model_name, results_dir):
    """LLM-as-a-judge to evaluate pros/cons quality."""
    from app.services.llm.langchain_client import get_llm
    judge_llm = get_llm(model_name="gpt-5.4") # Use a strong model as judge
    
    samples = []
    for f in list(results_dir.glob("*.json"))[:5]: 
        with open(f) as jf:
            data = json.load(jf)
            if data.get("evaluations") and data.get("evaluated_building_data"):
                samples.append({
                    "query": data["query"], 
                    "evaluation": data["evaluations"][0],
                    "building": data["evaluated_building_data"]
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

async def main():
    suite_path = Path(__file__).parent.absolute()
    pos_json = suite_path / "query_variables_possibilities.json"
    mapping_json = suite_path / "agent_mapping.json"
    with open(mapping_json) as f: mapping = json.load(f)
    await preload_data()
    data_stats = get_data_stats()

    models = ["gpt-5.4", "gpt-oss-120b", "ollama-gemma3-27b", "deepseek-r1-8b"]
    BASELINE_MODEL = "gpt-5.4"
    sem = asyncio.Semaphore(5)

    bench_csv = suite_path / "combinatorial_queries_suite.csv"
    if not bench_csv.exists(): generate_compositions(pos_json, bench_csv)
    sens_csv = suite_path / "sensitivity_queries_suite.csv"
    if not sens_csv.exists(): generate_compositions(pos_json, sens_csv, ablation=True)

    benchmark_results, sensitivity_results = {}, {}
    progress_state = {m: {"benchmark": "WAITING", "sensitivity": "WAITING", "current_task": "None", "perc": 0} for m in models}

    async def update_report():
        report = generate_report(benchmark_results, sensitivity_results, models, progress_state)
        with open(suite_path / "comprehensive_analysis_report.md", "w") as f: f.write(report)

    # Initial empty report
    await update_report()

    for model in models:
        print(f"\n=== STARTING MODEL: {model} ===")
        progress_state[model]["current_task"] = "INITIALIZING"
        await update_report()
        
        # 1. COMBINATORIAL BENCHMARK
        out_root = suite_path / "outputs" / "benchmarks" / model
        out_root.mkdir(parents=True, exist_ok=True)
        df_bench = pd.read_csv(bench_csv)
        total_bench = len(df_bench)

        # Baseline
        if BASELINE_MODEL == model or not BASELINE_MODEL:
            progress_state[model]["current_task"] = "BASELINE"
            await update_report()
            col = f"status_{model.replace('-', '_')}_baseline"
            if col not in df_bench.columns: df_bench[col] = 0; df_bench.to_csv(bench_csv, index=False)
            pending = df_bench[df_bench[col] == 0].index.tolist()
            if pending: 
                print(f"--- [BASELINE] {model} ---")
                await process_batch(pending, df_bench, out_root / "baseline", sem, arch="baseline", lock=asyncio.Lock(), csv_path=bench_csv, col=col, batch_name="BASELINE")
        
        configs = {"full": (None, True), "no_ranking": (["ranking"], True), "no_knowledge": (None, False), "consistency": (None, True)}
        for cid, (dis, kn) in configs.items():
            settings.set_llm_model(model)
            out_dir = out_root / cid
            out_dir.mkdir(parents=True, exist_ok=True)
            progress_state[model]["current_task"] = cid.upper()
            await update_report()

            if cid == "consistency":
                for tr in [1, 2, 3]:
                    col = f"status_{model.replace('-', '_')}_consistency_tr{tr}"
                    if col not in df_bench.columns: df_bench[col] = 0; df_bench.to_csv(bench_csv, index=False)
                    pending = df_bench[df_bench[col] == 0].index.tolist()
                    if pending: 
                        print(f"--- [CONSISTENCY] {model} Trial {tr} ---")
                        await process_batch(pending, df_bench, out_dir, sem, lock=asyncio.Lock(), csv_path=bench_csv, col=col, trial=tr, batch_name=f"CONS-TR{tr}")
            else:
                col = f"status_{model.replace('-', '_')}_{cid}"
                if col not in df_bench.columns: df_bench[col] = 0; df_bench.to_csv(bench_csv, index=False)
                pending = df_bench[df_bench[col] == 0].index.tolist()
                if pending: 
                    print(f"--- [{cid.upper()}] {model} ---")
                    await process_batch(pending, df_bench, out_dir, sem, disabled=dis, use_knowledge=kn, lock=asyncio.Lock(), csv_path=bench_csv, col=col, batch_name=cid.upper())
        # Analyze Phase 1
        progress_state[model]["benchmark"] = "COMPLETED"
        progress_state[model]["current_task"] = "ANALYZING PHASE 1"
        await update_report()

        benchmark_results[model] = {
            "activation": analyze_activation(out_root / "full", mapping, model),
            "iou": analyze_iou_stats(out_root / "full"),
            "arch_comp": analyze_architecture_comparison(out_root / "full", suite_path / "outputs" / "benchmarks" / (BASELINE_MODEL or model) / "baseline"),
            "ranking_impact": analyze_ranking_impact(out_root / "full", out_root / "no_ranking"),
            "knowledge_impact": analyze_knowledge_impact(out_root / "full", out_root / "no_knowledge", data_stats),
            "consistency": analyze_consistency(out_root / "consistency"),
            "eval_quality": await evaluate_with_judge(model, out_root / "full")
        }
        benchmark_results[model]["arch_comp"]["baseline_model"] = BASELINE_MODEL or model

        # 2. SENSITIVITY SUITE
        out_sens = suite_path / "outputs" / "sensitivity" / model
        out_sens.mkdir(parents=True, exist_ok=True)
        df_sens = pd.read_csv(sens_csv)
        sens_configs = [("all_enabled", None, True), ("no_ranking", ["ranking"], True), ("no_knowledge", None, False), ("no_poi", ["poi"], True), ("no_normative", ["normative"], True), ("no_location", ["location"], True), ("no_ape", ["ape"], True), ("no_property_technical", ["property_technical"], True)]
        
        sens_vals = {}
        for cid, dis, kn in sens_configs:
            progress_state[model]["current_task"] = f"SENS-{cid.upper()}"
            await update_report()
            col = f"status_{model.replace('-', '_')}_{cid}"
            if col not in df_sens.columns: df_sens[col] = 0; df_sens.to_csv(sens_csv, index=False)
            cfg_dir = out_sens / cid
            cfg_dir.mkdir(parents=True, exist_ok=True)
            pending = df_sens[df_sens[col] == 0].index.tolist()
            if pending: 
                print(f"--- [SENSITIVITY] {model} {cid} ---")
                await process_batch(pending, df_sens, cfg_dir, sem, disabled=dis, use_knowledge=kn, lock=asyncio.Lock(), csv_path=sens_csv, col=col, batch_name=f"SENS-{cid.upper()}")
            
            if dis or not kn:
                base_ref = {f.name: [r['id'] for r in json.load(open(f))['ranking']] for f in (out_sens / "all_enabled").glob("*.json")}
                cfg_res = {f.name: [r['id'] for r in json.load(open(f))['ranking']] for f in cfg_dir.glob("*.json")}
                ious = [calculate_iou(base_ref[n], cfg_res[n]) for n in cfg_res if n in base_ref]
                sens_vals[cid] = 1.0 - np.mean(ious) if ious else 0
        
        progress_state[model]["sensitivity"] = "COMPLETED"
        progress_state[model]["current_task"] = "IDLE"
        sensitivity_results[model] = {"sensitivity": sens_vals}
        await update_report()

    print(f"Workflow complete. Final report: {suite_path / 'comprehensive_analysis_report.md'}")

if __name__ == "__main__":
    asyncio.run(main())
