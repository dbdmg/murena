"""
Data processing functions for population data, POI distances, and APE XML parsing.

This module handles:
- Processing population data for GeoJSON zones
- Calculating POI distances with Haversine
- Parsing APE XML certificates with expert logic
- Extracting images from APE files
"""

import re

from lxml import etree
import numpy as np
import pandas as pd

from app.core.config import settings

MINUTES_PER_KM_WALKING = settings.MINUTES_PER_KM_WALKING

# APE XML parsing constants (from expert slides)
MAPPING_QUALITA_INVOLUCRO = {"0": "Smiling", "1": "Neutral/Amazed", "2": "Sad"}

MAPPING_IMPIANTI = {
    "0": "Standard boiler",
    "1": "Condensing boiler",
    "2": "Stove or fireplace",
    "3": "Electric heating",
    "4": "Heat pump",
    "5": "Heat pump",
    "6": "Heat pump",
    "7": "Heat pump",
    "8": "Heat pump",
    "9": "Heat pump",
    "10": "Heat pump",
    "11": "Heat pump",
    "12": "Heat pump",
    "13": "Heat pump",
    "14": "Heat pump",
    "15": "Heat pump",
    "16": "Solar thermal system",
    "17": "Photovoltaic system",
    "18": "Cogenerator",
    "19": "District heating",
    "32": "Gas water heater",
    "33": "Gas water heater",
    "34": "Heat pump water heater",
    "35": "Heat pump water heater",
    "36": "Electric boiler",
}

VETTORI_XPATHS = {
    "Grid electricity": "//ape:prestazioneImpianti/ape:energiaElettricaRete/ape:consumoAnnuo",
    "Natural gas": "//ape:prestazioneImpianti/ape:gasNaturale/ape:consumoAnnuo",
    "LPG": "//ape:prestazioneImpianti/ape:gpl/ape:consumoAnnuo",
    "Coal": "//ape:prestazioneImpianti/ape:carbone/ape:consumoAnnuo",
    "Diesel": "//ape:prestazioneImpianti/ape:gasolio/ape:consumoAnnuo",
    "Heating oil": "//ape:prestazioneImpianti/ape:olioCombustibile/ape:consumoAnnuo",
    "Solid biomass": "//ape:prestazioneImpianti/ape:biomasseSolide/ape:consumoAnnuo",
    "Liquid biomass": "//ape:prestazioneImpianti/ape:biomasseLiquide/ape:consumoAnnuo",
    "Gaseous biomass": "//ape:prestazioneImpianti/ape:biomasseGassose/ape:consumoAnnuo",
    "Photovoltaic solar": "//ape:prestazioneImpianti/ape:solareFotovoltaico/ape:consumoAnnuo",
    "Thermal solar": "//ape:prestazioneImpianti/ape:solareTermico/ape:consumoAnnuo",
    "Wind": "//ape:prestazioneImpianti/ape:eolico/ape:consumoAnnuo",
    "District heating": "//ape:prestazioneImpianti/ape:teleriscaldamento/ape:consumoAnnuo",
    "District cooling": "//ape:prestazioneImpianti/ape:teleraffrescamento/ape:consumoAnnuo",
}

VETTORI_PCI = {
    "Natural gas": 9.94,
    "LPG": 12.778,
    "Coal": 7.917,
    "Diesel": 11.87,
    "Heating oil": 11.75,
    "Solid biomass": 4.67,
    "Liquid biomass": 7.5,
    "Gaseous biomass": 6.4,
}


def process_population_data(geojson_data, csv_path):
    """
    Loads population data from CSV, cleans it, and joins it with the GeoJSON
    of urbanistic zones using the zone code as key.

    Args:
        geojson_data: GeoJSON features dict
        csv_path: Path to population CSV

    Returns:
        tuple: (updated_geojson_data, age_columns)
    """
    if not geojson_data:
        return None, []

    try:
        df_pop = pd.read_csv(csv_path, sep=",", on_bad_lines="skip", skiprows=2)

        # Check if zona_urbanistica column exists in any form
        zona_col = None
        for col in df_pop.columns:
            col_lower = str(col).lower()
            if (
                "zona" in col_lower and "urban" in col_lower
            ) or col_lower.strip() == "zona urbanistiche old":
                zona_col = col
                break

        if not zona_col:
            print(
                f"Urban zone column not found in CSV. Available columns: {list(df_pop.columns)}"
            )
            return geojson_data, []

        df_pop = df_pop.rename(columns={zona_col: "zona_urbanistica"})

        age_cols = [col for col in df_pop.columns if "-" in col or "+" in col]
        if "zona_urbanistica" not in df_pop.columns or not age_cols:
            return geojson_data, []

        df_pop_clean = df_pop[["zona_urbanistica"] + age_cols].copy()

        df_pop_clean = df_pop_clean[
            ~df_pop_clean["zona_urbanistica"].str.contains(
                "TOTALE|NON LOCALIZZATO", na=False, case=False
            )
        ]

        for col in age_cols:
            df_pop_clean[col] = pd.to_numeric(
                df_pop_clean[col], errors="coerce"
            ).fillna(0)

        df_pop_clean["join_key"] = (
            df_pop_clean["zona_urbanistica"].str.lower().str.strip()
        )

        for feature in geojson_data["features"]:
            props = feature["properties"]
            zona_code = props.get("ZONA_URBANISTICA", "").lower().strip()

            match = df_pop_clean[df_pop_clean["join_key"] == zona_code]
            if not match.empty:
                props["population_data"] = match.iloc[0][age_cols].to_dict()
            else:
                props["population_data"] = {col: 0 for col in age_cols}

        return geojson_data, age_cols
    except Exception as e:
        print(f"ERROR in processing population data: {e}")
        return geojson_data, []


def km_to_walking_minutes(km):
    """Convert kilometers to walking minutes."""
    if pd.isna(km) or km == float("inf"):
        return float("inf")
    return km * MINUTES_PER_KM_WALKING


def calculate_travel_times_df(
    input_df: pd.DataFrame, location_details: list, routing_mode: str = "walk"
) -> pd.DataFrame:
    """
    Calculates the distance in km between each property and selected POIs.
    Uses RoutingService (OSM/Pandana) if available for real distances,
    otherwise falls back to Haversine.
    """
    # from app.services.routing import get_router  # TODO: Implement routing service
    from app.utils.helpers import haversine_km

    # Routing not implemented yet, will use Haversine fallback
    get_router = None

    df_processed = input_df.copy()
    df_processed["poi_riferimento"] = None
    df_processed["distanza_km"] = np.nan
    df_processed["tempo_minuti"] = np.nan  # Added estimated time

    # Ensure coordinates are float
    if "latitudine" in df_processed.columns and "longitudine" in df_processed.columns:
        df_processed["latitudine"] = pd.to_numeric(
            df_processed["latitudine"], errors="coerce"
        )
        df_processed["longitudine"] = pd.to_numeric(
            df_processed["longitudine"], errors="coerce"
        )
    else:
        return df_processed

    if not valid_mask.any():
        return df_processed
 
    # Normalize user-provided POIs (list of [name, lat, lon])
    valid_locations = []
    for loc in location_details or []:
        if not isinstance(loc, (list, tuple)) or len(loc) < 3:
            continue
        try:
            raw_name = loc[0] if len(loc) > 0 else "POI"
            name = str(raw_name).strip() or "POI"
            lat = float(loc[1])
            lon = float(loc[2])
            valid_locations.append((name, lat, lon))
        except (TypeError, ValueError):
            continue

    if not valid_locations:
        return df_processed

    # Routing not implemented yet
    router = None
    # try:
    #     if get_router:
    #         router = get_router(mode=routing_mode)
    # except Exception as e:
    #     print(f"Routing init warning: {e}")

    # Calculation logic:
    # For each POI, we calculate vector distance from ALL properties
    # We maintain the MINIMUM distance for each property to one of the selected POIs

    # Inizializza colonne per il minimo
    min_distances = pd.Series(
        [float("inf")] * len(df_processed), index=df_processed.index
    )
    best_pois = pd.Series([None] * len(df_processed), index=df_processed.index)

    # Valid lat/lon mask
    valid_mask = (
        df_processed["latitudine"].notna() & df_processed["longitudine"].notna()
    )

    if not valid_mask.any():
        return df_processed

    valid_origins = df_processed[valid_mask]

    for name, lat_poi, lon_poi in valid_locations:
        # Calcolo distanze per questo POI
        current_distances = None

        # 1. Routing (metri)
        if router:
            try:
                # Returns meters
                d_meters = router.get_distances_batch(
                    valid_origins["latitudine"],
                    valid_origins["longitudine"],
                    lat_poi,
                    lon_poi,
                )
                # Convert to km
                current_distances = d_meters / 1000.0

                # Replace inf with nan for handling
                current_distances = current_distances.replace(
                    [float("inf"), np.inf], np.nan
                )
            except Exception as e:
                print(f"Routing error for {name}: {e}")

        # 2. Haversine fallback (km) if routing failed or gave NaNs
        if current_distances is None or current_distances.isna().all():
            # Vectorized haversine would be better but keeping simple loop optional or assuming haversine_km is scalar
            # Let's do a simple apply for fallback if needed, or trust the helper.
            # Ideally app.utils.helpers.haversine_km handles scalars. We can vectorize it easily.

            # Vectorized Haversine implementation inline for speed
            R = 6371  # Earth radius in km
            dlat = np.radians(lat_poi - valid_origins["latitudine"])
            dlon = np.radians(lon_poi - valid_origins["longitudine"])
            a = (
                np.sin(dlat / 2) ** 2
                + np.cos(np.radians(valid_origins["latitudine"]))
                * np.cos(np.radians(lat_poi))
                * np.sin(dlon / 2) ** 2
            )
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
            current_distances = R * c

        # Update min distances
        # Align series to original index
        dist_series = pd.Series(current_distances, index=valid_origins.index)

        # Logic to update minimum
        mask_better = dist_series < min_distances[valid_mask]
        # We need to update min_distances where mask_better is true in the valid subset
        # This is a bit tricky with pandas indexing, so we update via assignment
 
        # Use simple updates series
        update_indices = mask_better[mask_better].index
        min_distances.loc[update_indices] = dist_series.loc[update_indices]
        best_pois.loc[update_indices] = name

    # Assign results back
    df_processed["distanza_km"] = min_distances.replace(float("inf"), np.nan)
    df_processed["poi_riferimento"] = best_pois

    # Calculate time
    # Walk: 5km/h -> 12 min/km
    # Drive: Example 30km/h avg city -> 2 min/km
    minutes_per_km = MINUTES_PER_KM_WALKING  # default 12 from config
    if routing_mode == "drive":
        minutes_per_km = 3  # Conservative city estimate including traffic/lights

    df_processed["tempo_minuti"] = df_processed["distanza_km"] * minutes_per_km
    df_processed["tempo_minuti"] = df_processed["tempo_minuti"].round(0)

    df_processed["distanza_km"] = df_processed["distanza_km"].round(2)
    df_processed.sort_values(
        by="distanza_km", ascending=True, inplace=True, na_position="last"
    )

    return df_processed


def parse_ape_xml(xml_text: str) -> dict:
    """
    Updated EPC (APE) parser implementing expert analysis logic.

    Implements:
    - Bug fixes for data extraction
    - Expert logic (quality, simulated services, energy vectors, systems)
    - Top 5 energy vectors extraction

    Args:
        xml_text: XML content as string

    Returns:
        dict: Parsed energy performance data
    """
    ns = {"ape": "http://www.csi.it/sicee/siceeweb/xml/xmlapecompleto2015/data"}
    data = {}

    try:
        root = etree.fromstring(xml_text.encode("utf-8"))

        def sxp(x):
            val = root.xpath(f"string({x})", namespaces=ns)
            return val.strip() if isinstance(val, str) and val.strip() else None

        def xs(paths):
            for p in paths:
                v = sxp(p)
                if v:
                    return v
            return None

        # General data
        data["epc_id"] = sxp("//ape:datiAttestato/ape:codiceIdentificativo")
        data["address"] = xs(
            [
                "//ape:datiGenerali/ape:indirizzo",
                "//ape:datiCalcolo/ape:datiGenerali/ape:indirizzo",
            ]
        )
        data["house_number"] = xs(
            [
                "//ape:datiGenerali/ape:datiIdentificativi/ape:numeroCivico",
                "//ape:datiGenerali/ape:datiIdentificativi/ape:civico",
                "//ape:datiCalcolo/ape:datiGenerali/ape:civico",
            ]
        )
        data["municipality"] = xs(
            [
                "//ape:datiGenerali/ape:datiExtra/ape:comune",
                "//ape:datiCalcolo/ape:datiGenerali/ape:comune",
            ]
        )
        data["climate_zone"] = xs(
            [
                "//ape:datiGenerali/ape:zonaClimatica",
                "//ape:datiCalcolo/ape:datiGenerali/ape:zonaClimatica",
            ]
        )

        data["construction_year"] = xs(
            [
                "//ape:datiGenerali/ape:annoCostruzione",
                "//ape:datiGenerali/ape:datiIdentificativi/ape:annoCostruzione",
            ]
        )

        data["latitude"] = xs(
            [
                "//ape:datiGenerali/ape:LatitudineGIS",
                "//ape:datiCalcolo/ape:datiGenerali/ape:latitudineGIS",
            ]
        )
        data["longitude"] = xs(
            [
                "//ape:datiGenerali/ape:LongitudineGIS",
                "//ape:datiCalcolo/ape:datiGenerali/ape:longitudineGIS",
            ]
        )
        data["surface_area"] = sxp(
            "//ape:datiGenerali/ape:datiIdentificativi/ape:superficieUtileRiscaldata"
        )
        data["emission_date"] = sxp("//ape:dataEmissione")
        data["use_case_code"] = sxp("//ape:datiGenerali/ape:destinazioneUso")
        data["attestation_object_code"] = sxp("//ape:datiGenerali/ape:oggettoAttestato")
        data["building_typology_code"] = sxp("//ape:datiExtra/ape:tipologiaEdilizia")

        data["floor"] = xs(
            [
                "//ape:datiGenerali/ape:piano",
                "//ape:datiFabbricato//ape:piano",
                "string(//*[contains(translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'piano')][1])",
            ]
        )

        # Technical building system data (Nominal Power)
        data["heating_nominal_power"] = sxp(
            "//ape:datiImpianti/ape:climatizzazioneInvernale/ape:impianto/ape:potenzaNominale"
        )
        data["dhw_nominal_power"] = sxp(
            "//ape:datiImpianti/ape:produzioneACS/ape:impianto/ape:potenzaNominale"
        )

        # Building envelope areas
        data["opaque_envelope_area"] = sxp(
            "//ape:fabbricato/ape:altriDatiSintetici/ape:superficieOpacaTotale"
        )
        data["transparent_envelope_area"] = sxp(
            "//ape:fabbricato/ape:altriDatiSintetici/ape:superficieVetrataTotale"
        )

        # Energy needs and limits
        data["heating_energy_need"] = sxp("//ape:datiFabbricato/ape:ephnd")
        data["cooling_energy_need"] = sxp("//ape:datiFabbricato/ape:epcnd")
        data["heating_limit"] = sxp("//ape:datiExtra/ape:ephndLim")
        data["primary_energy_limit"] = sxp("//ape:datiExtra/ape:EPglnrenRifStandard")

        # Assessor information
        data["assessor_name"] = sxp("//ape:soggettoCertificatore/ape:nome")
        data["assessor_surname"] = sxp("//ape:soggettoCertificatore/ape:cognome")

        # Main performance indicators
        data["energy_class"] = sxp(
            "//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:classeEnergetica"
        )
        data["epglnren"] = sxp(
            "//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:epglnren"
        )
        data["energy_class_ref"] = sxp(
            "//ape:prestazioneGlobale/ape:riferimenti/ape:classificazioneNuovi/ape:classeEnergetica"
        )
        data["epglnren_ref"] = sxp(
            "//ape:prestazioneGlobale/ape:riferimenti/ape:classificazioneNuovi/ape:epglnren"
        )
        data["epglren"] = sxp("//ape:prestazioneImpianti/ape:epglren")
        data["co2_emissions"] = sxp("//ape:prestazioneImpianti/ape:emissioniCO2")

        # Energy services (updated logic with 'impiantoSimulato')
        services = []

        if (
            sxp("//ape:datiImpianti/ape:climatizzazioneInvernale/ape:impiantoSimulato")
            is None
        ):
            if (
                sxp(
                    "//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:climatizzazioneInvernale"
                )
                == "true"
            ):
                services.append("Heating")

        if sxp("//ape:datiImpianti/ape:produzioneACS/ape:impiantoSimulato") is None:
            if (
                sxp(
                    "//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:produzioneAcquaCaldaSanitaria"
                )
                == "true"
            ):
                services.append("DHW")

        for tag, label in [
            ("climatizzazioneEstiva", "Cooling"),
            ("ventilazioneMeccanica", "Ventilation"),
            ("illuminazione", "Lighting"),
            ("trasportoPersoneCose", "Lifts/Transport"),
        ]:
            v = sxp(f"//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:{tag}")
            if v and v.lower() == "true":
                services.append(label)

        data["present_services"] = services

        # Main energy vector calculation
        calculated_consumption_kwh = {}

        for name, path in VETTORI_XPATHS.items():
            consumption_str = sxp(path)
            if consumption_str:
                try:
                    consumption_val = float(consumption_str.replace(",", "."))
                    if name in VETTORI_PCI:
                        consumption_val *= VETTORI_PCI[name]
                    calculated_consumption_kwh[name] = consumption_val
                except ValueError:
                    continue

        main_energy_vector = None
        if calculated_consumption_kwh:
            vectors_sorted = sorted(
                calculated_consumption_kwh.items(), key=lambda item: item[1], reverse=True
            )
            positive_vectors = [
                (name, round(val, 2)) for name, val in vectors_sorted if val > 0
            ]

            if positive_vectors:
                main_energy_vector = positive_vectors[0][0]

            data["top_vectors"] = positive_vectors[:5]
        else:
            data["top_vectors"] = []

        data["main_energy_vector"] = main_energy_vector
        data["calculated_consumption_kwh"] = calculated_consumption_kwh

        # Cadastral data
        cat = {
            "cadastral_code": None,
            "section": None,
            "sheet": None,
            "parcel": None,
            "subA": None,
            "subDA": None,
            "subaltern": None,
        }
        nodes = root.xpath(".//ape:datiCatastali", namespaces=ns)
        if nodes:
            n = nodes[0]

            def s(node_x):
                t = n.xpath(f"string({node_x})", namespaces=ns)
                return t.strip() if t and t.strip() else None

            cat["cadastral_code"] = s("ape:codiceCatastale")
            cat["section"] = s("ape:sezione")
            cat["sheet"] = s("ape:foglio")
            cat["parcel"] = s("ape:particella")
            cat["subA"] = s("ape:subalterni/ape:subA")
            cat["subDA"] = s("ape:subalterni/ape:subDA")

            # Try to extract subalterno from identifier
            idf = sxp(
                "//ape:datiGenerali/ape:datiIdentificativi/ape:identificativoCatastale"
            )
            if idf:
                patterns = [
                    r"F\s*(\d+)\s+P\s*(\d+)\s+S\s*(\d+)",
                    r"foglio\s*(\d+).*?part.*?(\d+).*?sub.*?(\d+)",
                    r"(\d{1,5})\s*[/-]\s*(\d{1,6})\s*[/-]\s*(\d{1,4})",
                ]
                for patt in patterns:
                    m = re.search(patt, idf, re.IGNORECASE)
                    if m:
                        cat["sheet"] = cat["sheet"] or m.group(1)
                        cat["parcel"] = cat["parcel"] or m.group(2)
                        cat["subaltern"] = cat["subaltern"] or m.group(3)
                        break

            if (cat["sheet"] or cat["parcel"]) and not cat["cadastral_code"]:
                cc = sxp(".//ape:codiceCatastale")
                if cc:
                    cat["cadastral_code"] = cc
            if cat["subaltern"] and not (cat["subA"] or cat["subDA"]):
                cat["subA"] = cat["subaltern"]
        data.update(cat)

        # Building envelope quality (updated mapping)
        tolower = "translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"

        val_inv = sxp(
            "//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:inverno"
        )
        data["winter_quality_code"] = val_inv
        data["winter_quality"] = MAPPING_QUALITA_INVOLUCRO.get(val_inv, val_inv)

        val_est = sxp(
            "//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:estate"
        )
        data["summer_quality_code"] = val_est
        data["summer_quality"] = MAPPING_QUALITA_INVOLUCRO.get(val_est, val_est)

        # Systems information extraction
        def get_service_info(xpaths_service):
            found_node = None
            for xp in xpaths_service:
                tmp = root.xpath(xp, namespaces=ns)
                if tmp is not None and len(tmp) > 0:
                    found_node = tmp[0]
                    break
            if found_node is None:
                return {
                    "technology": None,
                    "year": None,
                    "description": None,
                    "epnren": None,
                    "system_type_code": None,
                }

            def s(xpath):
                val = found_node.xpath(f"string({xpath})", namespaces=ns)
                return val.strip() if isinstance(val, str) and val.strip() else None

            year = s(
                f".//*[contains({tolower},'install') and contains({tolower},'anno')][1]"
            )
            description = s(".//ape:impianto[1]/ape:descrizioneImpianto")
            epnren = s(".//ape:prestazione/ape:epnren")

            system_type_code = s(".//ape:impianto[1]/ape:tipoImpianto")
            technology = MAPPING_IMPIANTI.get(system_type_code, description)

            if technology is None:
                technology = s(
                    f".//*[contains({tolower},'tecnolog') or contains({tolower},'tipogener') or contains({tolower},'tipo')][1]"
                )

            return {
                "technology": technology,
                "year": year,
                "description": description,
                "epnren": epnren,
                "system_type_code": system_type_code,
            }

        data["systems"] = {
            "Heating": get_service_info(
                [
                    "//ape:datiImpianti//ape:climatizzazioneInvernale",
                    "//ape:impianti//ape:impiantoClimatizzazioneInvernale",
                ]
            ),
            "DHW": get_service_info(
                [
                    "//ape:datiImpianti//ape:produzioneACS",
                    "//ape:impianti//ape:impiantoAcquaCaldaSanitaria",
                ]
            ),
            "Cooling": get_service_info(
                [
                    "//ape:datiImpianti//ape:climatizzazioneEstiva",
                    "//ape:impianti//ape:impiantoClimatizzazioneEstiva",
                ]
            ),
        }

        # Renewable sources
        try:
            val_fv = float(sxp(VETTORI_XPATHS["Solare fotovoltaico"]) or 0)
            val_st = float(sxp(VETTORI_XPATHS["Solare termico"]) or 0)
            if val_fv > 0 or val_st > 0:
                data["renewable_sources"] = "Yes"
            else:
                data["renewable_sources"] = "No"
        except Exception:
            data["renewable_sources"] = "No"

        # Improvements
        data["target_class"] = xs(
            [
                "//ape:raccomandazioni//ape:classificazioneRaggiungibile/ape:classeEnergetica",
                "//ape:prestazioneGlobale//ape:classeEnergeticaRaggiungibile",
                f"string(//*[contains({tolower},'classe') and contains({tolower},'raggiung')][1])",
                f"string(//*[contains({tolower},'classe') and contains({tolower},'miglior')][1])",
            ]
        )

        data["savings_percentage"] = None  # Removed, too unreliable

        data["payback_period"] = sxp(
            "//ape:raccomandazioni//ape:tempoRitornoInvestimento"
        )
        if data["payback_period"] is None:
            full_text = " ".join(root.xpath("string(//*)")).strip()
            payback = re.search(
                r"(\d+(?:[.,]\d+)?)\s*(?:anni|anno)\s*(?:di)?\s*(?:ritorno|payback)",
                full_text,
                re.IGNORECASE,
            )
            data["payback_period"] = (
                (payback.group(1).replace(",", ".")) if payback else None
            )

        improv_txt = xs(["//ape:informazioniMiglioramento", "//ape:raccomandazioni"])
        if improv_txt:
            raw = improv_txt.replace("\r", "\n")
            lines = re.split(r"[\n;•\-]+", raw)
            interventions = [l.strip(" .:;") for l in lines if l and len(l.strip()) > 2]
            data["suggested_interventions"] = interventions[:3]
        else:
            data["suggested_interventions"] = []

    except Exception as e:
        print(f"Error parsing APE: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    return data


def _guess_image_mime(b64: str) -> str:
    """Guess MIME type from base64 header."""
    if b64.startswith("iVBOR"):
        return "image/png"
    if b64.startswith("/9j/"):
        return "image/jpeg"
    if b64.startswith("R0lGOD"):
        return "image/gif"
    return "image/png"


def extract_ape_image_b64(xml_text: str):
    """
    Returns (mime, base64) of the first plausible image found in the XML, if any.
 
    Args:
        xml_text: XML content as string
 
    Returns:
        tuple: (mime_type, base64_string) or None
    """
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
        ns = {"ape": "http://www.csi.it/sicee/siceeweb/xml/xmlapecompleto2015/data"}

        # Possible image locations
        xpaths = [
            "//ape:prestazioneGlobale//ape:immagine",
            "//ape:immagini/ape:immagine",
            "//*[contains(local-name(), 'immagine')]",
            "//*[contains(local-name(), 'image')]",
        ]
        for xp in xpaths:
            for n in root.xpath(xp, namespaces=ns):
                txt = (n.text or "").strip()
                if len(txt) > 100:  # likely base64
                    return _guess_image_mime(txt), txt
    except Exception as e:
        print(f"APE image extraction error: {type(e).__name__}: {e}")
    return None


def calculate_ape_score(ape_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a synthetic EPC (APE) score for each property based on expert criteria.
    Each category uses a 1-5 scale.

    Criteria (1-5 scale per category):
    1. Energy Class:
       - A1, A2, A3, A4 -> 5 points
       - B -> 4 points
       - C, D -> 3 points
       - E -> 2 points
       - F, G -> 1 point

    2. System:
       - Heat pump / District heating -> 5 points
       - Condensing boiler / Biomass -> 4 points
       - Other (standard boiler, oil, etc.) -> 2 points

    3. Envelope (based on winter quality):
       - High quality (Smiling face) -> 5 points
       - Medium quality (Neutral/amazed face) -> 3 points
       - Low quality (Sad face) -> 1 point

    4. Renewables:
       - Renewable sources present -> 5 points
       - Absent -> 2 points

    Args:
        ape_df: DataFrame with detailed EPC data

    Returns:
        pd.DataFrame: Enriched DataFrame with score columns (1-5 scale)
    """
    df = ape_df.copy()

    # 1. Energy Class Score (1-5)
    energy_class = df["classe"].astype(str).str.upper().str.strip()

    conditions_class = [
        energy_class.isin(["A1", "A2", "A3", "A4", "A"]),  # Class A -> 5
        energy_class == "B",  # Class B -> 4
        energy_class.isin(["C", "D"]),  # Class C, D -> 3
        energy_class == "E",  # Class E -> 2
    ]
    choices_class = [5, 4, 3, 2]
    df["energy_score_class"] = np.select(conditions_class, choices_class, default=1)

    # 2. System Score (1-5)
    desc = df["imp_risc_desc"].astype(str).str.lower()

    # Pattern for high efficiency systems (5 points)
    high_score_pattern = r"pompa di calore|teleriscaldamento|geotermico"
    # Pattern for medium efficiency systems (4 points)
    med_score_pattern = r"condensazione|biomassa|cippato|legna|pellet"

    conditions_sys = [
        desc.str.contains(high_score_pattern, regex=True, na=False),  # -> 5
        desc.str.contains(med_score_pattern, regex=True, na=False),  # -> 4
    ]
    choices_sys = [5, 4]
    df["energy_score_plant"] = np.select(conditions_sys, choices_sys, default=2)

    # 3. Envelope Score (1-5, based on winter quality)
    quality = df["qualita_invernale"].astype(str).str.lower()
 
    conditions_env = [
        quality.str.contains("smiling|sorridente", na=False),  # High quality -> 5
        quality.str.contains("basita|neutr|amazed", regex=True, na=False),  # Medium -> 3
    ]
    choices_env = [5, 3]
    df["energy_score_envelope"] = np.select(conditions_env, choices_env, default=1)

    # 4. Renewables Score (2-5 scale)
    renewables = df["fonti_rinnovabili"].astype(str).str.lower()
    # Check for 'si' or 'sì' or 'yes' -> 5, else -> 2
    df["energy_score_renewables"] = np.where(
        renewables.str.contains(r"s[iì]|yes", regex=True, na=False), 5, 2
    )

    # Total Calculation (Max 20, Min 6)
    df["energy_total_points"] = (
        df["energy_score_class"]
        + df["energy_score_plant"]
        + df["energy_score_envelope"]
        + df["energy_score_renewables"]
    )

    # Mapping to final 1-5 score (normalized)
    # Range: 6-20 points
    # 18-20 -> 5 (Excellent)
    # 15-17 -> 4 (Good)
    # 12-14 -> 3 (Sufficient)
    # 9-11 -> 2 (Poor)
    # 6-8 -> 1 (Insufficient)
    points = df["energy_total_points"]
    conditions_total = [
        points >= 18,  # -> 5
        points >= 15,  # -> 4
        points >= 12,  # -> 3
        points >= 9,  # -> 2
    ]
    choices_total = [5, 4, 3, 2]
    df["energy_score"] = np.select(conditions_total, choices_total, default=1)

    return df
