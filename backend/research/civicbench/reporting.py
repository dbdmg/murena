from __future__ import annotations
import json
import hashlib
from pathlib import Path
import duckdb
import pandas as pd
from .core import validate_scenario, evaluate_scenario, DEFAULT_SCORING_CONFIG_PATH

def create_reports(root: Path, raw_path: Path, recommendation_path: Path) -> dict:
    root.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((root/"candidate_universe_manifest.json").read_text())
    gen=json.loads((root/"scenario_generation_report.json").read_text())
    summaries=json.loads((root/"benchmark_summaries.json").read_text())
    scenarios=[json.loads(x) for x in (root/"benchmark_scenarios.jsonl").read_text().splitlines() if x.strip()]
    for s in scenarios: validate_scenario(s)
    cpath=root/"candidate_universe.parquet"; gpath=root/"benchmark_ground_truth.parquet"
    con=duckdb.connect()
    csql=f"read_parquet('{cpath.as_posix()}')"; gsql=f"read_parquet('{gpath.as_posix()}')"
    cand_count=int(con.execute(f"select count(*) from {csql}").fetchone()[0])
    candidate_ids=int(con.execute(f"select count(distinct candidate_id) from {csql}").fetchone()[0])
    row_count=int(con.execute(f"select count(*) from {gsql}").fetchone()[0])
    statuses={r[0]:int(r[1]) for r in con.execute(f"select eligibility_status,count(*) from {gsql} group by 1").fetchall()}
    groupstats=con.execute(f"select count(*) n, min(n) lo, max(n) hi from (select scenario_id,count(*) n from {gsql} group by 1)").fetchone()
    duplicated=int(con.execute(f"select count(*) from (select scenario_id,candidate_id,count(*) n from {gsql} group by 1,2 having n>1)").fetchone()[0])
    nullable={r[0]:int(r[1]) for r in con.execute(f"select column_name, null_percentage from (summarize select * from {csql})").fetchall()} if False else {}
    fields=["heated_usable_surface","construction_year","dpr412_class_code","attestation_object_code","energy_class","epglnren","epglren","co2_emissions","heating_energy_need","cooling_energy_need","xml_latitude","xml_longitude","municipality","istat_code"]
    completeness={}
    for f in fields:
        n=int(con.execute(f"select count({f}) from {csql}").fetchone()[0])
        completeness[f]={"nonnull":n,"null":cand_count-n,"nonnull_pct":round(100*n/cand_count,3) if cand_count else None}
    quality={
      "nonpositive_heated_surface":int(con.execute(f"select count(*) from {csql} where heated_usable_surface<=0").fetchone()[0]),
      "construction_year_before_1800":int(con.execute(f"select count(*) from {csql} where construction_year<1800").fetchone()[0]),
      "construction_year_after_2026":int(con.execute(f"select count(*) from {csql} where construction_year>2026").fetchone()[0]),
      "negative_energy_indicators":int(con.execute(f"select count(*) from {csql} where epglnren<0 or epglren<0 or co2_emissions<0 or heating_energy_need<0 or cooling_energy_need<0").fetchone()[0]),
      "out_of_range_wgs84_coordinates":int(con.execute(f"select count(*) from {csql} where xml_latitude not between -90 and 90 or xml_longitude not between -180 and 180").fetchone()[0]),
      "coordinate_pair_at_zero":int(con.execute(f"select count(*) from {csql} where xml_latitude=0 and xml_longitude=0").fetchone()[0]),
      "lat_lon_not_both_present":int(con.execute(f"select count(*) from {csql} where xml_latitude is null or xml_longitude is null").fetchone()[0]),
      "source_expiration_after_2040":int(con.execute(f"select count(*) from {csql} where year(try_cast(expiration_date as date))>2040").fetchone()[0])}
    numeric_stats={}
    for f in ("heated_usable_surface","construction_year","epglnren","epglren","co2_emissions","heating_energy_need"):
        row=con.execute(f"select min({f}),quantile_cont({f},[.1,.25,.5,.75,.9]),max({f}) from {csql}").fetchone()
        numeric_stats[f]={"minimum":row[0],"quantiles_10_25_50_75_90":row[1],"maximum":row[2]}
    rec_certs=int(con.execute("select count(distinct source_record_id) from read_parquet(?)",[str(recommendation_path)]).fetchone()[0])
    candidate_rec_coverage=con.execute(f"select count(*) filter(where exists(select 1 from read_parquet(?) r where r.source_record_id=c.selected_source_record_id)), count(*) from {csql} c",[str(recommendation_path)]).fetchone()
    rank_gaps=int(con.execute(f"select count(*) from (select scenario_id,count(*) n,min(rank) lo,max(rank) hi,count(rank) rn from {gsql} group by 1 having rn>0 and (lo<>1 or rn<>hi))").fetchone()[0])
    split=pd.read_parquet(root/"candidate_universe_split.parquet")
    cross_split=int((split.groupby("parcel_group_id").candidate_partition.nunique()>1).sum())
    cert_split=pd.read_parquet(root/"certificate_split_map.parquet")
    cert_cross_split=int((cert_split.dropna(subset=["parcel_group_id"]).groupby("parcel_group_id").candidate_partition.nunique()>1).sum())
    first=scenarios[0]
    needed=sorted({"candidate_id"}|{x["attribute"] for x in first["hard_constraints"]}|{x["attribute"] for x in first["preferences"]})
    sample_candidates=pd.read_parquet(cpath,columns=needed)
    _,repeat_summary=evaluate_scenario(first,sample_candidates)
    saved_first=next(x for x in summaries if x["scenario_id"]==first["scenario_id"])
    oracle_reproducible=repeat_summary["top_k"]==saved_first["top_k"] and repeat_summary["eligible_count"]==saved_first["eligible_count"] and repeat_summary["unknown_count"]==saved_first["unknown_count"]
    scoring_versions={x.get("scoring_config_version") for x in summaries}
    scoring_version_consistent=len(scoring_versions)==1 and all(s["scoring_config_version"] in scoring_versions for s in scenarios)
    scenario_properties={"zero_confirmed_eligible":sum(x["eligible_count"]==0 for x in summaries),
      "scenarios_with_opposing_preference_directions":sum(x.get("preference_direction_tradeoff",False) for x in summaries),
      "scenarios_with_multiple_pareto_alternatives":sum(x["pareto_count"]>1 for x in summaries),
      "scenarios_with_candidates_near_numeric_constraint_boundaries":sum(x.get("near_threshold_candidate_count",0)>0 for x in summaries),
      "scenarios_with_unknown_candidates":sum(x["unknown_count"]>0 for x in summaries),
      "scenarios_with_unranked_eligible_candidates":sum(x["ranked_count"]<x["eligible_count"] for x in summaries),
      "hard_constraint_count_distribution":{str(k):sum(len(s["hard_constraints"])==k for s in scenarios) for k in sorted({len(s["hard_constraints"]) for s in scenarios})},
      "preference_count_distribution":{str(k):sum(len(s["preferences"])==k for s in scenarios) for k in sorted({len(s["preferences"]) for s in scenarios})},
      "geographic_scope_counts":{k:sum(s["geographic_scope"]["type"]==k for s in scenarios) for k in sorted({s["geographic_scope"]["type"] for s in scenarios})},
      "geographic_scope_istat_code_count":len({s["geographic_scope"]["value"] for s in scenarios if s["geographic_scope"]["type"]=="istat_code"})}
    # Reproducible structural checks (all certificate histories remain referenced, no duplicate source IDs).
    hist_counts=con.execute(f"select sum(historical_certificate_count) from {csql}").fetchone()[0]
    checks={"candidate_rows_match_manifest":cand_count==manifest["snapshot_candidate_count"],
      "candidate_ids_unique":candidate_ids==cand_count,"scenario_count_is_200":len(scenarios)==200,
      "scenario_ids_unique":len({s["scenario_id"] for s in scenarios})==len(scenarios),
      "ground_truth_rows_match_cartesian_candidate_scenario_universe":row_count==cand_count*len(scenarios),
      "one_ground_truth_row_per_candidate_per_scenario":duplicated==0,
      "all_scenarios_have_full_candidate_coverage":groupstats[0]==len(scenarios) and groupstats[1]==cand_count and groupstats[2]==cand_count,
      "rank_sequences_have_no_gaps":rank_gaps==0,"parcel_groups_do_not_cross_candidate_splits":cross_split==0,
      "all_source_certificate_ids_have_one_split_status":len(cert_split)==manifest["original_certificate_count"] and cert_split.source_record_id.is_unique,
      "complete_source_parcel_groups_do_not_cross_splits":cert_cross_split==0,
      "candidate_history_reference_count_at_least_snapshot_size":hist_counts>=cand_count,
      "first_scenario_oracle_reproduces_saved_top_k_and_eligibility":oracle_reproducible,
      "scoring_configuration_version_consistent":scoring_version_consistent}
    report={"version":"civicbench-validation-v1","scoring_config_version":next(iter(scoring_versions)) if scoring_versions else None,"checks":checks,"candidate_rows":cand_count,"candidate_ids_unique":candidate_ids,
      "scenario_count":len(scenarios),"ground_truth_rows":row_count,"expected_ground_truth_rows":cand_count*len(scenarios),
      "ground_truth_status_rows":statuses,"per_scenario_ground_truth_row_counts":{"scenario_count":int(groupstats[0]),"minimum":int(groupstats[1]),"maximum":int(groupstats[2])},
      "duplicate_scenario_candidate_pairs":duplicated,"rank_sequence_scenarios_with_gaps":rank_gaps,"parcel_groups_crossing_splits":cross_split,
      "source_certificate_split_rows":len(cert_split),"source_certificate_split_ids_unique":bool(cert_split.source_record_id.is_unique),"source_parcel_groups_crossing_splits":cert_cross_split,
      "oracle_reproducibility_check":oracle_reproducible,
      "candidate_attribute_completeness":completeness,"recommendation_source_certificates":rec_certs,
      "current_candidate_recommendation_coverage":{"with_recommendations":int(candidate_rec_coverage[0]),"candidate_count":int(candidate_rec_coverage[1]),"pct":round(100*candidate_rec_coverage[0]/candidate_rec_coverage[1],3) if candidate_rec_coverage[1] else None},
      "candidate_quality_flags":quality,"candidate_numeric_distributions":numeric_stats,"scenario_properties":scenario_properties,
      "all_checks_pass":all(checks.values())}
    (root/"benchmark_validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    def sha(path: Path) -> str:
        h=hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
        return h.hexdigest()
    score_config=json.loads(DEFAULT_SCORING_CONFIG_PATH.read_text(encoding="utf-8"))
    run_manifest={"benchmark_version":"civicbench-pilot-v1","candidate_universe_version":manifest["version"],
      "candidate_parquet":str(cpath),"candidate_parquet_sha256":sha(cpath),
      "scenario_jsonl":str(root/"benchmark_scenarios.jsonl"),"scenario_jsonl_sha256":sha(root/"benchmark_scenarios.jsonl"),
      "scoring_config_version":score_config["version"],"scoring_config_sha256":hashlib.sha256(json.dumps(score_config,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
      "ground_truth_parquet":str(gpath),"ground_truth_parquet_sha256":sha(gpath),
      "candidate_manifest_sha256":sha(root/"candidate_universe_manifest.json"),
      "candidate_split_sha256":sha(root/"candidate_universe_split.parquet"),
      "certificate_split_sha256":sha(root/"certificate_split_map.parquet"),
      "benchmark_splits_sha256":sha(root/"benchmark_splits.json"),
      "scenario_count":len(scenarios),"candidate_count":cand_count,"ground_truth_rows":row_count,"top_k":20,
      "writer":"incremental per-scenario Parquet batches; atomic final replacement"}
    (root/"benchmark_run_manifest.json").write_text(json.dumps(run_manifest,indent=2),encoding="utf-8")
    distributions={}
    for key in ("eligible_set_size_band",):
        distributions[key]={}
        for s in summaries: distributions[key][s[key]]=distributions[key].get(s[key],0)+1
    strategy_counts={}
    for s in scenarios:
        k=s["generation_metadata"]["strategy"]; strategy_counts[k]=strategy_counts.get(k,0)+1
    val_lines=["# CivicBench pilot validation report","","## Validation status","",f"All automated artifact checks passed: **{report['all_checks_pass']}**.","", "| Check | Result |","|---|---:|"]
    val_lines += [f"| {k.replace('_',' ')} | {'PASS' if v else 'FAIL'} |" for k,v in checks.items()]
    val_lines += ["", "## Population reconciliation", "",f"- Original Phase 1 certificate records: {manifest['original_certificate_count']:,}.",f"- Complete, nonzero source unit keys: {manifest['identifiable_certificates']:,} certificates across {manifest['identifiable_cadastral_units']:,} distinct cadastral units.",f"- Current-state snapshot as of {manifest['snapshot_as_of_date']}: {cand_count:,} candidates; {manifest['identifiable_units_without_current_valid_certificate']:,} identifiable units have no certificate satisfying the issue/expiration date rule.",f"- Incomplete/zero identity certificates excluded from unit snapshot: {manifest['ambiguous_identity_certificate_count']:,}; retained in raw certificate Parquet.",f"- Certificates with nonnumeric cadastral components: {manifest['nonnumeric_cadastral_component_certificates']:,}; selected candidate units carrying such a code: {manifest['candidate_units_with_nonnumeric_components']:,}. These codes remain source strings and are flagged.",f"- Units with repeated certificates across complete-key history: {manifest['multiple_certificate_units']:,}; snapshot candidates that retain multiple historical IDs: {manifest['snapshot_units_with_multiple_historical_certificates']:,}.",f"- Intervention source records refer to {rec_certs:,} distinct certificates.",f"- Ground-truth records: {row_count:,} (expected full scenario × candidate coverage: {cand_count*len(scenarios):,}).", "", "## Oracle coverage", "",f"- Status counts across all scenario-candidate rows: `{json.dumps(statuses,sort_keys=True)}`.",f"- Eligible-set size bands: `{json.dumps(distributions.get('eligible_set_size_band',{}),sort_keys=True)}`.",f"- Sampling strategies: `{json.dumps(strategy_counts,sort_keys=True)}`.","- Ground truth preserves every candidate result, including confirmed failures and unknown eligibility, and includes criterion scores, aggregate score, Pareto flag and rank.","", "## Candidate attribute completeness", "", "Percentages are among the current-state unit snapshot; the source remains certificate-level and unchanged.", "", "| Attribute | Non-null | Null | Non-null % |", "|---|---:|---:|---:|"]
    val_lines += [f"| {f} | {d['nonnull']:,} | {d['null']:,} | {d['nonnull_pct']:.3f}% |" for f,d in completeness.items()]
    val_lines += ["", f"Scenario diversity checks: `{json.dumps(scenario_properties,sort_keys=True)}`. No unknown eligibility occurred in generated hard constraints because those evidence fields are complete in this snapshot; unknown-state behavior is covered by automated unit tests. Cooling energy need is wholly unavailable and excluded from generated preferences.", ""]
    val_lines += ["", f"Selected-current-certificate recommendation coverage: {candidate_rec_coverage[0]:,}/{candidate_rec_coverage[1]:,} ({100*candidate_rec_coverage[0]/candidate_rec_coverage[1]:.2f}%). This is availability of documented recommendations, not evidence of implemented works.", ""]
    val_lines += ["", "## Numerical and coordinate flags", "", f"Measured flags (observations are retained): `{json.dumps(quality,sort_keys=True)}`. Construction-year cutoffs 1800 and 2026 and expiration years after 2040 are review bounds, not proof of an invalid certificate. WGS84 coordinate-range checks are objective format checks; coordinates at (0,0) are reported as suspicious rather than deleted.", "", "Selected candidate-wide distributions (minimum, 10th/25th/50th/75th/90th percentiles, maximum):", "", "```json", json.dumps(numeric_stats,indent=2), "```", ""]
    val_lines += ["", "## Limitations", "", "A unit/parcel is not verified as a physical building. The candidate snapshot applies the source issue/expiration dates as of the fixed snapshot date, but this is not independent legal validation. Completeness and ranking evidence cannot establish public-service eligibility or reuse suitability.",""]
    (root/"benchmark_validation_report.md").write_text("\n".join(val_lines),encoding="utf-8")
    b_lines=["# MURENA-CivicBench Phase 2 design report","","## Scope and candidate unit","",f"The pilot has {cand_count:,} candidates derived from {manifest['original_certificate_count']:,} certificate rows. Each candidate is the latest certificate satisfying issue date <= {manifest['snapshot_as_of_date']} and expiration date >= {manifest['snapshot_as_of_date']}, for a complete nonzero four-part cadastral unit identity. Historical certificate IDs remain attached. {manifest['ambiguous_identity_certificate_count']:,} certificates lack a usable complete unit key; {manifest['identifiable_units_without_current_valid_certificate']:,} identifiable units have no certificate meeting the snapshot date rule. Those records remain in the Phase 1 raw data.","", "A cadastral unit is not a building-level truth label. Parcels may contain multiple structures; unit records may cover only part of a structure. Candidate attributes therefore support only preliminary certificate-based retrieval and comparison. Non-numeric cadastral components are retained exactly and flagged rather than collapsed or guessed.","","## Use-case ontology","", "`use_case_catalog.yaml` defines eight public-interest destinations. Observable screening proxies include unit area, source use codes, construction period, energy class and indicators, service-system presence, coordinates and municipality. Unsupported factors include ownership, availability, accessibility compliance, safety, permits, costs, capacity and territorial need. No scenario label claims regulatory or functional suitability.","","## Scenarios and sampling","",f"The fixed-seed pilot has {len(scenarios)} structured scenarios. Strategy counts: `{json.dumps(strategy_counts,sort_keys=True)}`. Use cases are approximately balanced: `{json.dumps(gen['use_case_counts'],sort_keys=True)}`. A samples documented experimental thresholds/categories independently of a target building; B samples empirical whole-universe quantiles to create informative boundaries. The generator reports duplicate-semantic rejections and deterministic resampling attempts in `scenario_generation_report.json`.","","Difficulty bands are computed from oracle candidate counts: none (0), scarce (1–100), moderate (101–10,000), broad (>10,000). These bands are descriptive protocol choices, not normative building requirements. Scenario definitions and measured bands are stored in `benchmark_scenarios.jsonl` and `benchmark_summaries.json`.","","## Independent deterministic oracle","","The oracle is implemented in `core.py` and does not import or mirror MURENA production ranking. It receives a fixed, versioned scoring configuration (`oracle_config.json`). Hard-constraint conjunction follows three-valued logic: any known failure makes a candidate ineligible; otherwise any missing required value makes it unknown; otherwise it is eligible. Unknowns remain a separate outcome. Only confirmed eligible candidates are ranked. Oracle-v1.1 uses fixed clipped bounds at the candidate snapshot's 1st/99th percentiles, independent of each scenario's filtered set; positive weights sum to one. Missing preference evidence yields a null aggregate instead of silently changing weights. Ties use candidate ID. Pareto flags are calculated on normalized criterion scores; ties remain alternatives.","","The oracle ground truth is a candidate-by-scenario table, not a single winning property. It records eligibility, failure/missing reasons, criterion scores, aggregate score, rank, and Pareto status. Benchmark labels describe deterministic agreement with the declared observed-attribute criteria, not observed outcomes or real-world suitability.","","## Leakage prevention","","`benchmark_splits.json` contains separate scenario partitions, candidate partitions grouped by municipality+sheet+parcel, and a deterministic geographic holdout. Grouping all units on a parcel is conservative against related unit leakage but can combine distinct buildings; missing/incomplete identifiers cannot be linked and are omitted from the candidate universe. Scenario partitioning alone is not sufficient: final evaluation should also hold candidate groups/geographies apart and keep the final test partition away from prompt and scoring development. This local reproducibility pack stores all scenario labels and ground truth, including test assignments; it is not a hidden test release. Withhold test scenarios and labels in any external evaluation service.","","## Evaluation recommendations","","Phase 2 supports testing structured constraint satisfaction (including unknown handling), candidate coverage, ranking agreement (e.g. Spearman/Kendall on fixed eligible sets), top-k utility under the oracle's declared criteria, and Pareto-front recovery. Report coverage alongside rank metrics so systems are not rewarded for silently dropping unknowns. Use candidate-set and geography holdouts. Do not claim functional suitability or task success from APE agreement alone.","","## Limitations and next phase","","APE certificates are not a random sample of all buildings. These records generally describe certified units, not necessarily reusable whole buildings. Coordinates are original XML values and not a verified accessibility measure. Current recommendations express estimated reachable performance, not completed works. Phase 3 should prioritize linking reliable building footprints/entrances, ownership and vacancy/availability, accessibility and safety evidence, use permits/zoning, retrofit cost/compatibility, and territorial population/service demand. Any later synthetic attributes should be separated from observed APE candidates, explicitly labeled, and used only for disclosed stress tests where empirical support is sparse. Do not combine synthetic buildings with empirical ground truth.", ""]
    (root/"benchmark_design_report.md").write_text("\n".join(b_lines),encoding="utf-8")
    return report
