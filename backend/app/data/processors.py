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
MAPPING_QUALITA_INVOLUCRO = {"0": "Sorridente", "1": "Basita/o", "2": "Triste"}

MAPPING_IMPIANTI = {
    "0": "Caldaia standard",
    "1": "Caldaia a condensazione",
    "2": "Stufa o caminetto",
    "3": "Riscaldamento elettrico",
    "4": "Pompa di calore",
    "5": "Pompa di calore",
    "6": "Pompa di calore",
    "7": "Pompa di calore",
    "8": "Pompa di calore",
    "9": "Pompa di calore",
    "10": "Pompa di calore",
    "11": "Pompa di calore",
    "12": "Pompa di calore",
    "13": "Pompa di calore",
    "14": "Pompa di calore",
    "15": "Pompa di calore",
    "16": "Impianto solare termico",
    "17": "Impianto fotovoltaico",
    "18": "Cogeneratore",
    "19": "Teleriscaldamento",
    "32": "Scalda-acqua a gas",
    "33": "Scalda-acqua a gas",
    "34": "Scalda-acqua a pompa di calore",
    "35": "Scalda-acqua a pompa di calore",
    "36": "Boiler elettrico",
}

VETTORI_XPATHS = {
    "Energia elettrica da rete": "//ape:prestazioneImpianti/ape:energiaElettricaRete/ape:consumoAnnuo",
    "Gas naturale": "//ape:prestazioneImpianti/ape:gasNaturale/ape:consumoAnnuo",
    "GPL": "//ape:prestazioneImpianti/ape:gpl/ape:consumoAnnuo",
    "Carbone": "//ape:prestazioneImpianti/ape:carbone/ape:consumoAnnuo",
    "Gasolio": "//ape:prestazioneImpianti/ape:gasolio/ape:consumoAnnuo",
    "Olio combustibile": "//ape:prestazioneImpianti/ape:olioCombustibile/ape:consumoAnnuo",
    "Biomasse solide": "//ape:prestazioneImpianti/ape:biomasseSolide/ape:consumoAnnuo",
    "Biomasse liquide": "//ape:prestazioneImpianti/ape:biomasseLiquide/ape:consumoAnnuo",
    "Biomasse gassose": "//ape:prestazioneImpianti/ape:biomasseGassose/ape:consumoAnnuo",
    "Solare fotovoltaico": "//ape:prestazioneImpianti/ape:solareFotovoltaico/ape:consumoAnnuo",
    "Solare termico": "//ape:prestazioneImpianti/ape:solareTermico/ape:consumoAnnuo",
    "Eolico": "//ape:prestazioneImpianti/ape:eolico/ape:consumoAnnuo",
    "Teleriscaldamento": "//ape:prestazioneImpianti/ape:teleriscaldamento/ape:consumoAnnuo",
    "Teleraffrescamento": "//ape:prestazioneImpianti/ape:teleraffrescamento/ape:consumoAnnuo",
}

VETTORI_PCI = {
    "Gas naturale": 9.94,
    "GPL": 12.778,
    "Carbone": 7.917,
    "Gasolio": 11.87,
    "Olio combustibile": 11.75,
    "Biomasse solide": 4.67,
    "Biomasse liquide": 7.5,
    "Biomasse gassose": 6.4,
}


def process_population_data(geojson_data, csv_path):
    """
    Carica i dati della popolazione dal CSV, li pulisce e li unisce al GeoJSON
    delle zone urbanistiche usando il codice della zona come chiave.

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
                f"Colonna zona_urbanistica non trovata nel CSV. Colonne disponibili: {list(df_pop.columns)}"
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
        print(f"ERRORE nell'elaborazione dei dati della popolazione: {e}")
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
    Calcola la distanza in km tra ciascun immobile e i POI selezionati.
    Usa il RoutingService (OSM/Pandana) se disponibile per distanze reali,
    altrimenti fallback su Haversine.
    """
    # from app.services.routing import get_router  # TODO: Implement routing service
    from app.utils.helpers import haversine_km

    # Routing not implemented yet, will use Haversine fallback
    get_router = None

    df_processed = input_df.copy()
    df_processed["poi_riferimento"] = None
    df_processed["distanza_km"] = np.nan
    df_processed["tempo_minuti"] = np.nan  # Aggiungo anche il tempo stimato

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

    # Normalizza i POI forniti dall'utente (lista di [nome, lat, lon])
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

    # Logica di calcolo:
    # Per ogni POI, calcoliamo la distanza vettoriale da TUTTI gli immobili
    # Manteniamo per ogni immobile la distanza MINIMA verso uno dei POI selezionati

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

                # Sostituisci inf con nan per gestione
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
        # This is a bit tricky with pandas indexing, so we iterate or use combining

        # Let's use a temp updates series
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
    Parser APE aggiornato con logica degli esperti.

    Implements:
    - Bug fixes for data extraction
    - Expert logic (quality, simulated services, energy vectors, systems)
    - Top 5 energy vectors extraction

    Args:
        xml_text: XML content as string

    Returns:
        dict: Parsed APE data
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
        data["indirizzo"] = xs(
            [
                "//ape:datiGenerali/ape:indirizzo",
                "//ape:datiCalcolo/ape:datiGenerali/ape:indirizzo",
            ]
        )
        data["civico"] = xs(
            [
                "//ape:datiGenerali/ape:datiIdentificativi/ape:numeroCivico",
                "//ape:datiGenerali/ape:datiIdentificativi/ape:civico",
                "//ape:datiCalcolo/ape:datiGenerali/ape:civico",
            ]
        )
        data["comune"] = xs(
            [
                "//ape:datiGenerali/ape:datiExtra/ape:comune",
                "//ape:datiCalcolo/ape:datiGenerali/ape:comune",
            ]
        )
        data["zona_climatica"] = xs(
            [
                "//ape:datiGenerali/ape:zonaClimatica",
                "//ape:datiCalcolo/ape:datiGenerali/ape:zonaClimatica",
            ]
        )

        data["anno_costruzione"] = xs(
            [
                "//ape:datiGenerali/ape:annoCostruzione",
                "//ape:datiGenerali/ape:datiIdentificativi/ape:annoCostruzione",
            ]
        )

        data["lat"] = xs(
            [
                "//ape:datiGenerali/ape:LatitudineGIS",
                "//ape:datiCalcolo/ape:datiGenerali/ape:latitudineGIS",
            ]
        )
        data["lon"] = xs(
            [
                "//ape:datiGenerali/ape:LongitudineGIS",
                "//ape:datiCalcolo/ape:datiGenerali/ape:longitudineGIS",
            ]
        )
        data["superficie"] = sxp(
            "//ape:datiGenerali/ape:datiIdentificativi/ape:superficieUtileRiscaldata"
        )
        data["data_emissione"] = sxp("//ape:dataEmissione")
        data["destinazione_uso_cod"] = sxp("//ape:datiGenerali/ape:destinazioneUso")
        data["oggetto_attestato_cod"] = sxp("//ape:datiGenerali/ape:oggettoAttestato")
        data["tipologia_edilizia_cod"] = sxp("//ape:datiExtra/ape:tipologiaEdilizia")

        data["piano"] = xs(
            [
                "//ape:datiGenerali/ape:piano",
                "//ape:datiFabbricato//ape:piano",
                "string(//*[contains(translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'piano')][1])",
            ]
        )

        # Main performance indicators
        data["classe_energetica"] = sxp(
            "//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:classeEnergetica"
        )
        data["epglnren"] = sxp(
            "//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:epglnren"
        )
        data["classe_energetica_rif"] = sxp(
            "//ape:prestazioneGlobale/ape:riferimenti/ape:classificazioneNuovi/ape:classeEnergetica"
        )
        data["epglnren_rif"] = sxp(
            "//ape:prestazioneGlobale/ape:riferimenti/ape:classificazioneNuovi/ape:epglnren"
        )
        data["epglren"] = sxp("//ape:prestazioneImpianti/ape:epglren")
        data["emissioni_co2"] = sxp("//ape:prestazioneImpianti/ape:emissioniCO2")

        # Energy services (updated logic with 'impiantoSimulato')
        servizi = []

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
                servizi.append("Riscaldamento")

        if sxp("//ape:datiImpianti/ape:produzioneACS/ape:impiantoSimulato") is None:
            if (
                sxp(
                    "//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:produzioneAcquaCaldaSanitaria"
                )
                == "true"
            ):
                servizi.append("ACS")

        for tag, label in [
            ("climatizzazioneEstiva", "Raffrescamento"),
            ("ventilazioneMeccanica", "Ventilazione"),
            ("illuminazione", "Illuminazione"),
            ("trasportoPersoneCose", "Ascensori/Trasporto"),
        ]:
            v = sxp(f"//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:{tag}")
            if v and v.lower() == "true":
                servizi.append(label)

        data["servizi_presenti"] = servizi

        # Main energy vector calculation
        consumi_calcolati_kwh = {}

        for nome, path in VETTORI_XPATHS.items():
            consumo_str = sxp(path)
            if consumo_str:
                try:
                    consumo_val = float(consumo_str.replace(",", "."))
                    if nome in VETTORI_PCI:
                        consumo_val *= VETTORI_PCI[nome]
                    consumi_calcolati_kwh[nome] = consumo_val
                except ValueError:
                    continue

        vettore_principale = None
        if consumi_calcolati_kwh:
            vettori_ordinati = sorted(
                consumi_calcolati_kwh.items(), key=lambda item: item[1], reverse=True
            )
            vettori_positivi = [
                (nome, round(val, 2)) for nome, val in vettori_ordinati if val > 0
            ]

            if vettori_positivi:
                vettore_principale = vettori_positivi[0][0]

            data["vettori_top"] = vettori_positivi[:5]
        else:
            data["vettori_top"] = []

        data["vettore_energetico_principale"] = vettore_principale
        data["consumi_calcolati_kwh"] = consumi_calcolati_kwh

        # Cadastral data
        cat = {
            "codice_catastale": None,
            "sezione": None,
            "foglio": None,
            "particella": None,
            "subA": None,
            "subDA": None,
            "subalterno": None,
        }
        nodes = root.xpath(".//ape:datiCatastali", namespaces=ns)
        if nodes:
            n = nodes[0]

            def s(node_x):
                t = n.xpath(f"string({node_x})", namespaces=ns)
                return t.strip() if t and t.strip() else None

            cat["codice_catastale"] = s("ape:codiceCatastale")
            cat["sezione"] = s("ape:sezione")
            cat["foglio"] = s("ape:foglio")
            cat["particella"] = s("ape:particella")
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
                        cat["foglio"] = cat["foglio"] or m.group(1)
                        cat["particella"] = cat["particella"] or m.group(2)
                        cat["subalterno"] = cat["subalterno"] or m.group(3)
                        break

            if (cat["foglio"] or cat["particella"]) and not cat["codice_catastale"]:
                cc = sxp(".//ape:codiceCatastale")
                if cc:
                    cat["codice_catastale"] = cc
            if cat["subalterno"] and not (cat["subA"] or cat["subDA"]):
                cat["subA"] = cat["subalterno"]
        data.update(cat)

        # Building envelope quality (updated mapping)
        tolower = "translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"

        val_inv = sxp(
            "//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:inverno"
        )
        data["qualita_invernale_cod"] = val_inv
        data["qualita_invernale"] = MAPPING_QUALITA_INVOLUCRO.get(val_inv, val_inv)

        val_est = sxp(
            "//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:estate"
        )
        data["qualita_estiva_cod"] = val_est
        data["qualita_estiva"] = MAPPING_QUALITA_INVOLUCRO.get(val_est, val_est)

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
                    "tecnologia": None,
                    "anno": None,
                    "descrizione": None,
                    "epnren": None,
                    "tipo_impianto_cod": None,
                }

            def s(xpath):
                val = found_node.xpath(f"string({xpath})", namespaces=ns)
                return val.strip() if isinstance(val, str) and val.strip() else None

            anno = s(
                f".//*[contains({tolower},'install') and contains({tolower},'anno')][1]"
            )
            descrizione = s(".//ape:impianto[1]/ape:descrizioneImpianto")
            epnren = s(".//ape:prestazione/ape:epnren")

            tipo_impianto_cod = s(".//ape:impianto[1]/ape:tipoImpianto")
            tecnologia = MAPPING_IMPIANTI.get(tipo_impianto_cod, descrizione)

            if tecnologia is None:
                tecnologia = s(
                    f".//*[contains({tolower},'tecnolog') or contains({tolower},'tipogener') or contains({tolower},'tipo')][1]"
                )

            return {
                "tecnologia": tecnologia,
                "anno": anno,
                "descrizione": descrizione,
                "epnren": epnren,
                "tipo_impianto_cod": tipo_impianto_cod,
            }

        data["impianti"] = {
            "Riscaldamento": get_service_info(
                [
                    "//ape:datiImpianti//ape:climatizzazioneInvernale",
                    "//ape:impianti//ape:impiantoClimatizzazioneInvernale",
                ]
            ),
            "ACS": get_service_info(
                [
                    "//ape:datiImpianti//ape:produzioneACS",
                    "//ape:impianti//ape:impiantoAcquaCaldaSanitaria",
                ]
            ),
            "Raffrescamento": get_service_info(
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
                data["fonti_rinnovabili"] = "Sì"
            else:
                data["fonti_rinnovabili"] = "No"
        except Exception:
            data["fonti_rinnovabili"] = "No"

        # Improvements
        data["classe_target"] = xs(
            [
                "//ape:raccomandazioni//ape:classificazioneRaggiungibile/ape:classeEnergetica",
                "//ape:prestazioneGlobale//ape:classeEnergeticaRaggiungibile",
                f"string(//*[contains({tolower},'classe') and contains({tolower},'raggiung')][1])",
                f"string(//*[contains({tolower},'classe') and contains({tolower},'miglior')][1])",
            ]
        )

        data["risparmio_perc"] = None  # Removed, too unreliable

        data["tempo_ritorno"] = sxp(
            "//ape:raccomandazioni//ape:tempoRitornoInvestimento"
        )
        if data["tempo_ritorno"] is None:
            full_text = " ".join(root.xpath("string(//*)")).strip()
            payback = re.search(
                r"(\d+(?:[.,]\d+)?)\s*(?:anni|anno)\s*(?:di)?\s*(?:ritorno|payback)",
                full_text,
                re.IGNORECASE,
            )
            data["tempo_ritorno"] = (
                (payback.group(1).replace(",", ".")) if payback else None
            )

        migli_txt = xs(["//ape:informazioniMiglioramento", "//ape:raccomandazioni"])
        if migli_txt:
            raw = migli_txt.replace("\r", "\n")
            lines = re.split(r"[\n;•\-]+", raw)
            interventi = [l.strip(" .:;") for l in lines if l and len(l.strip()) > 2]
            data["interventi_suggeriti"] = interventi[:3]
        else:
            data["interventi_suggeriti"] = []

    except Exception as e:
        print(f"Errore nel parsing APE: {type(e).__name__}: {e}")
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
    Ritorna (mime, base64) della prima immagine plausibile trovata nell'XML, se presente.

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
        print(f"Estrazione immagine APE: {type(e).__name__}: {e}")
    return None


def calculate_ape_score(ape_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcola uno score sintetico per ogni APE basato su criteri esperti.
    Ogni categoria usa una scala 1-5.

    Criteri (Scala 1-5 per categoria):
    1. Classe Energetica:
       - A1, A2, A3, A4 -> 5 punti
       - B -> 4 punti
       - C, D -> 3 punti
       - E -> 2 punti
       - F, G -> 1 punto

    2. Impianto:
       - Pompa di calore / Teleriscaldamento -> 5 punti
       - Caldaia a condensazione / Biomassa -> 4 punti
       - Altro (caldaia standard, gasolio, etc.) -> 2 punti

    3. Involucro (basato su qualità invernale):
       - Alta qualità (Faccina sorridente) -> 5 punti
       - Media qualità (Faccina neutra/basita) -> 3 punti
       - Bassa qualità (Faccina triste) -> 1 punto

    4. Rinnovabili:
       - Presenti fonti rinnovabili -> 5 punti
       - Assenti -> 2 punti

    Args:
        ape_df: DataFrame con i dati APE dettagliati

    Returns:
        pd.DataFrame: DataFrame arricchito con colonne score (scala 1-5)
    """
    df = ape_df.copy()

    # 1. Score Classe Energetica (1-5)
    classe = df["classe"].astype(str).str.upper().str.strip()

    conditions_class = [
        classe.isin(["A1", "A2", "A3", "A4", "A"]),  # Classe A -> 5
        classe == "B",  # Classe B -> 4
        classe.isin(["C", "D"]),  # Classe C, D -> 3
        classe == "E",  # Classe E -> 2
        # Default (F, G, altro) -> 1
    ]
    choices_class = [5, 4, 3, 2]
    df["ape_class_score"] = np.select(conditions_class, choices_class, default=1)

    # 2. Score Impianto (1-5)
    desc = df["imp_risc_desc"].astype(str).str.lower()

    # Pattern per impianti ad alta efficienza (5 punti)
    high_score_pattern = r"pompa di calore|teleriscaldamento|geotermico"
    # Pattern per impianti a media efficienza (4 punti)
    med_score_pattern = r"condensazione|biomassa|cippato|legna|pellet"

    conditions_sys = [
        desc.str.contains(high_score_pattern, regex=True, na=False),  # -> 5
        desc.str.contains(med_score_pattern, regex=True, na=False),  # -> 4
        # Default (caldaia standard, gasolio, etc.) -> 2
    ]
    choices_sys = [5, 4]
    df["ape_system_score"] = np.select(conditions_sys, choices_sys, default=2)

    # 3. Score Involucro (1-5, basato su qualità invernale)
    qualita = df["qualita_invernale"].astype(str).str.lower()

    conditions_env = [
        qualita.str.contains("sorridente", na=False),  # Alta qualità -> 5
        qualita.str.contains("basita|neutr", regex=True, na=False),  # Media -> 3
        # Default (triste, altro) -> 1
    ]
    choices_env = [5, 3]
    df["ape_envelope_score"] = np.select(conditions_env, choices_env, default=1)

    # 4. Score Rinnovabili (scala 2-5)
    rinnovabili = df["fonti_rinnovabili"].astype(str).str.lower()
    # Check for 'si' or 'sì' -> 5, altrimenti -> 2
    df["ape_renewables_score"] = np.where(
        rinnovabili.str.contains(r"s[iì]", regex=True, na=False), 5, 2
    )

    # Calcolo Totale (Max 20, Min 6)
    df["ape_total_points"] = (
        df["ape_class_score"]
        + df["ape_system_score"]
        + df["ape_envelope_score"]
        + df["ape_renewables_score"]
    )

    # Mapping a score finale 1-5 (normalizzato)
    # Range: 6-20 punti
    # 18-20 -> 5 (Eccellente)
    # 15-17 -> 4 (Buono)
    # 12-14 -> 3 (Sufficiente)
    # 9-11 -> 2 (Scarso)
    # 6-8 -> 1 (Insufficiente)
    points = df["ape_total_points"]
    conditions_total = [
        points >= 18,  # -> 5
        points >= 15,  # -> 4
        points >= 12,  # -> 3
        points >= 9,  # -> 2
        # < 9 -> 1
    ]
    choices_total = [5, 4, 3, 2]
    df["ape_score"] = np.select(conditions_total, choices_total, default=1)

    return df
