import pandas as pd
import xml.etree.ElementTree as ET
from lxml import etree
import os
import re
import zipfile
import glob
import shutil
import numpy as np
import hashlib
from typing import Dict, List, Tuple, Set
from tqdm.auto import tqdm
from functools import lru_cache
import warnings
from concurrent.futures import ProcessPoolExecutor
import ast
import sys
from pathlib import Path

# Add project root to sys.path to allow importing backend
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.services.energy_score_calculator import EnergyScoreCalculator

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Use environment variable for data path or a generic placeholder
path = os.environ.get("APE_XML_PATH", "./merged_xml_data")

# PCI (Potere Calorifico Inferiore) for energy vector conversion to kWh
VETTORI_PCI = {
    'Gas naturale': 9.94,
    'GPL': 12.778,
    'Carbone': 7.917,
    'Gasolio': 11.87,
    'Olio combustibile': 11.75,
    'Biomasse solide': 4.67,
    'Biomasse liquide': 7.5,
    'Biomasse gassose': 6.4
}

# Mapping per i codici di qualità involucro
MAPPING_QUALITA_INVOLUCRO = {
    '0': 'Sorridente',
    '1': 'Basita/o',
    '2': 'Triste'
}

# Mapping per i codici 'tipoImpianto'
MAPPING_IMPIANTI = {
    '0': 'Caldaia standard',
    '1': 'Caldaia a condensazione',
    '2': 'Stufa o caminetto',
    '3': 'Riscaldamento elettrico',
    '4': 'Pompa di calore', '5': 'Pompa di calore', '6': 'Pompa di calore', '7': 'Pompa di calore',
    '8': 'Pompa di calore', '9': 'Pompa di calore', '10': 'Pompa di calore', '11': 'Pompa di calore',
    '12': 'Pompa di calore', '13': 'Pompa di calore', '14': 'Pompa di calore', '15': 'Pompa di calore',
    '16': 'Impianto solare termico',
    '17': 'Impianto fotovoltaico',
    '18': 'Cogeneratore',
    '19': 'Teleriscaldamento',
    '32': 'Scalda-acqua a gas',
    '33': 'Scalda-acqua a gas',
    '34': 'Scalda-acqua a pompa di calore',
    '35': 'Scalda-acqua a pompa di calore',
    '36': 'Boiler elettrico'
}

TIPOLOGIA_MAP = {
    '1': 'Ed. Isolato', '3': 'Ed. Plurifam.',
    '9': 'App. Condominio', None: ''
}

VETTORI_XPATHS = {
    'Energia elettrica da rete': '//ape:prestazioneImpianti/ape:energiaElettricaRete/ape:consumoAnnuo',
    'Gas naturale': '//ape:prestazioneImpianti/ape:gasNaturale/ape:consumoAnnuo',
    'GPL': '//ape:prestazioneImpianti/ape:gpl/ape:consumoAnnuo',
    'Carbone': '//ape:prestazioneImpianti/ape:carbone/ape:consumoAnnuo',
    'Gasolio': '//ape:prestazioneImpianti/ape:gasolio/ape:consumoAnnuo',
    'Olio combustibile': '//ape:prestazioneImpianti/ape:olioCombustibile/ape:consumoAnnuo',
    'Biomasse solide': '//ape:prestazioneImpianti/ape:biomasseSolide/ape:consumoAnnuo',
    'Biomasse liquide': '//ape:prestazioneImpianti/ape:biomasseLiquide/ape:consumoAnnuo',
    'Biomasse gassose': '//ape:prestazioneImpianti/ape:biomasseGassose/ape:consumoAnnuo',
    'Solare fotovoltaico': '//ape:prestazioneImpianti/ape:solareFotovoltaico/ape:consumoAnnuo',
    'Solare termico': '//ape:prestazioneImpianti/ape:solareTermico/ape:consumoAnnuo',
    'Eolico': '//ape:prestazioneImpianti/ape:eolico/ape:consumoAnnuo',
    'Teleriscaldamento': '//ape:prestazioneImpianti/ape:teleriscaldamento/ape:consumoAnnuo',
    'Teleraffrescamento': '//ape:prestazioneImpianti/ape:teleraffrescamento/ape:consumoAnnuo'
}

def _normalize_text(s: str) -> str:
    if s is None:
        return ""
    return " ".join(s.split())

def _localname(tag: str) -> str:
    if isinstance(tag, str) and tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag

def xml_to_map(xml_text: str, strip_ns: bool = True) -> Dict[str, str]:
    root = ET.fromstring(xml_text)
    kv: Dict[str, str] = {}

    def walk(elem: ET.Element, path: str):
        for k in sorted(elem.attrib.keys()):
            ak = _localname(k) if strip_ns else k
            kv[f"{path}/@{ak}"] = _normalize_text(elem.attrib[k])
        t = _normalize_text(elem.text)
        if t:
            kv[f"{path}/#text"] = t
        counts = {}
        for child in list(elem):
            tag_name = _localname(child.tag) if strip_ns else child.tag
            counts[tag_name] = counts.get(tag_name, 0) + 1
            idx = counts[tag_name]
            child_path = f"{path}/{tag_name}[{idx}]"
            walk(child, child_path)

    root_name = _localname(root.tag) if strip_ns else root.tag
    walk(root, f"/{root_name}[1]")
    return kv

def read_xml_text_safe(full_path: str) -> str:
    with open(full_path, 'rb') as f:
        raw = f.read()
    if not raw: return ""
    if raw.startswith(b'\xef\xbb\xbf'):
        text = raw[3:].decode('utf-8', errors='ignore')
    elif raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        text = raw[2:].decode('utf-16', errors='ignore')
    else:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1', errors='ignore')
    text = re.sub(r'^.*?<\?xml', '<?xml', text, flags=re.DOTALL)
    return text

def parse_ape_xml(xml_text: str) -> dict:
    ns = {'ape': 'http://www.csi.it/sicee/siceeweb/xml/xmlapecompleto2015/data'}
    data = {}
    try:
        root = etree.fromstring(xml_text.encode('utf-8'))
        def sxp(x):
            val = root.xpath(f'string({x})', namespaces=ns)
            return val.strip() if isinstance(val, str) and val.strip() else None
        def xs(paths):
            for p in paths:
                v = sxp(p)
                if v: return v
            return None

        # Dati generali
        data['indirizzo'] = xs(['//ape:datiGenerali/ape:indirizzo','//ape:datiCalcolo/ape:datiGenerali/ape:indirizzo'])
        data['civico'] = xs(['//ape:datiGenerali/ape:datiIdentificativi/ape:numeroCivico','//ape:datiGenerali/ape:datiIdentificativi/ape:civico','//ape:datiCalcolo/ape:datiGenerali/ape:civico'])
        data['comune'] = xs(['//ape:datiGenerali/ape:datiExtra/ape:comune','//ape:datiCalcolo/ape:datiGenerali/ape:comune'])
        data['zona_climatica'] = xs(['//ape:datiGenerali/ape:zonaClimatica','//ape:datiCalcolo/ape:datiGenerali/ape:zonaClimatica'])
        data['anno_costruzione'] = xs(['//ape:datiGenerali/ape:annoCostruzione','//ape:datiGenerali/ape:datiIdentificativi/ape:annoCostruzione'])
        data['lat'] = xs(['//ape:datiGenerali/ape:LatitudineGIS','//ape:datiCalcolo/ape:datiGenerali/ape:latitudineGIS'])
        data['lon'] = xs(['//ape:datiGenerali/ape:LongitudineGIS','//ape:datiCalcolo/ape:datiGenerali/ape:longitudineGIS'])
        data['superficie'] = sxp('//ape:datiGenerali/ape:datiIdentificativi/ape:superficieUtileRiscaldata')
        data['data_emissione'] = sxp('//ape:dataEmissione')
        data['destinazione_uso_cod'] = sxp('//ape:datiGenerali/ape:destinazioneUso')
        data['oggetto_attestato_cod'] = sxp('//ape:datiGenerali/ape:oggettoAttestato')
        data['tipologia_edilizia_cod'] = sxp('//ape:datiExtra/ape:tipologiaEdilizia')
        data['piano'] = xs(['//ape:datiGenerali/ape:piano','//ape:datiFabbricato//ape:piano',"string(//*[contains(translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'piano')][1])"])

        # Prestazioni
        data['classe_energetica'] = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:classeEnergetica')
        data['epglnren'] = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaGlobale/ape:classificazione/ape:epglnren')
        data['epglren'] = sxp('//ape:prestazioneImpianti/ape:epglren')
        data['emissioni_co2'] = sxp('//ape:prestazioneImpianti/ape:emissioniCO2')

        # Servizi
        servizi = []
        if sxp('//ape:datiImpianti/ape:climatizzazioneInvernale/ape:impiantoSimulato') is None:
            if sxp('//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:climatizzazioneInvernale') == 'true': servizi.append('Riscaldamento')
        if sxp('//ape:datiImpianti/ape:produzioneACS/ape:impiantoSimulato') is None:
            if sxp('//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:produzioneAcquaCaldaSanitaria') == 'true': servizi.append('ACS')
        for tag, label in [('climatizzazioneEstiva', 'Raffrescamento'),('ventilazioneMeccanica', 'Ventilazione'),('illuminazione', 'Illuminazione'),('trasportoPersoneCose', 'Ascensori/Trasporto')]:
            v = sxp(f'//ape:datiGenerali/ape:serviziEnergeticiPresenti/ape:{tag}')
            if v and v.lower() == 'true': servizi.append(label)
        data['servizi_presenti'] = servizi

        # Vettore Energetico
        consumi_calcolati_kwh = {}
        for nome, xpath in VETTORI_XPATHS.items():
            consumo_str = sxp(xpath)
            if consumo_str:
                try:
                    v = float(consumo_str.replace(',', '.'))
                    if nome in VETTORI_PCI: v *= VETTORI_PCI[nome]
                    consumi_calcolati_kwh[nome] = v
                except ValueError: continue
        data['consumi_calcolati_kwh'] = consumi_calcolati_kwh
        if consumi_calcolati_kwh:
            v_ord = sorted(consumi_calcolati_kwh.items(), key=lambda x: x[1], reverse=True)
            v_pos = [(n, round(val, 2)) for n, val in v_ord if val > 0]
            data['vettore_energetico_principale'] = v_pos[0][0] if v_pos else None
        else: data['vettore_energetico_principale'] = None

        # Catasto
        cat = {'codice_catastale': None, 'sezione': None, 'foglio': None, 'particella': None, 'subA': None, 'subDA': None, 'subalterno': None}
        nodes = root.xpath('.//ape:datiCatastali', namespaces=ns)
        if nodes:
            n = nodes[0]
            def s(node_x):
                t = n.xpath(f'string({node_x})', namespaces=ns)
                return t.strip() if t and t.strip() else None
            cat['codice_catastale'] = s('ape:codiceCatastale')
            cat['sezione'] = s('ape:sezione')
            cat['foglio'] = s('ape:foglio')
            cat['particella'] = s('ape:particella')
            cat['subA'] = s('ape:subalterni/ape:subA')
            cat['subDA'] = s('ape:subalterni/ape:subDA')
        data.update(cat)

        # Qualità Involucro
        val_inv = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:inverno')
        data['qualita_invernale'] = MAPPING_QUALITA_INVOLUCRO.get(val_inv, val_inv)
        val_est = sxp('//ape:prestazioneGlobale/ape:prestazioneEnergeticaFabbricato/ape:estate')
        data['qualita_estiva'] = MAPPING_QUALITA_INVOLUCRO.get(val_est, val_est)

        # Impianti
        def get_inf(xps):
            for xp in xps:
                nodes = root.xpath(xp, namespaces=ns)
                if nodes:
                    n = nodes[0]
                    desc = n.xpath('string(.//ape:impianto[1]/ape:descrizioneImpianto)', namespaces=ns).strip()
                    tipo = n.xpath('string(.//ape:impianto[1]/ape:tipoImpianto)', namespaces=ns).strip()
                    anno = n.xpath("string(.//*[contains(translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'anno')][1])", namespaces=ns).strip()
                    epnren = n.xpath('string(.//ape:prestazione/ape:epnren)', namespaces=ns).strip()
                    return {'tecnologia': MAPPING_IMPIANTI.get(tipo, desc), 'anno': anno, 'descrizione': desc, 'epnren': epnren}
            return {'tecnologia': None, 'anno': None, 'descrizione': None, 'epnren': None}
        
        data['impianti'] = {
            'Riscaldamento': get_inf(['//ape:datiImpianti//ape:climatizzazioneInvernale']),
            'ACS': get_inf(['//ape:datiImpianti//ape:produzioneACS']),
            'Raffrescamento': get_inf(['//ape:datiImpianti//ape:climatizzazioneEstiva'])
        }

        # Rinnovabili
        try:
            fv = float(sxp(VETTORI_XPATHS['Solare fotovoltaico']) or 0)
            st = float(sxp(VETTORI_XPATHS['Solare termico']) or 0)
            data['fonti_rinnovabili'] = 'Sì' if (fv > 0 or st > 0) else 'No'
        except: data['fonti_rinnovabili'] = 'No'

        # Interventi
        data['classe_target'] = sxp('//ape:raccomandazioni//ape:classificazioneRaggiungibile/ape:classeEnergetica')
        data['tempo_ritorno'] = sxp('//ape:raccomandazioni//ape:tempoRitornoInvestimento')
        migli = sxp('//ape:informazioniMiglioramento') or sxp('//ape:raccomandazioni')
        if migli:
            data['interventi'] = [l.strip() for l in re.split(r'[\n;•\-]+', migli) if len(l.strip()) > 2]
        else: data['interventi'] = []

    except Exception as e: print(f"Errore parsing APE: {e}")
    return data

cache_bytes: Dict[str, bytes] = {}
cache_maps: Dict[str, Dict[str, str]] = {}
cache_signature: Dict[str, str] = {}

def _load_bytes(filename: str) -> bytes:
    if filename not in cache_bytes:
        with open(os.path.join(path, filename), "rb") as f:
            cache_bytes[filename] = f.read()
    return cache_bytes[filename]

def _decode_xml(raw: bytes) -> str:
    if not raw:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        text = raw[3:].decode("utf-8", errors='ignore')
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw[2:].decode("utf-16", errors='ignore')
    else:
        try:
            text = raw.decode("utf-8", errors='ignore')
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors='ignore')
    
    # Ripulisci eventuale "spazzatura" prima della dichiarazione XML
    text = re.sub(r'^.*?<\?xml', '<?xml', text, flags=re.DOTALL)
    
    # Rimuovi caratteri XML non validi (come #x65535/0xFFFF)
    # Range validi XML 1.0: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    text = re.sub(u'[^\u0009\u000a\u000d\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]', '', text)
    
    return text.strip()

def _load_map(filename: str) -> Dict[str, str]:
    if filename not in cache_maps:
        raw = _load_bytes(filename)
        content = re.sub(r"^.*?<\?xml", "<?xml", _decode_xml(raw), flags=re.DOTALL)
        cache_maps[filename] = xml_to_map(content, strip_ns=True)
    return cache_maps[filename]

def _to_float(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().replace(",", ".")
    try:
        return float(s)
    except:
        return None

def _parse_date(s):
    if not s:
        return pd.NaT
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce")
    return dt

def process_single_xml(fname: str) -> dict:
    """Worker function to process a single XML file."""
    try:
        xml_text = _decode_xml(_load_bytes(fname))
        if not xml_text:
            return None
        
        p = parse_ape_xml(xml_text)
        servizi = set(p.get("servizi_presenti") or [])
        
        indirizzo = p.get("indirizzo")
        civico = p.get("civico")
        indirizzo_full = " ".join(filter(None, [indirizzo, civico])) or None
        unita = p.get("subalterno") or p.get("subA") or p.get("subDA") or os.path.splitext(os.path.basename(fname))[0]
        
        imp_risc = p.get('impianti', {}).get('Riscaldamento', {})
        imp_acs = p.get('impianti', {}).get('ACS', {})
        imp_raf = p.get('impianti', {}).get('Raffrescamento', {})
        
        interventi = p.get('interventi', [])
        intervento_desc = interventi[0] if interventi else None
        
        # --- Calcolo Consumo Totale (kWh/anno) ---
        consumo_tot = 0.0
        # p.get('consumi_calcolati_kwh') nel parser originale usa i PCI
        # In questo script usiamo direttamente i vettori estratti
        consumi_vettori = p.get('consumi_calcolati_kwh', {})
        if consumi_vettori:
            consumo_tot = sum(v for v in consumi_vettori.values() if v > 0)
        
        # --- Calcolo Punteggi (1-5) per Radar Chart ---
        # 1. Classe
        c = str(p.get("classe_energetica") or "").upper().strip()
        if c.startswith("A"): ape_class_score = 5
        elif c == "B": ape_class_score = 4
        elif c in ["C", "D"]: ape_class_score = 3
        elif c == "E": ape_class_score = 2
        else: ape_class_score = 1

        # 2. Impianto
        desc_risc = str(imp_risc.get('descrizione') or "").lower()
        if any(x in desc_risc for x in ["pompa di calore", "teleriscaldamento", "geotermico"]):
            ape_system_score = 5
        elif any(x in desc_risc for x in ["condensazione", "biomassa", "cippato", "legna", "pellet"]):
            ape_system_score = 4
        else:
            ape_system_score = 2

        # 3. Involucro
        q_inv = str(p.get("qualita_invernale") or "").lower()
        if "sorridente" in q_inv: ape_envelope_score = 5
        elif any(x in q_inv for x in ["basita", "neutr"]): ape_envelope_score = 3
        else: ape_envelope_score = 1

        # 4. Rinnovabili
        fonti_rinnov = str(p.get("fonti_rinnovabili") or "").lower()
        ape_renewables_score = 5 if "sì" in fonti_rinnov or "si" in fonti_rinnov else 2

        return {
            "file": os.path.basename(fname),
            "unita": str(unita),
            "indirizzo": indirizzo_full,
            "data_emissione": _parse_date(p.get("data_emissione")),
            "classe": p.get("classe_energetica"),
            "epglnren": _to_float(p.get("epglnren")),
            "epglren": _to_float(p.get("epglren")),
            "co2": _to_float(p.get("emissioni_co2")),
            "superficie": _to_float(p.get("superficie")),
            "vettore": p.get("vettore_energetico_principale"), 
            "serv_risc": "Riscaldamento" in servizi,
            "serv_acs": "ACS" in servizi,
            "serv_raf": "Raffrescamento" in servizi,
            "serv_vent": "Ventilazione" in servizi,
            "serv_illu": "Illuminazione" in servizi,
            "serv_trasp": "Ascensori/Trasporto" in servizi,
            "destinazione_uso_cod": _to_float(p.get("destinazione_uso_cod")),
            "oggetto_attestato_cod": p.get("oggetto_attestato_cod"),
            "tipologia_edilizia_cod": p.get("tipologia_edilizia_cod"),
            "piano": p.get("piano"),
            "codice_catastale": p.get("codice_catastale"),
            "sezione": p.get("sezione"),
            "foglio": p.get("foglio"),
            "particella": p.get("particella"),
            "subA": p.get("subA"),
            "subDA": p.get("subDA"),
            "subalterno": p.get("subalterno"),
            "anno_costruzione": p.get("anno_costruzione"),
            "coordinate": (p.get("lat"), p.get("lon")),
            "comune": p.get("comune"),
            "zona_climatica": p.get("zona_climatica"),
            "intervento_desc": intervento_desc,
            "intervento_classe_target": p.get("classe_target"),
            "intervento_payback": _to_float(p.get("tempo_ritorno")),
            "qualita_invernale": p.get("qualita_invernale"),
            "qualita_estiva": p.get("qualita_estiva"),
            "fonti_rinnovabili": p.get("fonti_rinnovabili"),
            "imp_risc_anno": imp_risc.get('anno'),
            "imp_risc_desc": imp_risc.get('descrizione'),
            "imp_risc_tipo": imp_risc.get('tecnologia'),
            "imp_risc_epnren": _to_float(imp_risc.get('epnren')),
            "imp_acs_anno": imp_acs.get('anno'),
            "imp_acs_desc": imp_acs.get('descrizione'),
            "imp_acs_tipo": imp_acs.get('tecnologia'),
            "imp_acs_epnren": _to_float(imp_acs.get('epnren')),
            "imp_raf_anno": imp_raf.get('anno'),
            "imp_raf_desc": imp_raf.get('descrizione'),
            "imp_raf_tipo": imp_raf.get('tecnologia'),
            "imp_raf_tipo": imp_raf.get('tecnologia'),
            "imp_raf_epnren": _to_float(imp_raf.get('epnren')),
            # Nuovi campi per API backend
            "consumo_kwh_tot": consumo_tot,
            "superficie": _to_float(p.get("superficie")),
            "destinazione_uso_cod": _to_float(p.get("destinazione_uso_cod")),
            "ape_class_score": ape_class_score,
            "ape_system_score": ape_system_score,
            "ape_envelope_score": ape_envelope_score,
            "ape_renewables_score": ape_renewables_score,
            "ape_total_points": ape_class_score + ape_system_score + ape_envelope_score + ape_renewables_score,
            # ape_score is a normalized 1-5 score based on total points (from processors.py logic)
            "ape_score": (
                5 if (ape_class_score + ape_system_score + ape_envelope_score + ape_renewables_score) >= 18 else
                4 if (ape_class_score + ape_system_score + ape_envelope_score + ape_renewables_score) >= 15 else
                3 if (ape_class_score + ape_system_score + ape_envelope_score + ape_renewables_score) >= 12 else
                2 if (ape_class_score + ape_system_score + ape_envelope_score + ape_renewables_score) >= 9 else 1
            ),
            "lat": p.get("lat"),
            "lon": p.get("lon"),
            "coordinate_str": f"({p.get('lat')}, {p.get('lon')})",
            "tipologia_edilizia_str": TIPOLOGIA_MAP.get(p.get("tipologia_edilizia_cod"), "")
        }
    except Exception as e:
        print(f"Errore parsing {fname}: {e}")
        return None

def _load_ape_df(file_list: List[str]) -> pd.DataFrame:
    """Loads APE data from XML files in parallel."""
    all_rows = []

    with ProcessPoolExecutor() as executor:
        results_gen = tqdm(
            executor.map(process_single_xml, file_list),
            total=len(file_list),
            desc="Processing XML files (Parallel)"
        )
        for res in results_gen:
            if res is not None:
                all_rows.append(res)
    
    df = pd.DataFrame(all_rows)
    if not df.empty:
        # Arricchimento dati tramite EnergyScoreCalculator del backend
        calc = EnergyScoreCalculator()
        df = calc.load_and_compute(df)
        
        df = df.sort_values(["unita", "file"]).reset_index(drop=True)
    return df

def create_and_save_ape_table(df: pd.DataFrame, filepath_html: str, transpose: bool = True) -> bool:
    """
    Generates a Plotly table (horizontal or vertical) and saves it as HTML and PNG.
    - transpose=True: Attributes as rows, APEs as columns (vertical).
    - transpose=False: APEs as rows, Attributes as columns (horizontal).
    """
    
    # --- MAPPE Colori e Nomi ---
    CLASSE_COLORS = {
        'A4': '#00A651', 'A3': '#53B839', 'A2': '#A5C639', 'A1': '#F3E500',
        'B': '#F8B20C', 'C': '#F58021', 'D': '#F26723', 'E': '#ED3C24',
        'F': '#ED2E24', 'G': '#ED1C24', None: '#B0B0B0', 'N/D': '#B0B0B0'
    }
    
    # NUOVO: Colori per Qualità Involucro (Slide 6)
    QUALITA_COLORS = {
        'Sorridente': '#28a745', # Verde
        'Basita/o': '#ffc107',   # Giallo
        'Triste': '#dc3545',     # Rosso
        None: '#ffffff', 'N/D': '#ffffff'
    }
    
    # NUOVO: Colori per Fonti Rinnovabili
    RINNOVABILI_COLORS = {
        'Sì': '#28a745', # Verde
        'No': '#ffffff', # Bianco (neutro)
        None: '#ffffff', 'N/D': '#ffffff'
    }

    # MODIFICATO: Rimossa VETTORE_MAP (non più necessaria)
    
    DESTINAZIONE_MAP = {
        '0': 'Residenziale', '1': 'Residenziale', '2': 'Uffici',
        '3': 'Ospedali/Cliniche', '4': 'Att. Ricreative', '5': 'Commerciale',
        '6': 'Sportive', '7': 'Scolastiche', '8': 'Industriale', None: ''
    }
    OGGETTO_MAP = {
        '0': 'Non Spec.', '1': 'Unità Singola', '2': 'Intero Edificio',
        '3': 'Gruppo Unità', None: ''
    }
    # -----------------------------
    
    if df.empty:
        print(f"Skipping empty DataFrame for {os.path.basename(filepath_html)}")
        return False

    filepath_png = filepath_html.replace(".html", ".png")
    orientation = "Verticale" if transpose else "Orizzontale"
    print(f"Generating {orientation.lower()} table for {os.path.basename(filepath_html)}")

    df_display = df.sort_values("data_emissione", ascending=False).copy()

    # --- Common Data Preparation ---
    catasto_parts = []
    first_row = df_display.iloc[0]
    if pd.notna(first_row.get("codice_catastale")): catasto_parts.append(f"Comune Catastale: {first_row['codice_catastale']}")
    if pd.notna(first_row.get("foglio")): catasto_parts.append(f"Foglio: {first_row['foglio']}")
    if pd.notna(first_row.get("particella")): catasto_parts.append(f"Particella: {first_row['particella']}")
    # sub_parts = [s for s in [first_row.get("subA"), first_row.get("subDA"), first_row.get("subalterno")] if pd.notna(s)]
    # if sub_parts: catasto_parts.append(f"Sub: {','.join(map(str, set(sub_parts)))}")
    catasto_subtitle = " | ".join(catasto_parts) if catasto_parts else "Dati Catastali non disponibili"

    # Servizi Attivi (Questa logica funziona ancora bene con i booleani di _load_ape_df)
    servizi_cols = {
        "serv_risc": "Risc.", "serv_acs": "ACS", "serv_raf": "Raff.",
        "serv_vent": "Vent.", "serv_illu": "Illum.", "serv_trasp": "Trasp."
    }
    def get_active_services(row):
        active = [label for col, label in servizi_cols.items() if row.get(col) is True]
        return ", ".join(active) if active else "Nessuno"
    df_display['servizi_attivi'] = df_display.apply(get_active_services, axis=1)

    # Mapped columns
    for col in ['destinazione_uso_cod', 'oggetto_attestato_cod', 'tipologia_edilizia_cod']:
        if col not in df_display.columns:
            df_display[col] = None
    dest_str = df_display['destinazione_uso_cod'].astype(str).map(DESTINAZIONE_MAP).fillna('')
    obj_str = df_display['oggetto_attestato_cod'].astype(str).map(OGGETTO_MAP).fillna('')
    tipo_str = df_display['tipologia_edilizia_cod'].astype(str).map(TIPOLOGIA_MAP).fillna('')
    df_display['descrizione_immobile'] = (dest_str + ' / ' + tipo_str + ' / ' + obj_str).str.replace(r'(^\s*/\s*|\s*/\s*$)', '', regex=True).str.replace(r'\s*/\s*/\s*', ' / ', regex=True).str.strip()
    
    # MODIFICATO: Rimuovi mapping del vettore, usa fillna. Il parser fornisce già la stringa.
    df_display['vettore'] = df_display['vettore'].fillna('Sconosciuto')

    # Formatting
    df_display['data_emissione'] = pd.to_datetime(df_display['data_emissione']).dt.strftime('%Y-%m-%d')
    df_display['epglnren'] = pd.to_numeric(df_display['epglnren'], errors='coerce').round(1)
    df_display['epglren'] = pd.to_numeric(df_display['epglren'], errors='coerce').round(1)
    df_display['superficie'] = pd.to_numeric(df_display['superficie'], errors='coerce').round(1)
    df_display['co2'] = pd.to_numeric(df_display['co2'], errors='coerce').round(1)
    df_display.loc[:, 'piano'] = df_display['piano'].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
    df_display.loc[:, 'anno_costruzione'] = pd.to_numeric(df_display['anno_costruzione'], errors='coerce').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
    # NUOVO: Formattazione campi
    df_display.loc[:, 'intervento_payback'] = pd.to_numeric(df_display['intervento_payback'], errors='coerce').round(1)
    df_display.loc[:, 'imp_risc_anno'] = df_display['imp_risc_anno'].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
    df_display.loc[:, 'imp_acs_anno'] = df_display['imp_acs_anno'].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
    # -----------------------------

    # --- Define columns and rename map ---
    # MODIFICATO: Aggiunte le nuove colonne da mostrare
    cols_to_display = [ 
        "file", "data_emissione", "classe", 
        "epglnren", "epglren", "superficie", 
        "qualita_invernale", "qualita_estiva", # NUOVO
        "vettore", "fonti_rinnovabili", # NUOVO
        "servizi_attivi", 
        "imp_risc_tipo", "imp_risc_anno", # NUOVO
        "imp_acs_tipo", "imp_acs_anno", # NUOVO
        "intervento_classe_target", "intervento_payback", # NUOVO
        "piano", "anno_costruzione", "descrizione_immobile", "co2"
    ]
    cols_existing = [col for col in cols_to_display if col in df_display.columns]

    # MODIFICATO: Aggiunti nomi per le nuove colonne
    rename_map = { 
        'file': 'File APE', 'data_emissione': 'Data Emissione', 'classe': 'Classe',
        'descrizione_immobile': 'Descrizione Immobile', 'epglnren': 'EPgl,nren (kWh/m²a)',
        'epglren': 'EPgl,ren (kWh/m²a)', 'superficie': 'Superficie (m²)',
        'piano': 'Piano', 'anno_costruzione': 'Anno Costruzione',
        'vettore': 'Vettore Principale', 'co2': 'CO₂ (kg/m²a)',
        'servizi_attivi': 'Servizi Attivi', 'unita': 'Unità Imm.',
        # NUOVI NOMI
        'qualita_invernale': 'Qualità Inv.',
        'qualita_estiva': 'Qualità Est.',
        'fonti_rinnovabili': 'Rinnovabili',
        'imp_risc_tipo': 'Tecn. Risc.',
        'imp_risc_anno': 'Anno Risc.',
        'imp_acs_tipo': 'Tecn. ACS',
        'imp_acs_anno': 'Anno ACS',
        'intervento_classe_target': 'Classe Target',
        'intervento_payback': 'Payback (Anni)'
    }
    readable_cols = [rename_map.get(col, col) for col in cols_existing]
    # ------------------------------------

    if transpose:
        # --- Vertical Table Logic ---
        if 'file' not in df_display.columns:
            print(f"Errore: Colonna 'file' non trovata per {os.path.basename(filepath_html)}")
            return False
        
        cols_existing_no_file = [c for c in cols_existing if c != 'file']
        
        df_processed = df_display.set_index('file')[cols_existing_no_file].T.reset_index()
        if 'index' not in df_processed.columns:
             print(f"Errore: Colonna 'index' non trovata dopo reset_index per {os.path.basename(filepath_html)}")
             return False
        df_processed.rename(columns={'index': 'Attributo'}, inplace=True)
        if 'Attributo' not in df_processed.columns:
             print(f"Errore: Rinomina in 'Attributo' fallita per {os.path.basename(filepath_html)}")
             return False
        df_processed['Attributo'] = df_processed['Attributo'].map(rename_map).fillna(df_processed['Attributo'])

        header_values = df_processed.columns.tolist()
        cell_values = [df_processed[col].astype(str).replace('nan', 'N/D').tolist() for col in header_values]

        # MODIFICATO: Aggiunti indici per colorazione nuove righe
        try:
            classe_row_index = df_processed[df_processed['Attributo'] == 'Classe'].index[0]
        except (IndexError, KeyError):
            classe_row_index = -1
        try:
            target_row_index = df_processed[df_processed['Attributo'] == 'Classe Target'].index[0]
        except (IndexError, KeyError):
            target_row_index = -1
        try:
            qual_inv_row_index = df_processed[df_processed['Attributo'] == 'Qualità Inv.'].index[0]
        except (IndexError, KeyError):
            qual_inv_row_index = -1
        try:
            qual_est_row_index = df_processed[df_processed['Attributo'] == 'Qualità Est.'].index[0]
        except (IndexError, KeyError):
            qual_est_row_index = -1
        try:
            rinnov_row_index = df_processed[df_processed['Attributo'] == 'Rinnovabili'].index[0]
        except (IndexError, KeyError):
            rinnov_row_index = -1


        cell_colors = []
        # Colora la prima colonna (Attributi)
        cell_colors.append(['#e9ecef' for i in range(len(df_processed))]) 
        
        # Colora le colonne dei dati (ogni APE)
        for ape_file_col in header_values[1:]:
            col_colors = []
            for i, row in df_processed.iterrows():
                val = row[ape_file_col]
                # MODIFICATO: Logica di colorazione estesa
                if i == classe_row_index or i == target_row_index:
                    col_colors.append(CLASSE_COLORS.get(val, '#B0B0B0'))
                elif i == qual_inv_row_index or i == qual_est_row_index:
                    col_colors.append(QUALITA_COLORS.get(val, '#ffffff'))
                elif i == rinnov_row_index:
                    col_colors.append(RINNOVABILI_COLORS.get(val, '#ffffff'))
                else:
                    # Colore di sfondo alternato standard
                    col_colors.append('#ffffff' if i % 2 == 0 else '#f8f9fa')
            cell_colors.append(col_colors)

        fig = go.Figure(data=[go.Table(
            columnwidth = [1.5] + [1] * (len(header_values) - 1),
            header=dict(
                values=[f"<b>{h}</b>" for h in header_values],
                fill_color='#343a40', font=dict(color='white', size=12),
                align=['left'] + ['center'] * (len(header_values) - 1),
                line_color='darkslategray'
            ),
            cells=dict(
                values=cell_values, fill_color=cell_colors,
                align=['left'] + ['center'] * (len(header_values) - 1),
                font=dict(size=11), height=28, line_color='lightgrey'
            )
        )])
        # --- End Vertical Table Logic ---

    else:
        # --- Horizontal Table Logic ---
        df_processed = df_display[cols_existing].copy()
        df_processed.fillna('N/D', inplace=True) # Riempi NaN per la visualizzazione

        header_values = readable_cols 
        cell_values = [df_processed[col].astype(str).tolist() for col in cols_existing]

        # Colori di riga alternati di default
        row_colors = ['#ffffff' if i % 2 == 0 else '#f2f2f2' for i in range(len(df_processed))]

        # MODIFICATO: Logica di colorazione estesa
        fill_color_list = []
        for col_name in cols_existing:
            if col_name == 'classe' or col_name == 'intervento_classe_target':
                fill_color_list.append(df_processed[col_name].map(CLASSE_COLORS).fillna('#B0B0B0'))
            elif col_name == 'qualita_invernale' or col_name == 'qualita_estiva':
                 fill_color_list.append(df_processed[col_name].map(QUALITA_COLORS).fillna('#ffffff'))
            elif col_name == 'fonti_rinnovabili':
                fill_color_list.append(df_processed[col_name].map(RINNOVABILI_COLORS).fillna('#ffffff'))
            else:
                fill_color_list.append(row_colors) # Colore di riga standard

        fig = go.Figure(data=[go.Table(
             header=dict(
                 values=[f"<b>{h}</b>" for h in header_values],
                 fill_color='#2c7fb8', font=dict(color='white', size=14),
                 align='left', line_color='darkslategray'
             ),
             cells=dict(
                 values=cell_values,
                 fill_color=fill_color_list, 
                 align='left', font=dict(size=12),
                 height=30, line_color='lightgrey'
             )
        )])
        # --- End Horizontal Table Logic ---

    # --- Common Layout and Saving ---
    try:
        indirizzo_titolo = df['indirizzo'].iloc[0] if not df.empty else "Indirizzo non disponibile"
    except Exception:
        indirizzo_titolo = "Indirizzo non disponibile"
    fig.update_layout(
        title=f"<b>Confronto APE ({orientation}) per: {indirizzo_titolo}</b><br><sup>{catasto_subtitle}</sup>",
        margin=dict(l=15, r=15, t=70, b=15)
    )

    try:
        pio.show(fig)
        # pio.write_html(fig, filepath_html, auto_open=False)
        # Aumentata la larghezza di default per accomodare più colonne
        # pio.write_image(fig, filepath_png, engine='kaleido', format='png', width=1800, height=800, scale=2)
        return True
    except Exception as e:
        print(f"Errore durante il salvataggio dei grafici ({orientation.lower()}) per {os.path.basename(filepath_html)}: {e}")
        return False


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_list = [os.path.basename(f) for f in glob.glob(os.path.join(path, "*.xml"))]
    output_filename = os.path.join(script_dir, 'ape_detailed_data.parquet')
    
    print(f"Inizio elaborazione. Output: {output_filename}")
    df_ape = _load_ape_df(file_list)
    
    # Salvataggio finale (ordinato)
    print(f"Salvataggio finale ordinato in {output_filename}...")
    df_ape.to_parquet(output_filename, index=False)
    print("Completato.")
