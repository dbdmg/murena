from pathlib import Path
import json
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.metadata.ape_extraction import APEParseError, parse_ape_xml, extract_directory
from data.metadata.create_estate_dataset import (
    deduplicate_cadastral_units,
    generate_metaestates,
    is_single_physical_building_group,
    apply_application_scoring,
    select_coordinates,
)

XML = '''<?xml version="1.0" encoding="UTF-8"?>
<documento xmlns="http://www.csi.it/sicee/siceeweb/xml/xmlapecompleto2015/data">
 <ape2015><info><versione>12.00</versione></info>
 <datiAttestato><codiceIdentificativo>APE-001</codiceIdentificativo><dataScadenza>2030-01-01</dataScadenza></datiAttestato>
 <datiGenerali><classificazioneDPR412>0</classificazioneDPR412><oggettoAttestato>1</oggettoAttestato><numeroUnitaImmobiliari>2</numeroUnitaImmobiliari>
  <serviziEnergeticiPresenti><climatizzazioneInvernale>1</climatizzazioneInvernale><produzioneAcquaCaldaSanitaria>0</produzioneAcquaCaldaSanitaria><climatizzazioneEstiva>true</climatizzazioneEstiva></serviziEnergeticiPresenti>
  <datiIdentificativi><annoCostruzione>1965</annoCostruzione><superficieUtileRiscaldata>80.5</superficieUtileRiscaldata></datiIdentificativi>
  <datiCatastali><codiceCatastale>L219</codiceCatastale><foglio>003</foglio><particella>0123</particella><subalterni><subDA>0007</subDA></subalterni></datiCatastali>
  <datiExtra><tipologiaEdilizia>2</tipologiaEdilizia></datiExtra></datiGenerali>
 <prestazioneGlobale><prestazioneEnergeticaFabbricato><inverno>2</inverno></prestazioneEnergeticaFabbricato><prestazioneEnergeticaGlobale><classificazione><classeEnergetica>D</classeEnergetica><epglnren>66.88</epglnren></classificazione></prestazioneEnergeticaGlobale></prestazioneGlobale>
 <prestazioneImpianti><gasNaturale><consumoAnnuo>100</consumoAnnuo></gasNaturale><epglren>1.76</epglren><emissioniCO2>13.35</emissioniCO2></prestazioneImpianti>
 <datiFabbricato><volumeRiscaldato>143.18</volumeRiscaldato><ephnd>34</ephnd></datiFabbricato>
 <datiImpianti><climatizzazioneInvernale><impianto><tipoImpianto>1</tipoImpianto><descrizioneImpianto>caldaia</descrizioneImpianto><annoInstallazione>2014</annoInstallazione><potenzaNominale>24</potenzaNominale></impianto></climatizzazioneInvernale></datiImpianti>
 <raccomandazioni><interventoRaccomandato><codice>0</codice><tipoInterventoRaccomandato>Cappotto</tipoInterventoRaccomandato><ristrutturazioneImportante>0</ristrutturazioneImportante><tempoRitornoInvestimento>9</tempoRitornoInvestimento><classificazioneRaggiungibile><classeEnergetica>C</classeEnergetica><epglnren>50.2</epglnren></classificazioneRaggiungibile></interventoRaccomandato><interventoRaccomandato><codice>1</codice><tipoInterventoRaccomandato>Serramenti</tipoInterventoRaccomandato></interventoRaccomandato><classificazione><classeEnergetica>D</classeEnergetica><epglnren>58.76</epglnren></classificazione></raccomandazioni>
 <datiCalcolo><info><versione>5.00</versione></info><datiGenerali><codiceISTAT>001272</codiceISTAT><comune>Torino</comune><indirizzo>Corso Giulio Cesare</indirizzo><civico>171 BIS</civico><zonaClimatica>E</zonaClimatica><latitudineGIS>45.1</latitudineGIS><longitudineGIS>7.6</longitudineGIS></datiGenerali></datiCalcolo>
 </ape2015></documento>'''


def test_extracts_actual_ape_paths_boolean_cadastral_and_recommendations(tmp_path):
    p = tmp_path / "sample.xml"
    p.write_text(XML, encoding="utf-8")
    raw, recs = parse_ape_xml(p)
    assert raw["address"] == "Corso Giulio Cesare"
    assert raw["xml_latitude"] == 45.1 and raw["xml_longitude"] == 7.6
    assert raw["municipality"] == "Torino" and raw["istat_code"] == "001272"
    assert raw["cadastral_sheet"] == "003" and raw["cadastral_parcel"] == "0123"
    assert raw["cadastral_subaltern"] == "0007"
    assert raw["heating_service_present"] is True
    assert raw["dhw_service_present"] is False
    assert raw["energy_class"] == "D" and raw["epglnren"] == 66.88
    assert raw["construction_year"] == 1965
    assert [r["intervention_code"] for r in recs] == ["0", "1"]
    assert recs[0]["reachable_energy_class"] == "C"
    assert recs[0]["overall_reachable_energy_class"] == "D"
    assert recs[1]["reachable_energy_class"] is None


def test_namespace_independent_and_missing_optional_elements(tmp_path):
    p = tmp_path / "no-ns.xml"
    p.write_text(XML.replace(' xmlns="http://www.csi.it/sicee/siceeweb/xml/xmlapecompleto2015/data"', ''), encoding="utf-8")
    raw, recs = parse_ape_xml(p)
    assert raw["ape_id"] == "APE-001"
    assert raw["cooling_energy_need"] is None


def test_malformed_and_invalid_encoding_are_explicit_failures(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<documento><", encoding="utf-8")
    with pytest.raises(APEParseError): parse_ape_xml(p)
    p.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?><documento>\xff</documento>')
    with pytest.raises(APEParseError): parse_ape_xml(p)


def test_cp1252_recovery_is_strict_reversible_and_provenanced(tmp_path):
    p = tmp_path / "cp1252.xml"
    text = XML.replace("caldaia", "caldaia è m³")
    payload=text.encode("utf-8").replace("è".encode("utf-8"),b"\xe8")
    p.write_bytes(payload)
    raw, _ = parse_ape_xml(p)
    assert raw["parse_status"] == "normalized_utf8_cp1252_bytes_inferred"
    assert raw["source_encoding_declared"] == "UTF-8"
    assert "CP1252 mapping" in raw["source_encoding_used"]
    assert raw["potentially_lossy"] is False
    assert raw["heating_system_description"] == "caldaia è m³"
    assert raw["source_repaired_byte_count"] == 1
    assert raw["source_sha256"] and len(raw["source_sha256"]) == 64


def test_stable_source_identifier_and_bounded_batch_parquet_schema(tmp_path):
    source, out = tmp_path / "xml", tmp_path / "out"
    source.mkdir()
    (source / "b.xml").write_text(XML, encoding="utf-8")
    (source / "a.xml").write_text(XML, encoding="utf-8")
    report = extract_directory(source, out, batch_size=1)
    assert report["successfully_parsed"] == 2
    raw = pd.read_parquet(out / "ape_raw.parquet")
    recs = pd.read_parquet(out / "ape_recommendations.parquet")
    assert list(raw.columns)[0:4] == ["source_filename", "source_record_id", "source_sha256", "parse_status"]
    again, _ = parse_ape_xml(source / "a.xml")
    assert raw["source_record_id"].iloc[0] == again["source_record_id"]
    assert raw["source_record_id"].iloc[0] != raw["source_record_id"].iloc[1]
    assert str(raw["cadastral_sheet"].dtype) == "string"
    assert str(raw["potentially_lossy"].dtype) == "boolean"
    assert str(raw["parser_warning_count"].dtype) == "Int64"
    assert len(recs) == 4
    assert json.loads((out / "ape_data_quality_report.json").read_text())["recommendation_rows"] == 4
    assert report["duplicate_certificate_identifiers"] == {"APE-001": 2}


def test_empty_or_missing_cadastral_values_are_not_zero(tmp_path):
    p = tmp_path / "sample.xml"
    p.write_text(XML.replace("<foglio>003</foglio><particella>0123</particella>", ""), encoding="utf-8")
    raw, _ = parse_ape_xml(p)
    assert raw["cadastral_sheet"] is None and raw["cadastral_parcel"] is None


def test_extraction_resumes_from_manifest_without_duplicate_rows(tmp_path):
    source, out = tmp_path / "xml", tmp_path / "out"
    source.mkdir()
    (source / "a.xml").write_text(XML, encoding="utf-8")
    (source / "b.xml").write_text(XML, encoding="utf-8")
    first = extract_directory(source, out, batch_size=1, limit=1)
    assert first["successfully_parsed"] == 1
    second = extract_directory(source, out, batch_size=1)
    assert second["successfully_parsed"] == 2
    third = extract_directory(source, out, batch_size=1)
    assert third["successfully_parsed"] == 2
    assert len(pd.read_parquet(out / "ape_raw.parquet")) == 2


def test_coordinate_selection_preserves_valid_xml_and_marks_geocode_fill():
    osm = {"lat": 44.0, "lon": 7.0, "score": 250, "confidence": "medium", "provenance": "osm_address"}
    assert select_coordinates(45.0, 8.0, osm) == (45.0, 8.0, "xml", None)
    assert select_coordinates(None, None, osm) == (44.0, 7.0, "osm_address", "medium")
    weak = {**osm, "score": 100}
    assert select_coordinates(None, None, weak) == (None, None, None, None)


def test_cadastral_dedup_keeps_null_keys_and_uses_municipality_and_latest_date():
    frame = pd.DataFrame([
        {"comune_code": "A", "cadastral_sheet": 1, "cadastral_parcel": 2, "cadastral_subaltern": 3, "effective_date": "2020-01-01", "id": "old"},
        {"comune_code": "A", "cadastral_sheet": 1, "cadastral_parcel": 2, "cadastral_subaltern": 3, "effective_date": "2022-01-01", "id": "new"},
        {"comune_code": "B", "cadastral_sheet": 1, "cadastral_parcel": 2, "cadastral_subaltern": 3, "effective_date": "2021-01-01", "id": "other_municipality"},
        {"comune_code": "A", "cadastral_sheet": None, "cadastral_parcel": 2, "cadastral_subaltern": 4, "effective_date": "2021-01-01", "id": "missing_one"},
        {"comune_code": "A", "cadastral_sheet": None, "cadastral_parcel": 2, "cadastral_subaltern": 4, "effective_date": "2022-01-01", "id": "missing_two"},
    ])
    result = deduplicate_cadastral_units(frame)
    assert set(result["id"]) == {"new", "other_municipality", "missing_one", "missing_two"}


def test_metaestate_requires_same_address_and_close_coordinates():
    units = pd.DataFrame([
        {"address": "Via Roma 1", "latitude": 45.0, "longitude": 7.0},
        {"address": "VIA ROMA, 1", "latitude": 45.00001, "longitude": 7.00001},
    ])
    assert is_single_physical_building_group(units)
    assert not is_single_physical_building_group(pd.concat([units, pd.DataFrame([{"address": "Via Verdi 3", "latitude": 45.0, "longitude": 7.0}])], ignore_index=True))
    assert not is_single_physical_building_group(units.assign(latitude=[45.0, 45.01]))


def test_metaestate_preserves_constituents_and_uses_weighted_estimates():
    units = pd.DataFrame([
        {"comune_code": "A", "cadastral_sheet": 1, "cadastral_parcel": 2, "cadastral_subaltern": 1,
         "address": "Via Roma 1", "latitude": 45.0, "longitude": 7.0, "surface_area": 100.0,
         "epglnren": 100.0, "energy_class": "G", "property_type": "0", "construction_period": "1950",
         "id": "1", "is_meta_estate": False, "energy_class_is_estimate": False,
         "aggregation_methods": None, "cadastral_units_count": 1, "id_list": None,
         "ape_file_list": "['a.xml']", "ape_file_list_filtered": "['a.xml']", "ape_file_list_filtered_parsed": "['a.xml']"},
        {"comune_code": "A", "cadastral_sheet": 1, "cadastral_parcel": 2, "cadastral_subaltern": 2,
         "address": "VIA ROMA 1", "latitude": 45.00001, "longitude": 7.00001, "surface_area": 300.0,
         "epglnren": 40.0, "energy_class": "C", "property_type": "1", "construction_period": "1960",
         "id": "2", "is_meta_estate": False, "energy_class_is_estimate": False,
         "aggregation_methods": None, "cadastral_units_count": 1, "id_list": None,
         "ape_file_list": "['b.xml']", "ape_file_list_filtered": "['b.xml']", "ape_file_list_filtered_parsed": "['b.xml']"},
    ])
    result = generate_metaestates(units)
    meta = result[result["is_meta_estate"]].iloc[0]
    assert meta["id_list"] == "['1', '2']"
    assert meta["energy_class_is_estimate"]
    assert meta["epglnren"] == pytest.approx(55.0)
    methods = json.loads(meta["aggregation_methods"])
    assert methods["epglnren"] == "surface_weighted_mean_estimate"
    assert methods["energy_class"].endswith("not_certified")


def test_legacy_scoring_preserves_existing_scores_when_source_columns_were_exported_away():
    frame = pd.DataFrame([{
        "energy_class": "B", "energy_score_class": 3, "energy_score_plant": 4,
        "energy_score_envelope": 2, "energy_score_renewables": 5,
    }])
    result = apply_application_scoring(frame)
    assert result.loc[0, "energy_score_class"] == 3
    assert result.loc[0, "energy_score_plant"] == 4
    assert result.loc[0, "energy_score_envelope"] == 2
    assert result.loc[0, "energy_score_renewables"] == 5
    assert result.loc[0, "energy_score_total"] == 14
