"""Candidate snapshot, structured scenarios and deterministic reference oracle."""
from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

VERSION = "civicbench-candidates-v1-2026-10-19"
SNAPSHOT_AS_OF = pd.Timestamp("2026-10-19", tz="UTC")
FIELDS = {
    "heated_usable_surface": "number", "cooled_usable_surface": "number",
    "construction_year": "number", "energy_class": "category",
    "epglnren": "number", "epglren": "number", "co2_emissions": "number",
    "heating_energy_need": "number", "cooling_energy_need": "number",
    "dpr412_class_code": "category", "attestation_object_code": "category",
    "climate_zone": "category", "heating_service_present": "boolean",
    "cooling_service_present": "boolean", "municipality": "category",
    "istat_code": "category", "xml_latitude": "number", "xml_longitude": "number",
    "number_real_estate_units": "number", "building_typology_code": "category",
}
OPS = {"eq", "ne", "in", "gte", "lte", "between", "is_true", "is_false"}
USE_CASE_IDS={"community_healthcare","social_community_center","libraries_cultural_facilities","educational_training_spaces","public_administration_offices","social_housing","climate_shelters","multifunctional_community_hubs"}
DEFAULT_SCORING_CONFIG_PATH=Path(__file__).with_name("oracle_config.json")
DEFAULT_SCORING_CONFIG=json.loads(DEFAULT_SCORING_CONFIG_PATH.read_text(encoding="utf-8"))
SCORE_BOUNDS=DEFAULT_SCORING_CONFIG["bounds"]
CLASS_SCORE={name:idx for idx,name in enumerate(DEFAULT_SCORING_CONFIG["energy_class_order"])}

BASE_FIELDS = ["source_record_id", "source_filename", "source_sha256", "parse_status",
 "source_encoding_declared", "source_encoding_used", "potentially_lossy", "source_repaired_byte_count", "parser_warning_count",
 "ape_id", "xml_schema_version", "issue_date", "expiration_date", "cadastral_municipality",
 "cadastral_sheet", "cadastral_parcel", "cadastral_subaltern", "address", "municipality",
 "istat_code", "xml_latitude", "xml_longitude", "construction_year", "building_typology_code",
 "dpr412_class_code", "attestation_object_code", "number_real_estate_units", "floor",
 "heated_usable_surface", "cooled_usable_surface", "heated_volume", "climate_zone", "energy_class",
 "epglnren", "epglren", "co2_emissions", "heating_energy_need", "cooling_energy_need",
 "envelope_winter_quality_code", "envelope_summer_quality_code", "main_energy_carrier",
 "heating_system_code", "dhw_system_code", "heating_service_present", "cooling_service_present"]


def _stable_id(prefix: str, fields: list[str]) -> str:
    payload = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _file_sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): digest.update(block)
    return digest.hexdigest()


def _usable_id(x: Any) -> bool:
    if x is None or pd.isna(x): return False
    s = str(x).strip()
    if not s: return False
    try:
        if int(Decimal(s)) == 0: return False  # matches Phase 1's numeric-zero placeholder rule
    except (InvalidOperation, ValueError, OverflowError):
        pass  # Coded alphanumeric values are preserved, not coerced into numbers.
    return True

def _numeric_code(x: Any) -> bool:
    try:
        return Decimal(str(x).strip()).is_finite()
    except InvalidOperation:
        return False


def build_candidates(raw_path: Path, output: Path) -> dict[str, Any]:
    """Select latest dated certificate per complete nonzero unit key; retain history refs."""
    con = duckdb.connect()
    raw = con.execute("select * from read_parquet(?)", [str(raw_path)]).fetchdf()
    missing_cols = sorted(set(BASE_FIELDS) - set(raw.columns))
    if missing_cols: raise ValueError(f"raw dataset missing required columns: {missing_cols}")
    if raw.source_record_id.isna().any() or raw.source_record_id.duplicated().any():
        raise ValueError("source_record_id must be present and unique")
    raw["_issue_date"] = pd.to_datetime(raw.issue_date, errors="coerce", utc=True)
    raw["_expiration_date"] = pd.to_datetime(raw.expiration_date, errors="coerce", utc=True)
    keys = ["cadastral_municipality", "cadastral_sheet", "cadastral_parcel", "cadastral_subaltern"]
    complete = raw[keys].apply(lambda c: c.map(_usable_id)).all(axis=1)
    identifiable = raw.loc[complete].copy()
    identifiable["_key"] = identifiable[keys].astype(str).apply(lambda row: tuple(x.strip() for x in row), axis=1)
    n_units = identifiable._key.nunique()
    # A current-state certificate must have been issued by the fixed as-of date and not yet expired.
    # Incomplete identities and inactive certificates stay preserved in the original raw source.
    is_current=(identifiable._issue_date.notna() & identifiable._expiration_date.notna() &
                (identifiable._issue_date <= SNAPSHOT_AS_OF) & (identifiable._expiration_date >= SNAPSHOT_AS_OF))
    dated = identifiable.loc[is_current].copy()
    dated = dated.sort_values(["_issue_date", "source_record_id"], ascending=[False, True], kind="mergesort")
    chosen = dated.drop_duplicates("_key", keep="first").copy()
    by_key = identifiable.groupby("_key", sort=True).source_record_id.apply(list).to_dict()
    chosen["candidate_id"] = chosen._key.map(lambda k: _stable_id("unit_", list(k)))
    chosen["selected_source_record_id"] = chosen.source_record_id
    chosen["historical_source_record_ids"] = chosen._key.map(lambda k: json.dumps(sorted(by_key[k])))
    chosen["historical_certificate_count"] = chosen._key.map(lambda k: len(by_key[k])).astype("int32")
    chosen["candidate_universe_version"] = VERSION
    chosen["identity_key_json"] = chosen._key.map(lambda k: json.dumps(list(k), ensure_ascii=False))
    nonnumeric_fields=["cadastral_sheet","cadastral_parcel","cadastral_subaltern"]
    chosen["identity_confidence"] = np.where(chosen[nonnumeric_fields].apply(lambda col: col.map(_numeric_code)).all(axis=1),
      "complete_nonzero_numeric_key", "complete_key_with_nonnumeric_component")
    outcols = ["candidate_id", "candidate_universe_version", "identity_key_json", "selected_source_record_id",
      "historical_source_record_ids", "historical_certificate_count", "identity_confidence"] + [c for c in BASE_FIELDS if c in chosen]
    output.parent.mkdir(parents=True, exist_ok=True)
    chosen[outcols].sort_values("candidate_id").to_parquet(output, index=False)
    valid_keys=set(dated._key)
    no_current_keys=set(identifiable._key)-valid_keys
    reasons = {"incomplete_or_zero_cadastral_identity": int((~complete).sum()),
               "complete_identity_without_parseable_issue_or_expiration_date": int((complete & (raw._issue_date.isna() | raw._expiration_date.isna())).sum()),
               "expired_complete_key_certificates": int((complete & raw._expiration_date.lt(SNAPSHOT_AS_OF)).sum()),
               "future_issue_complete_key_certificates": int((complete & raw._issue_date.gt(SNAPSHOT_AS_OF)).sum())}
    manifest = {"version": VERSION, "raw_path": str(raw_path), "candidate_path": str(output),
      "raw_parquet_sha256": _file_sha256(raw_path), "candidate_parquet_sha256": _file_sha256(output),
      "original_certificate_count": len(raw), "identifiable_certificates": int(complete.sum()),
      "identifiable_cadastral_units": int(n_units), "snapshot_candidate_count": len(chosen),
      "snapshot_as_of_date": SNAPSHOT_AS_OF.date().isoformat(),
      "current_certificate_rule": "issue_date <= snapshot_as_of_date AND expiration_date >= snapshot_as_of_date; both dates must parse.",
      "identifiable_units_without_current_valid_certificate": len(no_current_keys),
      "ambiguous_identity_certificate_count": reasons["incomplete_or_zero_cadastral_identity"],
      "nonnumeric_cadastral_component_certificates": int(identifiable[nonnumeric_fields].apply(lambda col: ~col.map(_numeric_code)).any(axis=1).sum()),
      "candidate_units_with_nonnumeric_components": int((chosen.identity_confidence=="complete_key_with_nonnumeric_component").sum()),
      "excluded_certificates_by_reason": reasons,
      "multiple_certificate_units": int(sum(len(ids)>1 for ids in by_key.values())),
      "snapshot_units_with_multiple_historical_certificates": int((chosen.historical_certificate_count > 1).sum()),
      "selection_rule": "Among certificates with issue_date <= 2026-10-19 and expiration_date >= 2026-10-19, select the latest issue_date; source_record_id ascending breaks same-date ties. This is a date-based snapshot rule, not legal validation beyond the source expiry field.",
      "unit_key_fields": keys, "identity_limitations": "Cadastral units are not physical buildings; a unit may be part of a building and a parcel may contain multiple buildings. Incomplete keys are not merged. Non-numeric sheet/parcel/subaltern strings are preserved and flagged rather than assumed invalid or normalized.",
      "history_retained": "All source_record_id values for each selected unit are stored in historical_source_record_ids; original raw Parquet is unchanged."}
    output.with_name("candidate_universe_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def validate_scenario(s: dict[str, Any]) -> dict[str, Any]:
    required = {"scenario_id", "use_case_id", "candidate_universe_version", "geographic_scope", "hard_constraints",
                "preferences", "missing_value_policy", "normalization_method", "scoring_config_version", "expected_behavior", "generation_metadata"}
    extra, absent = set(s)-required, required-set(s)
    if extra or absent: raise ValueError(f"scenario keys mismatch; extra={sorted(extra)}, missing={sorted(absent)}")
    if not re.fullmatch(r"CB-[AB]-[0-9]{4}",str(s["scenario_id"])): raise ValueError("invalid scenario_id")
    if s["use_case_id"] not in USE_CASE_IDS: raise ValueError("unsupported use case")
    if not isinstance(s["hard_constraints"],list) or not isinstance(s["preferences"],list) or not isinstance(s["generation_metadata"],dict) or not isinstance(s["expected_behavior"],dict): raise ValueError("constraints, preferences, metadata, and expected behavior must be objects/lists")
    if len(s["preferences"])>2: raise ValueError("oracle-v1 supports at most two preference criteria per scenario")
    meta=s["generation_metadata"]
    if meta.get("strategy") not in {"A_distribution_independent","B_dataset_aware"} or not isinstance(meta.get("seed"),int) or not isinstance(meta.get("difficulty"),str): raise ValueError("invalid scenario generation metadata")
    if s["missing_value_policy"] not in {"exclude_from_confirmed", "include_unknown_separately"}: raise ValueError("unsupported missing value policy")
    if s["normalization_method"] != "fixed_bounds_clipped_minmax_v1": raise ValueError("unsupported normalization method")
    scope=s["geographic_scope"]
    if set(scope)!={"type","value"}: raise ValueError("geographic_scope must contain only type and value")
    if scope.get("type") not in {"all", "istat_code"}: raise ValueError("unsupported geographic scope")
    if scope.get("type")=="all" and scope.get("value") is not None: raise ValueError("all geographic scope requires null value")
    if scope.get("type")=="istat_code" and not scope.get("value"): raise ValueError("istat_code scope requires a value")
    if scope.get("type")=="istat_code" and not any(c.get("attribute")=="istat_code" and c.get("operator")=="eq" and c.get("value")==scope["value"] for c in s["hard_constraints"]):
        raise ValueError("geographic scope must be represented by an explicit hard constraint")
    for c in s["hard_constraints"]:
        f, op = c.get("attribute"), c.get("operator")
        if f not in FIELDS or op not in OPS: raise ValueError(f"unsupported constraint: {f} {op}")
        if set(c)!={"constraint_id","attribute","operator","value","unit","source","missing_behavior"}: raise ValueError("constraint fields must match the explicit schema")
        if not isinstance(c["constraint_id"],str) or not c["constraint_id"] or not isinstance(c["source"],str) or not c["source"]: raise ValueError("constraint id and provenance source are required")
        if op in {"gte", "lte", "between"} and FIELDS[f] != "number": raise ValueError(f"{op} requires numerical attribute {f}")
        if op in {"is_true", "is_false"} and FIELDS[f] != "boolean": raise ValueError(f"{op} requires boolean attribute {f}")
        if "missing_behavior" not in c or c["missing_behavior"] != "unknown": raise ValueError("missing_behavior must be explicitly 'unknown'")
        if c["unit"] is not None and not isinstance(c["unit"],str): raise ValueError("constraint unit must be a string or null")
        val=c["value"]
        if op in {"gte","lte"} and (not isinstance(val,(int,float)) or isinstance(val,bool) or not math.isfinite(val)): raise ValueError(f"{op} requires a finite number")
        if op=="between" and (not isinstance(val,list) or len(val)!=2 or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in val) or val[0]>val[1]): raise ValueError("between requires an ordered pair of finite numbers")
        if op=="in":
            if not isinstance(val,list) or not val: raise ValueError("in requires a nonempty list")
            kind=FIELDS[f]
            good=all(isinstance(x,str) for x in val) if kind=="category" else (all(isinstance(x,bool) for x in val) if kind=="boolean" else all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in val))
            if not good: raise ValueError(f"in values have the wrong type for {f}")
        if op in {"is_true","is_false"} and val is not (op=="is_true"): raise ValueError(f"{op} requires matching boolean value")
        if op in {"eq","ne"}:
            kind=FIELDS[f]
            valid=(isinstance(val,str) if kind=="category" else (isinstance(val,bool) if kind=="boolean" else isinstance(val,(int,float)) and not isinstance(val,bool) and math.isfinite(val)))
            if not valid: raise ValueError(f"{op} value has the wrong type for {f}")
    total = 0.0
    for p in s["preferences"]:
        f = p.get("attribute")
        if set(p)!={"attribute","direction","weight","normalization"}: raise ValueError("preference fields must match the explicit schema")
        if f not in FIELDS or FIELDS[f] != "number" and f != "energy_class": raise ValueError(f"unsupported preference: {f}")
        if p.get("direction") not in {"maximize", "minimize"}: raise ValueError("preference direction must be maximize/minimize")
        if p.get("normalization") != "fixed_bounds_clipped_minmax_v1": raise ValueError("unsupported preference normalization")
        w = p.get("weight")
        if not isinstance(w, (int, float)) or w <= 0 or not math.isfinite(w): raise ValueError("preference weights must be finite and positive")
        total += w
    if s["preferences"] and not math.isclose(total, 1.0, abs_tol=1e-8): raise ValueError("preference weights must sum to 1")
    return s


def _predicate(series: pd.Series, c: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    vals = series.to_numpy()
    null = pd.isna(vals)
    op, target = c["operator"], c.get("value")
    result = np.zeros(len(vals), dtype=bool)
    try:
        if op == "eq": result = vals == target
        elif op == "ne": result = vals != target
        elif op == "in": result = np.isin(vals, target)
        elif op == "gte": result = vals.astype(float) >= float(target)
        elif op == "lte": result = vals.astype(float) <= float(target)
        elif op == "between": result = (vals.astype(float) >= float(target[0])) & (vals.astype(float) <= float(target[1]))
        elif op == "is_true": result = vals == True
        elif op == "is_false": result = vals == False
    except (TypeError, ValueError):
        null = np.ones(len(vals), dtype=bool)
    result = np.asarray(result, dtype=bool) & ~null
    return result, null


def _criterion(values: pd.Series, p: dict[str, Any], scoring_config: dict[str, Any]) -> np.ndarray:
    val = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    if p["attribute"] == "energy_class":
        class_score={name:idx for idx,name in enumerate(scoring_config["energy_class_order"])}
        val = values.map(class_score).to_numpy(dtype=float, na_value=np.nan)
        lo, hi = 0.0, float(len(class_score)-1)
    else:
        lo, hi = scoring_config["bounds"][p["attribute"]]
    score = np.clip((val - lo) / (hi - lo), 0, 1)
    if p["direction"] == "minimize": score = 1-score
    score[np.isnan(val)] = np.nan
    return score


def evaluate_scenario(s: dict[str, Any], candidates: pd.DataFrame, top_k: int = 20,
                      scoring_config: dict[str, Any] | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    validate_scenario(s)
    if s["candidate_universe_version"] != VERSION: raise ValueError("candidate universe version mismatch")
    config=scoring_config or DEFAULT_SCORING_CONFIG
    if not str(config.get("version", "")).startswith("oracle-v1") or config.get("normalization")!="fixed_bounds_clipped_minmax_v1": raise ValueError("unsupported scoring configuration version")
    if s["scoring_config_version"]!=config["version"]: raise ValueError("scenario scoring configuration version mismatch")
    if not isinstance(config.get("bounds"),dict) or not isinstance(config.get("energy_class_order"),list) or len(config["energy_class_order"])<2 or len(set(config["energy_class_order"]))!=len(config["energy_class_order"]): raise ValueError("malformed scoring configuration")
    for p in s["preferences"]:
        if p["attribute"]!="energy_class":
            bounds=config["bounds"].get(p["attribute"])
            if not isinstance(bounds,list) or len(bounds)!=2 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in bounds) or bounds[0]>=bounds[1]: raise ValueError(f"missing or invalid fixed bounds for {p['attribute']}")
    n = len(candidates); status = np.full(n, "eligible", dtype=object); reasons = [[] for _ in range(n)]
    for c in s["hard_constraints"]:
        truth, missing = _predicate(candidates[c["attribute"]], c)
        failed = ~truth & ~missing
        status[failed] = "ineligible"
        for i in np.flatnonzero(failed): reasons[i].append(c["constraint_id"])
        status[(missing) & (status != "ineligible")] = "unknown"
        for i in np.flatnonzero(missing & (status != "ineligible")): reasons[i].append(c["constraint_id"] + ":missing")
    near_boundary=np.zeros(n,dtype=bool)
    for c in s["hard_constraints"]:
        attr=c["attribute"]
        if FIELDS[attr]!="number" or c["operator"] not in {"gte","lte","between"} or attr not in config["bounds"]: continue
        lo,hi=config["bounds"][attr]; tolerance=0.01*(hi-lo)
        vals=pd.to_numeric(candidates[attr],errors="coerce").to_numpy(dtype=float,na_value=np.nan)
        targets=c["value"] if c["operator"]=="between" else [c["value"]]
        near=np.zeros(n,dtype=bool)
        for target in targets: near |= np.abs(vals-float(target))<=tolerance
        near_boundary |= near
    out = pd.DataFrame({"candidate_id": candidates.candidate_id, "eligibility_status": status,
                        "constraint_reasons": [json.dumps(x) for x in reasons]})
    weight_scores=[]
    for p in s["preferences"]:
        name = "score_" + p["attribute"]
        scores = _criterion(candidates[p["attribute"]], p, config)
        out[name] = scores
        weight_scores.append((scores, p["weight"]))
    if weight_scores:
        matrix = np.vstack([v for v, _ in weight_scores])
        # Incomplete preference evidence does not silently renormalize the declared weights.
        aggregate = np.sum(matrix * np.array([w for _, w in weight_scores])[:, None], axis=0)
        aggregate[np.isnan(matrix).any(axis=0)] = np.nan
        out["aggregate_score"] = aggregate
    else: out["aggregate_score"] = np.nan
    out["pareto_optimal"] = False
    score_cols = [c for c in out if c.startswith("score_")]
    confirmed = np.flatnonzero(out.eligibility_status.eq("eligible").to_numpy())
    if score_cols and len(confirmed):
        arr = out.iloc[confirmed][score_cols].to_numpy(dtype=float)
        complete_idx = np.flatnonzero(~np.isnan(arr).any(axis=1)); arr = arr[complete_idx]
        front=[]
        if arr.shape[1] == 1:
            best = np.nanmax(arr[:, 0]); front = confirmed[complete_idx[np.flatnonzero(arr[:, 0] == best)]].tolist()
        elif arr.shape[1] == 2:
            best_second = -np.inf
            for first in sorted(np.unique(arr[:, 0]), reverse=True):
                group=np.flatnonzero(arr[:,0] == first)
                group_best=float(np.max(arr[group,1]))
                if group_best > best_second:
                    tied=group[arr[group,1] == group_best]
                    front.extend(confirmed[complete_idx[tied]].tolist())
                best_second=max(best_second,group_best)
        else:
            # Multi-dimensional frontier is computed by pairwise dominance only for modest sets.
            # Avoid quadratic behavior on the corpus: use a deterministic bounded sample if >5000.
            if len(arr) > 5000: raise ValueError("Pareto frontier with >2 preferences is limited to 5000 confirmed candidates")
            for i, row in enumerate(arr):
                dominates = np.all(arr >= row, axis=1) & np.any(arr > row, axis=1)
                dominates[i] = False
                if not dominates.any(): front.append(confirmed[complete_idx[i]])
        out.loc[front, "pareto_optimal"] = True
    out["rank"] = pd.Series([pd.NA]*n, dtype="Int64")
    order = out[out.eligibility_status.eq("eligible") & out.aggregate_score.notna()].sort_values(
        ["aggregate_score", "candidate_id"], ascending=[False, True], kind="mergesort").index
    out.loc[order, "rank"] = np.arange(1, len(order)+1)
    eligible = out[out.eligibility_status.eq("eligible")]
    summary = {"scenario_id": s["scenario_id"], "candidate_count": n,
      "eligible_count": int((status=="eligible").sum()), "ineligible_count": int((status=="ineligible").sum()),
      "unknown_count": int((status=="unknown").sum()), "ranked_count": int(out["rank"].notna().sum()),
      "top_k": out.loc[order[:top_k], "candidate_id"].tolist(), "oracle_version": config["version"], "scoring_config_version":config["version"],
      "near_threshold_candidate_count":int(near_boundary.sum()),"near_threshold_tolerance":"within 1% of fixed normalization span for any numerical gte/lte/between constraint",
      "normalization": "Fixed clipped min-max bounds in scoring configuration; not recalculated after filtering.",
      "tie_break": "candidate_id ascending", "pareto_count": int(out.pareto_optimal.sum())}
    return out, summary


def run_benchmark(candidate_path: Path, scenario_path: Path, output_dir: Path, top_k: int = 20,
                  scoring_config_path: Path | None = None) -> list[dict[str, Any]]:
    candidates = pd.read_parquet(candidate_path)
    scenarios = [validate_scenario(json.loads(x)) for x in scenario_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    config=json.loads((scoring_config_path or DEFAULT_SCORING_CONFIG_PATH).read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True); summaries=[]
    target=output_dir/"benchmark_ground_truth.parquet"
    partial=output_dir/"benchmark_ground_truth.parquet.partial"
    score_attributes=sorted({"score_"+p["attribute"] for s in scenarios for p in s["preferences"]})
    writer=None
    for s in scenarios:
        result, summary = evaluate_scenario(s, candidates, top_k, config)
        count=summary["eligible_count"]
        size_label="none" if count==0 else ("scarce" if count<=100 else ("moderate" if count<=10000 else "broad"))
        tradeoff=len({p["direction"] for p in s["preferences"]})>1
        tags=[size_label]
        if tradeoff: tags.append("opposing_preference_directions")
        if summary["pareto_count"]>1: tags.append("multiple_pareto_alternatives")
        if s["generation_metadata"]["strategy"]=="B_dataset_aware" and summary["near_threshold_candidate_count"]>0: tags.append("near_hard_constraint_boundary")
        summary["difficulty_tags"]=tags
        summary["eligible_set_size_band"]=size_label
        summary["preference_direction_tradeoff"]=tradeoff
        s["generation_metadata"]["difficulty"]="+".join(tags)
        s["generation_metadata"]["eligible_set_size_band"]=size_label
        result.insert(0, "scenario_id", s["scenario_id"])
        for col in score_attributes:
            if col not in result: result[col]=np.nan
        result=result[["scenario_id","candidate_id","eligibility_status","constraint_reasons"]+score_attributes+["aggregate_score","pareto_optimal","rank"]]
        table=pa.Table.from_pandas(result,preserve_index=False)
        if writer is None: writer=pq.ParquetWriter(partial,table.schema,compression="zstd")
        writer.write_table(table)
        summaries.append(summary)
    if writer is not None:
        writer.close(); partial.replace(target)
    else:
        pd.DataFrame().to_parquet(target,index=False)
    (output_dir/"benchmark_summaries.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    scenario_path.write_text("".join(json.dumps(s,ensure_ascii=False,sort_keys=True)+"\n" for s in scenarios),encoding="utf-8")
    config_hash=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    run_manifest={"benchmark_version":"civicbench-pilot-v1","candidate_universe_version":VERSION,
      "candidate_parquet":str(candidate_path),"candidate_parquet_sha256":_file_sha256(candidate_path),
      "scenario_jsonl":str(scenario_path),"scenario_jsonl_sha256":_file_sha256(scenario_path),
      "scoring_config_version":config["version"],"scoring_config_sha256":config_hash,
      "ground_truth_parquet":str(target),"ground_truth_parquet_sha256":_file_sha256(target),
      "scenario_count":len(scenarios),"candidate_count":len(candidates),
      "ground_truth_rows":int(len(candidates)*len(scenarios)),"top_k":top_k,
      "writer":"incremental per-scenario Parquet batches; atomic final replacement"}
    (output_dir/"benchmark_run_manifest.json").write_text(json.dumps(run_manifest,indent=2),encoding="utf-8")
    return summaries
