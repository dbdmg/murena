from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd
from .core import build_candidates, run_benchmark, _stable_id, _usable_id
from .generate import generate_scenarios
from .reporting import create_reports

def _splits(candidate_path: Path, scenario_path: Path, output: Path, raw_path: Path) -> dict:
    c=pd.read_parquet(candidate_path,columns=["candidate_id","identity_key_json","cadastral_municipality","cadastral_sheet","cadastral_parcel","istat_code"])
    def bucket(s): return int(hashlib.sha256(str(s).encode()).hexdigest()[:8],16)%100
    parcel_key=c[["cadastral_municipality","cadastral_sheet","cadastral_parcel"]].astype(str).apply(lambda row:json.dumps(row.tolist(),ensure_ascii=False,separators=(",",":")),axis=1)
    c["parcel_group_id"]=[hashlib.sha256(("parcel-v1:"+x).encode()).hexdigest() for x in parcel_key]
    c["candidate_partition"]=["development" if (b:=bucket(x))<70 else ("validation" if b<85 else "test") for x in c.parcel_group_id]
    # Geographic holdout is separately assigned; candidate-unit partitioning remains the primary split.
    c["geographic_holdout"]=[bucket("geo:"+str(x))<20 if pd.notna(x) else False for x in c.istat_code]
    split_file=output/"candidate_universe_split.parquet"; c.to_parquet(split_file,index=False)
    raw=pd.read_parquet(raw_path,columns=["source_record_id","cadastral_municipality","cadastral_sheet","cadastral_parcel","cadastral_subaltern","istat_code"])
    if raw.source_record_id.isna().any() or raw.source_record_id.duplicated().any(): raise ValueError("raw source_record_id must be present and unique for split assignment")
    fields=["cadastral_municipality","cadastral_sheet","cadastral_parcel","cadastral_subaltern"]
    parcels=["cadastral_municipality","cadastral_sheet","cadastral_parcel"]
    def identity(row, names):
        vals=[str(row[x]).strip() for x in names]
        return vals if all(_usable_id(row[x]) for x in names) else None
    raw["_unit_key"]=raw[fields].apply(lambda row:identity(row,fields),axis=1)
    raw["_parcel_key"]=raw[parcels].apply(lambda row:identity(row,parcels),axis=1)
    raw["parcel_group_id"]=[hashlib.sha256(("parcel-v1:"+json.dumps(k,ensure_ascii=False,separators=(",",":"))).encode()).hexdigest() if k else None for k in raw._parcel_key]
    raw["unit_id"]=[_stable_id("unit_",k) if k else None for k in raw._unit_key]
    active_map=dict(zip(c.identity_key_json,c.candidate_id))
    raw["candidate_id"]=[active_map.get(json.dumps(k,ensure_ascii=False)) if k else None for k in raw._unit_key]
    raw["identity_status"]=["complete_unit_identity" if unit else ("parcel_group_only" if parcel else "ambiguous_no_parcel_group") for unit,parcel in zip(raw._unit_key,raw._parcel_key)]
    raw["candidate_partition"]=["excluded_ambiguous" if not isinstance(group,str) or not group else ("development" if (b:=bucket(group))<70 else ("validation" if b<85 else "test")) for group in raw.parcel_group_id]
    raw["geographic_holdout"]=[bucket("geo:"+str(x))<20 if pd.notna(x) else False for x in raw.istat_code]
    certificate_split_path=output/"certificate_split_map.parquet"
    raw[["source_record_id","candidate_id","unit_id","parcel_group_id","identity_status","candidate_partition","geographic_holdout"]].to_parquet(certificate_split_path,index=False)
    scenarios=[json.loads(x) for x in scenario_path.read_text().splitlines() if x.strip()]
    groups={}
    for s in scenarios: groups.setdefault((s["generation_metadata"]["strategy"],s["use_case_id"]),[]).append(s)
    assignments={}
    for group,items in sorted(groups.items()):
        items=sorted(items,key=lambda x:x["scenario_id"])
        for i,s in enumerate(items): assignments[s["scenario_id"]]=["development","validation","test"][i%3]
    manifest={"version":"civicbench-splits-v1","candidate_partition_rule":"sha256(parcel_group_id) modulo 100: 0-69 development, 70-84 validation, 85-99 test; all certificates with a complete municipality+sheet+parcel group receive the same split, including historical records and units without a current snapshot candidate.","geographic_holdout_rule":"Separate experimental holdout: sha256('geo:'+ISTAT) modulo 100 < 20; municipality codes with same hash remain grouped.","scenario_split_rule":"Within strategy x use-case groups sorted by scenario_id, assign round-robin development/validation/test.","scenario_assignments":assignments,"candidate_partition_counts":c.candidate_partition.value_counts().to_dict(),"parcel_group_count":int(c.parcel_group_id.nunique()),"parcel_groups_crossing_splits":0,"geographic_holdout_candidate_count":int(c.geographic_holdout.sum()),"source_certificate_rows":len(raw),"source_certificate_split_counts":raw.candidate_partition.value_counts().to_dict(),"source_certificate_identity_status_counts":raw.identity_status.value_counts().to_dict(),"certificate_split_map":"certificate_split_map.parquet","limitations":"Scenario partitions do not themselves prevent candidate leakage. Use the candidate partition or geographic holdout protocol for model development/evaluation, and do not tune against final test outputs. Records with no complete parcel key are labeled excluded_ambiguous instead of being randomly split. Distinct physical buildings on a parcel may remain grouped together."}
    (output/"benchmark_splits.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest

def main():
    p=argparse.ArgumentParser(description="MURENA-CivicBench independent structured benchmark")
    sub=p.add_subparsers(dest="cmd",required=True)
    b=sub.add_parser("build-candidates"); b.add_argument("--raw",type=Path,default=Path("backend/data/metadata/extracted/ape_raw.parquet")); b.add_argument("--output",type=Path,default=Path("backend/research/civicbench/output/v1/candidate_universe.parquet"))
    g=sub.add_parser("generate"); g.add_argument("--candidates",type=Path,default=Path("backend/research/civicbench/output/v1/candidate_universe.parquet")); g.add_argument("--output",type=Path,default=Path("backend/research/civicbench/output/v1/benchmark_scenarios.jsonl")); g.add_argument("--count",type=int,default=200); g.add_argument("--seed",type=int,default=20261019)
    r=sub.add_parser("evaluate"); r.add_argument("--candidates",type=Path,default=Path("backend/research/civicbench/output/v1/candidate_universe.parquet")); r.add_argument("--raw",type=Path,default=Path("backend/data/metadata/extracted/ape_raw.parquet")); r.add_argument("--scenarios",type=Path,default=Path("backend/research/civicbench/output/v1/benchmark_scenarios.jsonl")); r.add_argument("--output-dir",type=Path,default=Path("backend/research/civicbench/output/v1")); r.add_argument("--top-k",type=int,default=20); r.add_argument("--scoring-config",type=Path,default=Path("backend/research/civicbench/oracle_config.json"))
    q=sub.add_parser("report"); q.add_argument("--output-dir",type=Path,default=Path("backend/research/civicbench/output/v1")); q.add_argument("--raw",type=Path,default=Path("backend/data/metadata/extracted/ape_raw.parquet")); q.add_argument("--recommendations",type=Path,default=Path("backend/data/metadata/extracted/ape_recommendations.parquet"))
    a=p.parse_args()
    if a.cmd=="build-candidates": print(json.dumps(build_candidates(a.raw,a.output),indent=2))
    elif a.cmd=="generate": print(json.dumps(generate_scenarios(a.candidates,a.output,a.count,a.seed),indent=2))
    elif a.cmd=="evaluate":
        summary=run_benchmark(a.candidates,a.scenarios,a.output_dir,a.top_k,a.scoring_config)
        _splits(a.candidates,a.scenarios,a.output_dir,a.raw)
        print(json.dumps({"scenarios":len(summary),"result_rows":sum(x["candidate_count"] for x in summary),"zero_eligible":sum(x["eligible_count"]==0 for x in summary),"summaries":str(a.output_dir/"benchmark_summaries.json")},indent=2))
    else: print(json.dumps(create_reports(a.output_dir,a.raw,a.recommendations),indent=2))
if __name__=="__main__": main()
