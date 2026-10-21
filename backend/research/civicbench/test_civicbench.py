import json
import pandas as pd
import unittest
from copy import deepcopy

from .core import VERSION, build_candidates, evaluate_scenario, validate_scenario, run_benchmark
from .generate import generate_scenarios

def scenario(constraints=None, preferences=None, sid="CB-A-0001"):
    return {"scenario_id":sid,"use_case_id":"social_community_center","candidate_universe_version":VERSION,"scoring_config_version":"oracle-v1.1",
      "geographic_scope":{"type":"all","value":None},"hard_constraints":constraints or [],"preferences":preferences or [],
      "missing_value_policy":"include_unknown_separately","normalization_method":"fixed_bounds_clipped_minmax_v1",
      "expected_behavior":{},"generation_metadata":{"strategy":"A_distribution_independent","seed":1,"difficulty":"test"}}

def candidates():
    return pd.DataFrame({"candidate_id":["u1","u2","u3"],"heated_usable_surface":[100.,None,200.],"epglnren":[100.,50.,200.],
      "energy_class":["C","A1","G"],"construction_year":[1980.,2000.,None],"dpr412_class_code":["1","2","1"],
      "istat_code":["001001","001001","001002"]})

class CivicBenchTests(unittest.TestCase):
 def test_three_valued_constraint_missing_not_zero(self):
    s=scenario([{"constraint_id":"surface","attribute":"heated_usable_surface","operator":"gte","value":50,"unit":"m2","source":"test","missing_behavior":"unknown"}])
    out,meta=evaluate_scenario(s,candidates())
    self.assertEqual(list(out.eligibility_status),["eligible","unknown","eligible"])
    self.assertEqual(meta["eligible_count"],2); self.assertEqual(meta["unknown_count"],1)

 def test_near_constraint_boundary_is_measured_against_fixed_span(self):
    c=candidates()
    s=scenario([{"constraint_id":"surface","attribute":"heated_usable_surface","operator":"gte","value":100,"unit":"m2","source":"test","missing_behavior":"unknown"}])
    _,meta=evaluate_scenario(s,c)
    self.assertGreaterEqual(meta["near_threshold_candidate_count"],1)

 def test_add_constraint_never_increases_confirmed_eligibility(self):
    c=candidates()
    one={"constraint_id":"s","attribute":"heated_usable_surface","operator":"gte","value":50,"unit":"m2","source":"test","missing_behavior":"unknown"}
    two={"constraint_id":"e","attribute":"epglnren","operator":"lte","value":150,"unit":None,"source":"test","missing_behavior":"unknown"}
    a,_=evaluate_scenario(scenario([one]),c); b,_=evaluate_scenario(scenario([one,two]),c)
    self.assertLessEqual((b.eligibility_status=="eligible").sum(),(a.eligibility_status=="eligible").sum())

 def test_ranking_direction_and_stable_tie_break(self):
    c=candidates().iloc[[2,0]].reset_index(drop=True)
    s=scenario(preferences=[{"attribute":"epglnren","direction":"minimize","weight":1.0,"normalization":"fixed_bounds_clipped_minmax_v1"}])
    a,meta=evaluate_scenario(s,c); b,meta2=evaluate_scenario(s,c.iloc[::-1].reset_index(drop=True))
    self.assertEqual(meta["top_k"][0],"u1"); self.assertEqual(meta["top_k"],meta2["top_k"])

 def test_versioned_scoring_configuration_is_explicit(self):
    from .core import DEFAULT_SCORING_CONFIG
    s=scenario(preferences=[{"attribute":"epglnren","direction":"minimize","weight":1.0,"normalization":"fixed_bounds_clipped_minmax_v1"}])
    alternate=deepcopy(DEFAULT_SCORING_CONFIG); alternate["bounds"]["epglnren"]=[0,1000]
    base,_=evaluate_scenario(s,candidates(),scoring_config=DEFAULT_SCORING_CONFIG)
    changed,_=evaluate_scenario(s,candidates(),scoring_config=alternate)
    self.assertNotEqual(base.loc[0,"score_epglnren"],changed.loc[0,"score_epglnren"])
    alternate["version"]="oracle-v1.2"
    with self.assertRaises(ValueError): evaluate_scenario(s,candidates(),scoring_config=alternate)

 def test_rejects_unsupported_and_bad_weights(self):
    with self.assertRaises(ValueError): validate_scenario(scenario([{"constraint_id":"x","attribute":"sql","operator":"eq","value":1,"unit":None,"source":"test","missing_behavior":"unknown"}]))
    s=scenario(preferences=[{"attribute":"epglnren","direction":"minimize","weight":.8,"normalization":"fixed_bounds_clipped_minmax_v1"}])
    with self.assertRaises(ValueError): validate_scenario(s)

 def test_equivalent_constraints_empty_results_and_irrelevant_metadata(self):
    c=candidates()
    a=scenario([{"constraint_id":"surface","attribute":"heated_usable_surface","operator":"gte","value":5000,"unit":"m2","source":"test","missing_behavior":"unknown"}])
    b=scenario([{"constraint_id":"surface2","attribute":"heated_usable_surface","operator":"gte","value":5000,"unit":"m2","source":"test","missing_behavior":"unknown"}])
    x,m=evaluate_scenario(a,c); y,n=evaluate_scenario(b,c)
    self.assertEqual(m["eligible_count"],0); self.assertEqual(x.eligibility_status.tolist(),y.eligibility_status.tolist())
    a["generation_metadata"]["note"]="irrelevant"; z,_=evaluate_scenario(a,c)
    self.assertEqual(x.eligibility_status.tolist(),z.eligibility_status.tolist())

 def test_preference_monotonicity_and_pareto_ties(self):
    c=pd.DataFrame({"candidate_id":["a","b","c"],"heated_usable_surface":[100.,100.,200.],"epglnren":[100.,100.,400.]})
    s=scenario(preferences=[{"attribute":"heated_usable_surface","direction":"maximize","weight":.5,"normalization":"fixed_bounds_clipped_minmax_v1"},{"attribute":"epglnren","direction":"minimize","weight":.5,"normalization":"fixed_bounds_clipped_minmax_v1"}])
    r,_=evaluate_scenario(s,c)
    self.assertTrue(bool(r.loc[r.candidate_id.isin(["a","b"]),"pareto_optimal"].all()))
    self.assertTrue(bool(r.loc[r.candidate_id=="c","pareto_optimal"].iloc[0]))
    self.assertGreater(r.loc[r.candidate_id=="c","score_heated_usable_surface"].iloc[0],r.loc[r.candidate_id=="a","score_heated_usable_surface"].iloc[0])

 def test_incremental_parquet_schema_stable_across_scenarios(self):
    import tempfile
    from pathlib import Path
    d=Path(tempfile.mkdtemp()); cp=d/"c.parquet"; sp=d/"s.jsonl"
    c=candidates(); c.to_parquet(cp,index=False)
    s1=scenario(preferences=[{"attribute":"epglnren","direction":"minimize","weight":1.0,"normalization":"fixed_bounds_clipped_minmax_v1"}],sid="CB-A-0001")
    s2=scenario(preferences=[{"attribute":"heated_usable_surface","direction":"maximize","weight":1.0,"normalization":"fixed_bounds_clipped_minmax_v1"}],sid="CB-A-0002")
    sp.write_text("\n".join(json.dumps(x) for x in [s1,s2]))
    summaries=run_benchmark(cp,sp,d)
    out=pd.read_parquet(d/"benchmark_ground_truth.parquet")
    self.assertEqual(len(summaries),2); self.assertEqual(len(out),6)
    self.assertIn("score_epglnren",out.columns); self.assertIn("score_heated_usable_surface",out.columns)
    self.assertFalse((d/"benchmark_ground_truth.parquet.partial").exists())

 def test_generator_is_seeded_and_excludes_unobserved_preference_fields(self):
    import tempfile
    from pathlib import Path
    d=Path(tempfile.mkdtemp()); cp=d/"c.parquet"
    c=pd.DataFrame({"heated_usable_surface":[40.,60.,80.,100.],"construction_year":[1950.,1960.,1980.,2000.],"energy_class":["C","D","E","F"],"epglnren":[100.,150.,200.,250.],"co2_emissions":[20.,30.,40.,50.],"heating_energy_need":[50.,60.,70.,80.],"cooling_energy_need":[None]*4,"dpr412_class_code":["1","2","3","4"],"istat_code":["001001"]*4})
    c.to_parquet(cp,index=False)
    p1=d/"one.jsonl"; p2=d/"two.jsonl"
    generate_scenarios(cp,p1,count=4,seed=23); generate_scenarios(cp,p2,count=4,seed=23)
    self.assertEqual(p1.read_text(),p2.read_text())
    scenarios=[json.loads(x) for x in p1.read_text().splitlines()]
    self.assertEqual(len({x["scenario_id"] for x in scenarios}),4)
    self.assertTrue(all(all(p["attribute"]!="cooling_energy_need" for p in s["preferences"]) for s in scenarios))

 def test_candidate_snapshot_keeps_history_and_excludes_incomplete(self):
    import tempfile
    from pathlib import Path
    tmp_path=Path(tempfile.mkdtemp())
    old={"source_record_id":"old","source_filename":"a.xml","source_sha256":"x","parse_status":"ok","ape_id":"1","xml_schema_version":"12","issue_date":"2020-01-01","expiration_date":"2030-01-01","cadastral_municipality":"A","cadastral_sheet":"001","cadastral_parcel":"002","cadastral_subaltern":"003","address":None,"municipality":"Town","istat_code":"001001","xml_latitude":None,"xml_longitude":None,"construction_year":1980,"building_typology_code":None,"dpr412_class_code":"0","attestation_object_code":"1","number_real_estate_units":1,"floor":None,"heated_usable_surface":50,"cooled_usable_surface":None,"heated_volume":None,"climate_zone":None,"energy_class":"C","epglnren":100,"epglren":None,"co2_emissions":None,"heating_energy_need":None,"cooling_energy_need":None,"envelope_winter_quality_code":None,"envelope_summer_quality_code":None,"main_energy_carrier":None,"heating_system_code":None,"dhw_system_code":None,"heating_service_present":None,"cooling_service_present":None}
    frame=pd.DataFrame([
      old,
      {"source_record_id":"new","source_filename":"b.xml","source_sha256":"y","parse_status":"ok","ape_id":"2","xml_schema_version":"12","issue_date":"2022-01-01","expiration_date":"2032-01-01","cadastral_municipality":"A","cadastral_sheet":"001","cadastral_parcel":"002","cadastral_subaltern":"003","address":None,"municipality":"Town","istat_code":"001001","xml_latitude":None,"xml_longitude":None,"construction_year":1980,"building_typology_code":None,"dpr412_class_code":"0","attestation_object_code":"1","number_real_estate_units":1,"floor":None,"heated_usable_surface":55,"cooled_usable_surface":None,"heated_volume":None,"climate_zone":None,"energy_class":"C","epglnren":90,"epglren":None,"co2_emissions":None,"heating_energy_need":None,"cooling_energy_need":None,"envelope_winter_quality_code":None,"envelope_summer_quality_code":None,"main_energy_carrier":None,"heating_system_code":None,"dhw_system_code":None,"heating_service_present":None,"cooling_service_present":None},
      {**old,"source_record_id":"expired","source_filename":"expired.xml","issue_date":"2024-01-01","expiration_date":"2025-01-01"},
      {**old,"source_record_id":"incomplete","source_filename":"c.xml","issue_date":"2023-01-01","cadastral_subaltern":None}
    ])
    for name in ["source_encoding_declared","source_encoding_used","potentially_lossy","source_repaired_byte_count","parser_warning_count"]:
        frame[name]=None
    src=tmp_path/"raw.parquet"; dst=tmp_path/"candidate.parquet"; frame.to_parquet(src,index=False)
    m=build_candidates(src,dst); out=pd.read_parquet(dst)
    self.assertEqual(len(out),1); self.assertEqual(out.iloc[0].selected_source_record_id,"new")
    self.assertEqual(json.loads(out.iloc[0].historical_source_record_ids),["expired","new","old"])
    self.assertEqual(m["snapshot_candidate_count"],1)
    self.assertEqual(m["excluded_certificates_by_reason"]["incomplete_or_zero_cadastral_identity"],1)
    self.assertEqual(m["excluded_certificates_by_reason"]["expired_complete_key_certificates"],1)
    reversed_src=tmp_path/"raw_reversed.parquet"; reversed_dst=tmp_path/"candidate_reversed.parquet"
    frame.iloc[::-1].to_parquet(reversed_src,index=False); build_candidates(reversed_src,reversed_dst)
    reversed_out=pd.read_parquet(reversed_dst)
    self.assertEqual(out.candidate_id.tolist(),reversed_out.candidate_id.tolist())

if __name__ == "__main__": unittest.main()
