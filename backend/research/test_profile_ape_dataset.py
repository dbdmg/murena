import duckdb
import json

from backend.research.profile_ape_dataset import profile_one, profile_raw_research, wilson


def test_wilson_interval_is_bounded_and_handles_empty():
    assert wilson(0, 0) is None
    interval = wilson(5, 10)
    assert interval is not None
    assert 0 <= interval[0] < 0.5 < interval[1] <= 1


def test_profile_parquet_schema_and_cadastral_nulls(tmp_path):
    parquet = tmp_path / "tiny.parquet"
    con = duckdb.connect()
    con.execute("""copy (select * from (values
        ('L219', '001', '2', '3', 65.0, 1980, 'C', 120.0, date '2020-01-02', false),
        ('L219', NULL, '2', NULL, NULL, 0, NULL, NULL, NULL, false),
        ('L219', '001', '2', '0', 70.0, 1980, 'C', 100.0, date '2020-01-02', true)
    ) as t(comune_code,cadastral_sheet,cadastral_parcel,cadastral_subaltern,surface_area,construction_period,energy_class,epglnren,effective_date,is_meta_estate)) to ? (format parquet)""", [str(parquet)])
    con.close()

    profile, dictionary = profile_one(parquet, "fixture", tmp_path, None, 17)
    assert profile["rows_in_file"] == 3
    assert profile["attribute_profiles"]["surface_area"]["null"] == 1
    assert profile["anomalies"]["missing_cadastral_key"]["count"] == 1
    assert profile["identity"]["metaestate_rows"] == 1
    assert profile["canonical_attribute_availability"]["xml_schema_version"]["physical_column"] is None
    assert any(row["name"] == "surface_area" and row["null"] == 1 for row in dictionary)


def test_reservoir_sample_is_reproducible(tmp_path):
    parquet = tmp_path / "many.parquet"
    con = duckdb.connect()
    con.execute("copy (select i as surface_area from range(1000) t(i)) to ? (format parquet)", [str(parquet)])
    con.close()
    p1, _ = profile_one(parquet, "one", tmp_path, 50, 99)
    p2, _ = profile_one(parquet, "two", tmp_path, 50, 99)
    assert p1["rows_profiled"] == p2["rows_profiled"] == 50
    assert p1["attribute_profiles"]["surface_area"]["median"] == p2["attribute_profiles"]["surface_area"]["median"]


def test_raw_completeness_surface_and_candidate_analyses(tmp_path):
    raw=tmp_path/"ape_raw.parquet"; rec=tmp_path/"ape_recommendations.parquet"
    con=duckdb.connect()
    con.execute("""copy (select * from (values
      ('a','A','1','2','3',100.0,1980,'0','1','D',100.0,20.0,10.0,45.0,7.0,'Town','2020-01-01'),
      ('b','A','1','2','4',200.0,2000,'0','1','C',70.0,15.0,8.0,45.1,7.1,'Town','2021-01-01'),
      ('c',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)
    ) t(source_record_id,cadastral_municipality,cadastral_sheet,cadastral_parcel,cadastral_subaltern,heated_usable_surface,construction_year,dpr412_class_code,attestation_object_code,energy_class,epglnren,epglren,co2_emissions,xml_latitude,xml_longitude,municipality,issue_date)) to ? (format parquet)""",[str(raw)])
    con.execute("""copy (select * from (values
      ('a',50.0,'B','I1',5.0,'A',55.0),('a',60.0,'C','I2',10.0,'A',55.0),
      ('b',NULL,NULL,'I1',NULL,'C',NULL)
    ) t(source_record_id,reachable_epglnren,reachable_energy_class,intervention_code,payback_period_years,overall_reachable_energy_class,overall_reachable_epglnren)) to ? (format parquet)""",[str(rec)])
    con.close()
    config=tmp_path/"constraints.json"
    config.write_text(json.dumps({"scenarios":[
      {"scenario":"large","constraints":[{"field":"heated_usable_surface","op":"gte","value":100}]},
      {"scenario":"empty","constraints":[{"field":"heated_usable_surface","op":"gte","value":1000}]},
      {"scenario":"recommended","constraints":[{"field":"has_recommendation","op":"eq","value":True}]}
    ]}))
    result=profile_raw_research(raw,rec,tmp_path,seed=11,constraint_config=config)
    assert result["rows_profiled"]==3
    assert result["recommendation_rows_profiled"]==3
    assert result["recommendation_analysis"]["certificates_with_recommendations"]==2
    assert result["recommendation_analysis"]["recommendation_coverage_pct"]==100*2/3
    assert result["recommendation_analysis"]["individual_potential_reduction"]["n_valid_intervention_or_certificate_rows"]==2
    assert result["recommendation_analysis"]["overall_potential_reduction"]["n_valid_certificates"]==1
    assert result["recommendation_analysis"]["payback_summary"]["median"]==7.5
    identity=result["cadastral_identity_analysis"]
    assert identity["unique_cadastral_units"]==2
    assert identity["unique_cadastral_parcels"]==1
    assert identity["parcels_with_multiple_dpr412_codes"]==0
    assert next(x for x in result["completeness_bundles"] if x["bundle"]=="basic_retrieval" and x["grouping"]=="all")["n_complete"]==2
    assert next(x for x in result["completeness_bundles"] if x["bundle"]=="retrofit_evaluation" and x["grouping"]=="all")["n_complete"]==1
    candidates={x["scenario"]:x for x in result["candidate_scenarios"]}
    assert candidates["large"]["eligible_certificates"]==2
    assert candidates["empty"]["eligible_certificates"]==0
    assert candidates["recommended"]["eligible_certificates"]==2
    assert (tmp_path/"surface_distribution_by_group.csv").exists()
    assert (tmp_path/"joint_attribute_completeness.csv").exists()
    assert (tmp_path/"candidate_availability.csv").exists()
    assert (tmp_path/"recommendation_analysis.csv").exists()
    assert (tmp_path/"figures"/"raw_surface_median_by_dpr412.svg").exists()
    assert (tmp_path/"figures"/"raw_joint_attribute_completeness.svg").exists()
    assert (tmp_path/"figures"/"raw_candidate_availability.svg").exists()
