#!/usr/bin/env python3
"""
Test Completo Sistema Synthetic Evaluation - ALL-IN-ONE STANDALONE

Sistema di test per piattaforma di valorizzazione immobili abbandonati MEF.
La piattaforma supporta esperti del Ministero dell'Economia e delle Finanze
che devono decidere come riqualificare immobili dismessi nel comune di Torino,
ipotizzando possibili destinazioni d'uso (studentato, asilo nido, centro anziani, ecc.).

Test automatico su tutti e 5 gli use case:
- Generazione dataset sintetico (immobili abbandonati)
- Creazione ground truth con valutazioni esperto
- Valutazione ranking
- Test consistenza
- Report aggregato comparativo

Configurazione fissa:
- 50 immobili per use case
- 5 POI per categoria
- 3 run di consistency test

Usage:
    python test_synthetic_evaluation.py
"""

import json
import os
import sys
import random
import re
import time
import shutil
import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from itertools import combinations

import pandas as pd
import numpy as np
import logging

# Import per gestire ChatPromptTemplate
try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:
    ChatPromptTemplate = None

# Carica variabili d'ambiente
from dotenv import load_dotenv
load_dotenv()

# Aggiungi project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.llm.langchain_client import get_langfuse_client, flush_langfuse
from app.services.analysis_service import analysis_service


# ============================================================================
# CONFIGURAZIONE USE CASES
# ============================================================================

USE_CASE_CONFIGS = {
    "studentato": {
        "superficie_range": (300, 800),
        "prezzo_mq_range": (1200, 2200),
        "piano_range": (0, 5),
        "locali_range": (10, 30),
        "poi_categories": ["università", "mensa", "biblioteca", "supermercato", "trasporti"],
        "poi_max_distance": 2000,
        "required_features": ["internet", "riscaldamento", "ascensore"],
        "preferred_typologies": ["ufficio", "residenziale", "commerciale"],
        "ape_classes": ["A", "B", "C"],
        "test_queries": [
            "Cerca un edificio dismesso vicino a Palazzo Nuovo con superficie totale di 500 m² per farne uno studentato strutturato a micro alloggi di circa 40-60 m² ciascuno. Preferirei un edificio con classe energetica alta per ridurre i costi di gestione.",
            "Cerco immobile zona Crocetta, superficie 400-600 m², da convertire in studentato. Vicinanza Politecnico essenziale, accesso mezzi pubblici entro 300m. Budget contenuto, anche classe energetica C accettabile.",
            "Edificio abbandonato zona Centro, minimo 350 m², per studentato universitario. Deve avere almeno 8-10 locali per creare micro appartamenti. Presenza trasporti pubblici e supermercati nel raggio di 500m.",
            "Cerco stabile dismesso zona Aurora, superficie 450-700 m², per residenza studentesca. Priorità: vicinanza università (max 1.5km), buona connessione internet, possibilità installazione ascensore.",
            "Immobile inutilizzato zona San Salvario, circa 550 m², da riqualificare per alloggi studenti. Essenziale: piano terra o basso per accessibilità, vicinanza mense universitarie, classe energetica B o superiore."
        ]
    },
    "asilo_nido": {
        "superficie_range": (250, 500),
        "prezzo_mq_range": (1200, 2000),
        "piano_range": (0, 2),
        "locali_range": (8, 15),
        "poi_categories": ["parco", "ospedale", "farmacia", "supermercato", "trasporti"],
        "poi_max_distance": 500,
        "required_features": ["giardino", "accesso_disabili", "sicurezza"],
        "preferred_typologies": ["residenziale", "scolastico", "commerciale"],
        "ape_classes": ["A", "B"],
        "test_queries": [
            "Cerca un edificio abbandonato in zona residenziale, possibilmente con spazio esterno, da riconvertire in asilo nido per 30-40 bambini. Superficie indicativa 350 m². Vicinanza a parchi e servizi sanitari fondamentale. Classe energetica minima B per sostenibilità gestionale.",
            "Immobile dismesso zona Crocetta, 300-450 m², per asilo nido 0-3 anni. Indispensabile: giardino privato minimo 100 m², piano terra, vicinanza ospedale pediatrico entro 800m. Classe A preferibile.",
            "Cerco ex scuola o edificio pubblico zona Lingotto, superficie 280-400 m², da convertire in asilo nido. Requisiti: spazi esterni sicuri, accessibilità totale, parcheggio nelle vicinanze, farmacie entro 300m.",
            "Edificio abbandonato Centro storico, circa 320 m², per nido comunale. Essenziale: locali ampi e luminosi, possibilità adattamento normativa sicurezza bambini, parco pubblico raggiungibile a piedi.",
            "Stabile inutilizzato zona San Salvario, 350-480 m², per asilo nido aziendale. Priorità: ottima classe energetica (A), accesso disabili, vicinanza supermercati per logistica, trasporti pubblici."
        ]
    },
    "micronido": {
        "superficie_range": (120, 250),
        "prezzo_mq_range": (1300, 2100),
        "piano_range": (0, 1),
        "locali_range": (4, 8),
        "poi_categories": ["parco", "farmacia", "supermercato", "trasporti"],
        "poi_max_distance": 400,
        "required_features": ["giardino", "accesso_disabili"],
        "preferred_typologies": ["residenziale", "commerciale"],
        "ape_classes": ["A", "B", "C"],
        "test_queries": [
            "Cerca un immobile dismesso adatto per micronido (max 12 bambini) in zona residenziale tranquilla. Superficie circa 150-180 m², preferibilmente con piccolo giardino o terrazzo. Vicinanza a parchi verde e collegamenti mezzi pubblici importante.",
            "Piccolo edificio abbandonato zona Aurora, 130-200 m², per micronido familiare. Requisiti: piano terra, spazio esterno anche piccolo, zona tranquilla lontano da traffico. Budget limitato, classe C accettabile.",
            "Ex negozio o piccolo ufficio zona Crocetta, circa 160 m², da convertire in micronido. Necessario: accesso autonomo, possibilità ristrutturazione interna, vicinanza fermata bus, farmacia nel raggio 400m.",
            "Immobile dismesso Centro, 140-190 m², per micronido privato. Essenziale: locali tutti allo stesso piano, illuminazione naturale ottima, piccolo cortile o terrazzo per giochi all'aperto.",
            "Cerco appartamento o locale commerciale inutilizzato zona Lingotto, 170-220 m², per micronido aziendale. Priorità: accessibilità auto per genitori, parcheggio vicino, struttura già a norma o facilmente adattabile."
        ]
    },
    "centro_anziani": {
        "superficie_range": (300, 600),
        "prezzo_mq_range": (1000, 1800),
        "piano_range": (0, 2),
        "locali_range": (10, 20),
        "poi_categories": ["ospedale", "farmacia", "parco", "supermercato", "trasporti"],
        "poi_max_distance": 800,
        "required_features": ["ascensore", "accesso_disabili", "sicurezza"],
        "preferred_typologies": ["residenziale", "sanitario", "ufficio"],
        "ape_classes": ["B", "C"],
        "test_queries": [
            "Cerca un edificio pubblico dismesso da riconvertire in centro diurno per anziani. Superficie minima 400 m² con possibilità di sale attività, ambulatorio e mensa. Essenziale presenza ascensore e accessibilità totale. Vicinanza presidi sanitari e farmacie entro 500m.",
            "Ex ambulatorio o ufficio pubblico zona Crocetta, 350-550 m², per centro diurno anziani. Requisiti critici: ascensore funzionante, accessibilità carrozzine, farmacia entro 300m, ospedale entro 1km.",
            "Immobile dismesso zona Lingotto, superficie 420-580 m², per centro servizi terza età. Necessario: ampi spazi comuni, cucina attrezzabile per mensa, bagni accessibili, parcheggio limitrofo.",
            "Cerco ex scuola o centro civico abbandonato zona San Salvario, minimo 450 m², per centro diurno. Priorità: piano unico o max 2 piani con ascensore, giardino o terrazzo, vicinanza parco pubblico.",
            "Edificio pubblico inutilizzato Centro storico, 380-500 m², da riqualificare per anziani. Essenziale: ottima accessibilità trasporti pubblici, servizi sanitari nel raggio 600m, classe energetica B minimo per comfort."
        ]
    },
    "centro_incontro": {
        "superficie_range": (200, 400),
        "prezzo_mq_range": (1100, 2000),
        "piano_range": (0, 3),
        "locali_range": (6, 12),
        "poi_categories": ["trasporti", "parcheggio", "supermercato"],
        "poi_max_distance": 1000,
        "required_features": ["accesso_disabili", "parcheggio"],
        "preferred_typologies": ["residenziale", "commerciale", "culturale", "ufficio"],
        "ape_classes": ["B", "C", "D"],
        "test_queries": [
            "Cerca un edificio abbandonato da valorizzare come centro di aggregazione sociale e culturale. Superficie circa 250-300 m² con spazi flessibili per attività multiple. Buoni collegamenti trasporti pubblici e possibilità parcheggio nelle vicinanze. Preferibile zona centrale o semi-centrale.",
            "Ex circolo o biblioteca dismessa zona Aurora, 220-350 m², per centro culturale di quartiere. Requisiti: spazi modulabili, accesso disabili, fermata bus/tram entro 200m. Classe energetica non prioritaria.",
            "Immobile commerciale abbandonato zona Crocetta, 280-400 m², per centro incontro giovanile. Necessario: ampia sala principale, possibilità suddivisione spazi, parcheggio auto nelle vicinanze.",
            "Cerco ex cinema o teatro dismesso Centro storico, superficie 300-450 m², per spazio culturale polifunzionale. Priorità: visibilità e accessibilità ottima, collegamenti trasporti pubblici eccellenti.",
            "Edificio pubblico inutilizzato zona Lingotto, 260-380 m², per centro aggregazione sociale. Essenziale: spazi flessibili adattabili a eventi, attività ricreative, corsi. Parcheggio e supermercato entro 500m."
        ]
    }
}


POI_TEMPLATES = {
    "università": [
        {"name": "Politecnico di Torino", "lat": 45.0628, "lon": 7.6621},
        {"name": "Università di Torino", "lat": 45.0703, "lon": 7.6869},
        {"name": "Campus Luigi Einaudi", "lat": 45.0736, "lon": 7.6603},
    ],
    "ospedale": [
        {"name": "Ospedale Molinette", "lat": 45.0344, "lon": 7.6635},
        {"name": "Ospedale San Giovanni Bosco", "lat": 45.0833, "lon": 7.7058},
    ],
    "parco": [
        {"name": "Parco del Valentino", "lat": 45.0547, "lon": 7.6861},
        {"name": "Parco della Pellerina", "lat": 45.0886, "lon": 7.6364},
    ],
    "mensa": [
        {"name": "Mensa Universitaria", "lat": 45.0705, "lon": 7.6870},
        {"name": "Mensa Politecnico", "lat": 45.0630, "lon": 7.6625},
    ],
    "biblioteca": [
        {"name": "Biblioteca Nazionale", "lat": 45.0706, "lon": 7.6919},
    ],
    "farmacia": [
        {"name": "Farmacia Comunale 1", "lat": 45.0650, "lon": 7.6700},
    ],
    "supermercato": [
        {"name": "Carrefour", "lat": 45.0656, "lon": 7.6789},
        {"name": "Esselunga", "lat": 45.0756, "lon": 7.6689},
    ],
    "trasporti": [
        {"name": "Stazione Porta Nuova", "lat": 45.0614, "lon": 7.6781},
        {"name": "Stazione Porta Susa", "lat": 45.0706, "lon": 7.6661},
    ],
    "parcheggio": [
        {"name": "Parcheggio Valentino", "lat": 45.0560, "lon": 7.6850},
    ],
}


TIPOLOGIE = ["ufficio", "residenziale", "commerciale", "scolastico", "culturale", "sanitario"]


ZONE_TORINO = [
    {"name": "Centro", "lat_center": 45.0703, "lon_center": 7.6869},
    {"name": "Crocetta", "lat_center": 45.0547, "lon_center": 7.6861},
    {"name": "San Salvario", "lat_center": 45.0519, "lon_center": 7.6747},
    {"name": "Lingotto", "lat_center": 45.0297, "lon_center": 7.6650},
    {"name": "Aurora", "lat_center": 45.0833, "lon_center": 7.6922},
]


# Agenti disponibili per ablation
AVAILABLE_AGENTS = [
    "location_agent",
    "typology_agent",
    "poi_category_agent",
    "poi_amenity_agent",
    "ape_agent",
    "normative_agent",
    "consistency_agent",
    "sql_agent",
    "evaluation_agent"
]


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class RankingMetrics:
    """Metriche per singolo prompt."""
    prompt_id: str
    query: str
    predicted_count: int
    expected_count: int
    matched_count: int
    recall_at_k: float
    precision_at_k: float
    f1_at_k: float
    ndcg_at_k: float
    mrr: float
    matched_ids: List[str]
    missing_ids: List[str]
    extra_ids: List[str]
    position_deltas: Dict[str, int]
    success: bool
    error_msg: Optional[str]
    latency_ms: float


@dataclass
class ConsistencyMetrics:
    """Metriche di consistenza tra multiple run."""
    prompt_id: str
    num_runs: int
    avg_matched_count: float
    std_matched_count: float
    coefficient_variation: float
    jaccard_similarity_avg: float
    jaccard_similarity_min: float
    jaccard_similarity_max: float
    avg_position_variance: float
    avg_recall: float
    avg_precision: float
    avg_ndcg: float
    avg_mrr: float
    runs_metrics: List[Dict[str, Any]]


class AgentLogger:
    """Logger per tracciare input/output di ogni agente."""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_log_file = None
        self.log_data = []
    
    def start_evaluation(self, use_case: str, prompt_id: str, run_number: int, timestamp: str):
        """Inizializza un nuovo file di log per una specifica valutazione."""
        log_filename = f"agent_traces_{use_case}_{prompt_id}_run{run_number}_{timestamp}.jsonl"
        self.current_log_file = self.log_dir / log_filename
        self.log_data = []
        
        # Scrivi header
        header = {
            "use_case": use_case,
            "prompt_id": prompt_id,
            "run_number": run_number,
            "timestamp": datetime.now().isoformat()
        }
        self.log_data.append(header)  # Aggiungi a log_data per poterlo usare dopo
        self._write_log_entry(header)
    
    def log_agent_execution(self, agent_name: str, input_data: Any, output_data: Any, 
                           execution_time_ms: float, metadata: Optional[Dict] = None):
        """Registra l'esecuzione di un singolo agente con campi selezionati."""
        
        # Estrai input dall'input (se presente)
        input_extracted = None
        if isinstance(input_data, dict):
            # Se l'input è un PromptRecord (ha chiavi system/user/full_text), usalo direttamente
            if 'system' in input_data or 'user' in input_data or 'full_text' in input_data:
                input_extracted = input_data
            else:
                # Altrimenti cerca input in vari modi possibili
                input_extracted = input_data.get('prompt') or input_data.get('query') or input_data.get('input')
        
        # Estrai output dall'output (se presente)
        output_extracted = None
        if agent_name.lower() == "ape-agent" and hasattr(output_data, 'suggested_filters'):
            output_extracted = output_data.suggested_filters
        elif agent_name == "consistency-agent" and hasattr(output_data, 'requirements'):
            output_extracted = output_data.requirements
        elif hasattr(output_data, 'raw_text'):
            output_extracted = output_data.raw_text
        elif isinstance(output_data, dict) and 'raw_text' in output_data:
            output_extracted = output_data['raw_text']
        
        log_entry = {
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat(),
            "execution_time_ms": execution_time_ms,
            "input": self._serialize_data(input_extracted) if input_extracted is not None else None,
            "output": self._serialize_data(output_extracted) if output_extracted is not None else None,
            "output_structure": self._serialize_data(output_data) if output_data is not None else None
        }
        self.log_data.append(log_entry)
        self._write_log_entry(log_entry)
    
    def end_evaluation(self, success: bool, error_msg: Optional[str] = None):
        """Finalizza il log per questa valutazione."""
        footer = {
            "type": "evaluation_end",
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "error_msg": error_msg,
            "total_agents_executed": len([e for e in self.log_data if "agent_name" in e])
        }
        
        # Aggiungi info dalla valutazione se disponibile
        if self.log_data and "use_case" in self.log_data[0] and "prompt_id" in self.log_data[0]:
            eval_start = self.log_data[0]
            footer.update({
                "use_case": eval_start.get("use_case"),
                "prompt_id": eval_start.get("prompt_id"), 
                "run_number": eval_start.get("run_number"),
                "start_timestamp": eval_start.get("timestamp")
            })
        
        # NON scrivere footer nel log
        
        # Crea anche un file JSON completo per questa run
        if self.current_log_file:
            json_file = self.current_log_file.with_suffix(".json")
            with open(json_file, 'w', encoding='utf-8') as f:
                # Prendi l'evaluation_start come base
                eval_start = self.log_data[0] if self.log_data and "use_case" in self.log_data[0] else {}
                
                # Estrai le proprietà della run
                run_props = {
                    "use_case": eval_start.get("use_case"),
                    "prompt_id": eval_start.get("prompt_id"),
                    "run_number": eval_start.get("run_number"),
                    "run_timestamp": eval_start.get("timestamp")
                }
                
                # Processa agent_executions SENZA aggregare evaluation-agent
                agent_executions = []
                batch_counter = 1
                
                for e in self.log_data:
                    if "agent_name" in e:
                        if e["agent_name"] == "evaluation-agent":
                            # Invece di aggregare, crea esecuzioni separate per ogni batch
                            if isinstance(e.get("output"), list):
                                for item in e["output"]:
                                    if isinstance(item, dict):
                                        agent_entry = {
                                            **run_props,  # Aggiungi proprietà run
                                            "agent_name": "evaluation-agent",
                                            "batch_id": batch_counter,
                                            "timestamp": e.get("timestamp"),
                                            "execution_time_ms": e.get("execution_time_ms"),
                                            "input": e.get("input"),
                                            "output": item  # Singolo batch invece dell'array completo
                                        }
                                        agent_executions.append(agent_entry)
                                    else:
                                        # Se item non è un dict, aggiungilo come valore semplice
                                        agent_entry = {
                                            **run_props,  # Aggiungi proprietà run
                                            "agent_name": "evaluation-agent", 
                                            "batch_id": batch_counter,
                                            "timestamp": e.get("timestamp"),
                                            "execution_time_ms": e.get("execution_time_ms"),
                                            "input": e.get("input"),
                                            "output": item
                                        }
                                        agent_executions.append(agent_entry)
                                    batch_counter += 1
                            else:
                                # Se output non è una lista, trattalo come singola esecuzione
                                agent_entry = {
                                    **run_props,  # Aggiungi proprietà run
                                    "agent_name": "evaluation-agent",
                                    "batch_id": batch_counter,
                                    "timestamp": e.get("timestamp"),
                                    "execution_time_ms": e.get("execution_time_ms"),
                                    "input": e.get("input"),
                                    "output": e.get("output")
                                }
                                agent_executions.append(agent_entry)
                                batch_counter += 1
                        else:
                            # Altri agenti: aggiungi proprietà run e batch_id=None
                            agent_entry = {**run_props, **e, "batch_id": None}
                            agent_executions.append(agent_entry)
                
                # Crea oggetto finale solo con agent_executions
                log_data = {"agent_executions": agent_executions}
                
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            # Elimina il file JSONL dopo aver creato il JSON aggregato
            if self.current_log_file and self.current_log_file.exists():
                try:
                    self.current_log_file.unlink()
                    print(f"🗑️ JSONL eliminato: {self.current_log_file.name}")
                except Exception as e:
                    print(f"⚠️ Errore nell'eliminare JSONL {self.current_log_file.name}: {e}")
            
            # === SALVATAGGIO DATAFRAME ===
            try:
                # DataFrame per TUTTE le agent executions (inclusi evaluation batch separati)
                agent_rows = []
                for execution in agent_executions:
                    # Funzione helper per convertire input/output in stringa o tabella HTML
                    def to_display_value(value, field_name=None):
                        if value is None:
                            return None
                        elif field_name == "output_structure" and isinstance(value, dict):
                            # Per output_structure, mostra solo le chiavi (nomi delle proprietà)
                            return "\n".join(sorted(value.keys()))
                        elif isinstance(value, dict):
                            # Se è un dict (come evaluation batch), crea tabella HTML inline
                            return self._dict_to_html_table(value)
                        elif isinstance(value, list):
                            # Se è una lista di dict, crea tabella con righe multiple
                            if value and isinstance(value[0], dict):
                                return self._list_of_dicts_to_html_table(value)
                            else:
                                return "\n".join(str(item) for item in value)
                        else:
                            # Per output non-JSON, applica parsing markdown semplice
                            if field_name == "output":
                                return self._parse_markdown_simple(str(value))
                            else:
                                return str(value)
                    
                    agent_rows.append({
                        "use_case": execution.get("use_case"),
                        "prompt_id": execution.get("prompt_id"),
                        "run_number": execution.get("run_number"),
                        "run_timestamp": execution.get("run_timestamp"),
                        "batch_id": execution.get("batch_id"),
                        "agent_name": execution.get("agent_name"),
                        "timestamp": execution.get("timestamp"),
                        "execution_time_ms": execution.get("execution_time_ms"),
                        "input": to_display_value(execution.get("input"), "input"),
                        "output_structure": to_display_value(execution.get("output_structure"), "output_structure"),
                        "output": to_display_value(execution.get("output"), "output")
                    })
                
                agent_df = pd.DataFrame(agent_rows)
                
                # Aggiungi colonna retry_id
                # Raggruppa per agent_name e run_number per identificare retry
                agent_df['retry_id'] = agent_df.groupby(['agent_name', 'run_number']).cumcount() + 1
                
                # Riordina colonne nell'ordine desiderato
                desired_order = [
                    'use_case', 'prompt_id', 'run_number', 'run_timestamp', 
                    'agent_name', 'batch_id', 'retry_id', 'timestamp',
                    'execution_time_ms', 'input', 'output_structure', 'output'
                ]
                # Mantieni solo le colonne che esistono nel DataFrame
                existing_columns = [col for col in desired_order if col in agent_df.columns]
                agent_df = agent_df[existing_columns]
                
                # Converti timestamp in datetime se possibile
                if "run_timestamp" in agent_df.columns:
                    agent_df["run_timestamp"] = pd.to_datetime(agent_df["run_timestamp"], errors='coerce')
                if "timestamp" in agent_df.columns:
                    agent_df["timestamp"] = pd.to_datetime(agent_df["timestamp"], errors='coerce')
                
                # Salva HTML per visualizzazione testi lunghi
                html_dir = self.log_dir
                agent_html = html_dir / f"agent_executions_{run_props.get('use_case')}_{run_props.get('prompt_id')}_run{run_props.get('run_number')}.html"
                
                self._save_as_html(agent_df, agent_html, "Agent Executions (All)")
                
                print(f"💾 HTML salvato: {agent_html.name}")
                
                # Elimina il file JSON dopo aver creato l'HTML
                if json_file.exists():
                    try:
                        json_file.unlink()
                        print(f"🗑️ JSON eliminato: {json_file.name}")
                    except Exception as e:
                        print(f"⚠️ Errore nell'eliminare JSON {json_file.name}: {e}")
                    
            except Exception as e:
                print(f"⚠️ Errore nel salvare DataFrame Parquet: {e}")
                import traceback
                traceback.print_exc()
    
    def _write_log_entry(self, entry: Dict):
        """Scrive una singola entry nel file JSONL."""
        if self.current_log_file and self.current_log_file.exists():
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def _dict_to_html_table(self, data: dict) -> str:
        """Converte un dizionario in una tabella HTML inline."""
        if not data:
            return ""
        
        html = '<table class="subtable" style="border-collapse: collapse; font-size: 11px; margin: 2px 0;">'
        
        for key, value in data.items():
            # Gestisci valori complessi ricorsivamente
            if isinstance(value, dict):
                display_value = self._dict_to_html_table(value)
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    display_value = self._list_of_dicts_to_html_table(value)
                else:
                    display_value = '<br>'.join(str(item) for item in value)
            else:
                display_value = str(value).replace('\n', '<br>')
            
            html += f'<tr><td style="border: 1px solid #ccc; padding: 2px 4px; background-color: #f9f9f9; font-weight: bold;">{key}</td>'
            html += f'<td style="border: 1px solid #ccc; padding: 2px 4px;">{display_value}</td></tr>'
        
        html += '</table>'
        return html
    
    def _list_of_dicts_to_html_table(self, data: list) -> str:
        """Converte una lista di dizionari in una tabella HTML inline."""
        if not data:
            return ""
        
        # Se è una lista di dict, crea tabella
        if isinstance(data[0], dict):
            # Ottieni tutte le chiavi possibili
            all_keys = set()
            for item in data:
                if isinstance(item, dict):
                    all_keys.update(item.keys())
            
            if not all_keys:
                return str(data)
            
            html = '<table class="subtable" style="border-collapse: collapse; font-size: 11px; margin: 2px 0;">'
            
            # Header
            html += '<tr>'
            for key in sorted(all_keys):
                html += f'<th style="border: 1px solid #ccc; padding: 2px 4px; background-color: #e8f5e8; font-weight: bold;">{key}</th>'
            html += '</tr>'
            
            # Righe
            for item in data:
                if isinstance(item, dict):
                    html += '<tr>'
                    for key in sorted(all_keys):
                        value = item.get(key, '')
                        if isinstance(value, dict):
                            display_value = self._dict_to_html_table(value)
                        elif isinstance(value, list):
                            if value and isinstance(value[0], dict):
                                display_value = self._list_of_dicts_to_html_table(value)
                            else:
                                display_value = '<br>'.join(str(item) for item in value)
                        else:
                            display_value = str(value).replace('\n', '<br>')
                        html += f'<td style="border: 1px solid #ccc; padding: 2px 4px;">{display_value}</td>'
                    html += '</tr>'
            
            html += '</table>'
            return html
        else:
            # Lista semplice: ogni elemento su una riga
            return '<br>'.join(str(item) for item in data)
    
    def _parse_markdown_simple(self, text: str) -> str:
        """Parsing markdown semplice per output non-JSON: ## diventa <strong>, ** diventa <strong>."""
        if not isinstance(text, str):
            return str(text)
        
        # Prima gestisci ## (intestazioni)
        import re
        text = re.sub(r'^##\s+(.+)$', r'<strong>\1</strong>', text, flags=re.MULTILINE)
        
        # Poi gestisci ** (grassetto)
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        
        return text
    
    def _save_as_html(self, df: pd.DataFrame, html_path: Path, title: str):
        """Salva DataFrame come HTML con formattazione ottimizzata per testi lunghi e colonne interattive."""
        try:
            # Converti DataFrame in HTML con stili
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            font-size: 12px;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }}
        
        /* Controlli colonne */
        .column-controls {{
            background-color: white;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .column-controls h3 {{
            margin-top: 0;
            color: #333;
        }}
        .column-checkboxes {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }}
        .column-checkboxes label {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 11px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            table-layout: fixed;
        }}
        
        /* Stili per tabella principale */
        #dataTable {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            table-layout: fixed;
        }}
        #dataTable th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: bold;
            position: sticky;
            top: 0;
            z-index: 10;
            position: relative;
        }}
        
        /* Stili per sottotabelle */
        table.subtable {{
            width: auto;
            min-width: 200px;
            margin: 2px 0;
            box-shadow: none;
            border: 1px solid #ccc;
        }}
        table.subtable th {{
            background-color: #f0f0f0 !important;
            color: black !important;
            padding: 4px 6px;
            text-align: left;
            font-weight: bold;
            font-size: 11px;
            position: relative;
            min-width: 50px;
        }}
        table.subtable td {{
            padding: 2px 4px;
            border-bottom: 1px solid #eee;
            font-size: 11px;
        }}
        table.subtable tr:nth-child(even) {{
            background-color: #fafafa;
        }}
        table.subtable tr:hover {{
            background-color: #f0f8f0;
        }}
        td {{
            padding: 8px;
            border-bottom: 1px solid #ddd;
            vertical-align: top;
            overflow: hidden;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #e8f5e8;
        }}
        
        /* Resize handles per tabella principale */
        #dataTable th {{
            position: relative;
            min-width: 50px;
        }}
        #dataTable th:not(:last-child)::after {{
            content: '';
            position: absolute;
            right: 0;
            top: 0;
            width: 4px;
            height: 100%;
            background-color: #ddd;
            cursor: col-resize;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        #dataTable th:not(:last-child):hover::after {{
            opacity: 1;
        }}
        #dataTable th.resizing {{
            background-color: #e8f5e8;
        }}
        
        /* Resize handles per sottotabelle */
        table.subtable th {{
            position: relative;
            min-width: 50px;
        }}
        table.subtable th:not(:last-child)::after {{
            content: '';
            position: absolute;
            right: 0;
            top: 0;
            width: 3px;
            height: 100%;
            background-color: #bbb;
            cursor: col-resize;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        table.subtable th:not(:last-child):hover::after {{
            opacity: 1;
        }}
        table.subtable th.resizing {{
            background-color: #e8f5e8 !important;
        }}
        
        .wide-column {{
            width: 200px;
            word-wrap: break-word;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
        }}
        .narrow-column {{
            width: 75px;
            word-wrap: break-word;
        }}
        .numeric-column {{
            text-align: right;
            font-family: 'Courier New', monospace;
            width: 50px;
        }}
        .timestamp-column {{
            font-family: 'Courier New', monospace;
            font-size: 11px;
            width: 90px;
        }}
        
        /* Hidden column class */
        .hidden-column {{
            display: none !important;
        }}
        
        /* Scroll hints */
        .scroll-hint {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            display: none;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    
    <div class="column-controls">
        <h3>Mostra/Nascondi Colonne</h3>
        <div class="column-checkboxes" id="columnCheckboxes">
"""

            # Aggiungi checkbox per ogni colonna
            wide_columns = ['input', 'output', 'output_structure']  # Colonne che dovrebbero essere wide
            for col in df.columns:
                # Per default, nascondi colonne tecniche, mostra colonne dati
                default_hidden = col in ['run_timestamp', 'timestamp', 'execution_time_ms', 'batch_id'] and col != 'batch_id'
                checked = "" if default_hidden else "checked"
                html_content += f'<label><input type="checkbox" {checked} data-column="{col}" onchange="toggleColumn(\'{col}\')"> {col}</label>'

            html_content += """
        </div>
    </div>
    
    <div style="overflow-x: auto;">
        <table id="dataTable">
"""

            # Aggiungi dropdown filtri per ogni colonna visibile
            # TEMPORANEAMENTE DISABILITATO PER DEBUG
            # for col in df.columns:
            #     if col in ['run_timestamp', 'timestamp', 'execution_time_ms', 'batch_id']:
            #         continue  # Salta colonne tecniche
            #         
            #     unique_values = df[col].dropna().unique()
            #     if len(unique_values) > 1 and len(unique_values) <= 50:  # Max 50 valori per evitare dropdown troppo grandi
            #         unique_values = sorted(unique_values, key=lambda x: str(x).lower())
            #         html_content += f'<div class="filter-item"><label for="filter_{col}">{col}</label><select multiple class="filter-dropdown" id="filter_{col}" data-column="{col}"><option value="all" selected>Tutti ({len(unique_values)})</option>'
            #         
            #         for value in unique_values:
            #             # Escape dei caratteri speciali per HTML
            #             escaped_value = str(value).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            #             display_value = escaped_value[:50] + "..." if len(escaped_value) > 50 else escaped_value
            #             html_content += f'<option value="{escaped_value}">{display_value}</option>'
            #         
            #         html_content += '</select></div>'

            # Header
            wide_columns = ['input', 'output', 'output_structure']  # Colonne che dovrebbero essere wide
            html_content += "        <thead><tr>"
            for col in df.columns:
                col_class = "wide-column" if col in wide_columns else "narrow-column"
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_class = "numeric-column"
                elif 'timestamp' in col.lower():
                    col_class = "timestamp-column"
                
                html_content += f'<th class="{col_class}" data-column="{col}">{col}</th>'
            html_content += "</tr></thead>\n"
            
            # Body
            html_content += "        <tbody>\n"
            for _, row in df.iterrows():
                html_content += "        <tr>"
                for col in df.columns:
                    value = row[col]
                    if pd.isna(value):
                        display_value = ""
                    else:
                        # Formattazione speciale per timestamp e execution time
                        if 'timestamp' in col.lower() and isinstance(value, pd.Timestamp):
                            display_value = value.strftime('%Y-%m-%d %H:%M:%S')
                        elif 'execution_time' in col.lower() and isinstance(value, (int, float)):
                            display_value = f"{int(value)}"
                        elif col == 'batch_id' and isinstance(value, (int, float)):
                            display_value = f"{int(value)}"
                        else:
                            display_value = str(value).replace('\n', '<br>').replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
                    
                    col_class = "wide-column" if col in wide_columns else "narrow-column"
                    if pd.api.types.is_numeric_dtype(df[col]):
                        col_class = "numeric-column"
                    elif 'timestamp' in col.lower():
                        col_class = "timestamp-column"
                    
                    html_content += f'<td class="{col_class}" data-column="{col}">{display_value}</td>'
                html_content += "</tr>\n"
            
            html_content += """        </tbody>
    </table>
    </div>
    
    <div class="scroll-hint" id="scrollHint">
        Suggerimento: Trascina le maniglie sui bordi delle colonne per ridimensionarle
    </div>

    <script>
        // Toggle colonne visibili/nascoste
        // NOTA: nasconde solo le celle della tabella (th/td), i checkbox rimangono sempre visibili
        function toggleColumn(columnName) {
            // Nasconde/mostra solo le celle della tabella (th e td), non il checkbox
            const tableElements = document.querySelectorAll(`th[data-column="${columnName}"], td[data-column="${columnName}"]`);
            const isChecked = document.querySelector(`input[data-column="${columnName}"]`).checked;
            
            tableElements.forEach(element => {
                if (isChecked) {
                    element.classList.remove('hidden-column');
                } else {
                    element.classList.add('hidden-column');
                }
            });
        }
        
        // Mostra hint di scroll quando necessario
        function checkScrollHint() {
            const table = document.getElementById('dataTable');
            const hint = document.getElementById('scrollHint');
            
            if (table.scrollWidth > table.clientWidth) {
                hint.style.display = 'block';
                setTimeout(() => {
                    hint.style.display = 'none';
                }, 3000);
            }
        }
        
        // Inizializzazione
        document.addEventListener('DOMContentLoaded', function() {
            // Applica impostazioni iniziali delle colonne
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                toggleColumn(checkbox.dataset.column);
            });
            
            // Controlla se mostrare hint di scroll
            setTimeout(checkScrollHint, 1000);
            
            // Salva preferenze colonne nel localStorage
            checkboxes.forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const preferences = {};
                    document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                        preferences[cb.dataset.column] = cb.checked;
                    });
                    localStorage.setItem('tableColumnPreferences', JSON.stringify(preferences));
                });
            });
            
            // Carica preferenze salvate
            const savedPreferences = localStorage.getItem('tableColumnPreferences');
            if (savedPreferences) {
                const preferences = JSON.parse(savedPreferences);
                Object.keys(preferences).forEach(column => {
                    const checkbox = document.querySelector(`input[data-column="${column}"]`);
                    if (checkbox) {
                        checkbox.checked = preferences[column];
                        toggleColumn(column);
                    }
                });
            }
        });
        
        // Gestione resize colonne con maniglie
        let isResizing = false;
        let currentColumn = null;
        let startX = 0;
        let startWidth = 0;
        
        document.addEventListener('mousedown', function(e) {
            // Controlla se il click è sulla maniglia di resize
            if (e.target.tagName === 'TH' && e.offsetX >= e.target.offsetWidth - 4) {
                isResizing = true;
                currentColumn = e.target;
                startX = e.clientX;
                startWidth = currentColumn.offsetWidth;
                currentColumn.classList.add('resizing');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
                e.preventDefault();
            }
        });
        
        document.addEventListener('mousemove', function(e) {
            if (!isResizing || !currentColumn) return;
            
            const delta = e.clientX - startX;
            const newWidth = Math.max(50, startWidth + delta);
            currentColumn.style.width = newWidth + 'px';
        });
        
        document.addEventListener('mouseup', function() {
            if (isResizing && currentColumn) {
                currentColumn.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
            isResizing = false;
            currentColumn = null;
        });
    </script>
</body>
</html>"""

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
        except Exception as e:
            print(f"⚠️ Errore nel salvare HTML {html_path.name}: {e}")
    
    def _serialize_data(self, data: Any) -> Any:
        """Serializza i dati in formato JSON-compatibile con parsing intelligente e unescaping ricorsivo."""
        
        def _unescape_string(text: str) -> str:
            """Unescapes caratteri speciali in una stringa in maniera ricorsiva."""
            if not isinstance(text, str):
                return text
            
            # Gestisci escaping multipli (ricorsivo)
            while '\\\\' in text:  # Prima gestisci doppi backslash
                text = text.replace('\\\\', '\\')
            
            # Unescape caratteri comuni
            unescape_map = {
                '\\n': '\n',
                '\\t': '\t',
                '\\r': '\r',
                '\\"': '"',
                "\\'": "'",
                '\\\\': '\\'
            }
            
            for escaped, unescaped in unescape_map.items():
                text = text.replace(escaped, unescaped)
            
            return text
        
        def _process_string_value(text: str, try_json: bool = True) -> Any:
            """Processa una stringa: tentativo parsing JSON + unescape."""
            if not text:
                return text
            
            # 1. Tenta prima il parsing JSON sul testo RAW (perché è già correttamente escaped)
            if try_json and text.strip().startswith(('{', '[')):
                try:
                    parsed = json.loads(text)
                    return self._serialize_data(parsed)
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass # Proseguiamo con tentativo riparazione o unescape
            
            # 2. Se non è JSON valido, facciamo unescape per la visualizzazione
            unescaped = _unescape_string(text)
            
            # 3. Se sembrava JSON ma è fallito prim, tenta riparazione su testo unescaped
            if try_json and unescaped.strip().startswith(('{', '[')):
                try:
                    # Ripara virgolette doppie annidate in valori stringa o liste
                    # Sostituisce "interno" con 'interno'
                    # Pattern 1: : "valore "interno" finale"
                    repaired = re.sub(r'(:\s*")(.+?)("\s*[,}])', 
                                     lambda m: m.group(1) + m.group(2).replace('"', "'") + m.group(3), 
                                     unescaped, flags=re.DOTALL)
                    # Pattern 2: [ "valore "interno" finale", ... ]
                    repaired = re.sub(r'(,\s*")(.+?)("\s*[,\]])', 
                                     lambda m: m.group(1) + m.group(2).replace('"', "'") + m.group(3), 
                                     repaired, flags=re.DOTALL)
                    # Pattern 3: [ "valore "interno" finale" ] (inizio lista)
                    repaired = re.sub(r'(\[\s*")(.+?)("\s*[,\]])', 
                                     lambda m: m.group(1) + m.group(2).replace('"', "'") + m.group(3), 
                                     repaired, flags=re.DOTALL)
                    
                    if repaired != unescaped:
                        try:
                            parsed = json.loads(repaired)
                            return self._serialize_data(parsed)
                        except:
                            pass
                except Exception:
                    pass
            
            # Se molto lunga con newline, splitta per leggibilità
            if len(unescaped) > 200 and '\n' in unescaped:
                return unescaped.split('\n')
            
            return unescaped
        
        # Stringhe: unescape e parsing JSON ricorsivo
        if isinstance(data, str):
            return _process_string_value(data)
        
        # Tipi primitivi
        elif isinstance(data, (int, float, bool, type(None))):
            return data
        
        # Dizionari: serializza ricorsivamente con gestione speciale per campi JSON
        elif isinstance(data, dict):
            # Se il dizionario ha struttura prompt {system, user, full_text}, restituisci solo full_text (senza parsing JSON)
            if 'full_text' in data and 'system' in data and 'user' in data:
                return _process_string_value(data['full_text'], try_json=False)
            
            result = {}
            for k, v in data.items():
                result[k] = self._serialize_data(v)
            return result
        
        # Liste e tuple: serializza elementi ricorsivamente
        elif isinstance(data, (list, tuple)):
            return [self._serialize_data(item) for item in data]
        
        # DataFrame Pandas
        elif isinstance(data, pd.DataFrame):
            return {
                "_type": "DataFrame",
                "shape": data.shape,
                "columns": data.columns.tolist(),
                "data_preview": data.head(5).to_dict('records') if len(data) > 0 else []
            }
        
        # ChatPromptTemplate: converti a full_text invece di mostrare struttura interna
        elif ChatPromptTemplate is not None and isinstance(data, ChatPromptTemplate):
            try:
                # Estrai i messaggi e formatta come full_text
                messages = []
                for msg in data.messages:
                    if hasattr(msg, 'content'):
                        msg_type = "SYSTEM" if msg.__class__.__name__ == "SystemMessage" else "USER"
                        messages.append(f"[{msg_type}]\n{msg.content}")
                    else:
                        messages.append(str(msg))
                return "\n\n".join(messages)
            except Exception:
                # Fallback se qualcosa va storto
                return f"ChatPromptTemplate: {str(data)}"
        
        # Pydantic models
        elif hasattr(data, 'model_dump'):
            dumped = data.model_dump()
            return self._serialize_data(dumped)
        
        # Oggetti con __dict__
        elif hasattr(data, '__dict__'):
            return self._serialize_data(data.__dict__)
        
        # Fallback: converti a stringa
        else:
            return str(data)


# ============================================================================
# GENERATORE DATASET SINTETICO
# ============================================================================

class SyntheticDataGenerator:
    """Generatore di dataset sintetico."""
    
    def __init__(self, num_immobili: int, num_poi_per_category: int, use_case: str, seed: int = 42):
        self.num_immobili = num_immobili
        self.num_poi_per_category = num_poi_per_category
        self.use_case = use_case
        random.seed(seed)
        np.random.seed(seed)
        self.output_dir = Path("synthetic_data")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_coordinate(self, zone: Dict) -> tuple:
        """Genera coordinate casuali in una zona."""
        lat_offset = random.gauss(0, 0.0045)
        lon_offset = random.gauss(0, 0.0065)
        return (zone["lat_center"] + lat_offset, zone["lon_center"] + lon_offset)
    
    def generate_immobile(self, idx: int, config: Dict, zone: Dict) -> Dict:
        """Genera singolo immobile con colonne già rinominate per compatibilità."""
        lat, lon = self.generate_coordinate(zone)
        superficie = random.randint(*config["superficie_range"])
        prezzo_mq = random.randint(*config["prezzo_mq_range"])
        classe_energetica = random.choice(config["ape_classes"])
        
        # Genera valori APE dettagliati basati sulla classe energetica
        ape_data = self._generate_ape_data(classe_energetica)
        
        immobile = {
            "id": f"IMM{idx:03d}",
            "tipologia_bene_immobile": random.choice(config["preferred_typologies"]),
            "superficie_totale": superficie,
            "prezzo": superficie * prezzo_mq,
            "prezzo_mq": prezzo_mq,
            "piano": random.randint(*config["piano_range"]),
            "numero_locali": random.randint(*config["locali_range"]),
            "lat": lat,
            "lon": lon,
            "zona_omi": zone["name"],
            "classe_energetica": classe_energetica,
            "anno_costruzione": random.randint(1970, 2023),
        }
        
        # Aggiungi dati APE
        immobile.update(ape_data)
        
        return immobile
    
    def _generate_ape_data(self, classe_energetica: str) -> Dict:
        """Genera valori APE dettagliati basati sulla classe energetica."""
        # Mapping delle classi APE dettagliate
        ape_class_mapping = {
            "A": ["A1", "A2", "A3", "A4"],
            "B": ["B1", "B2", "B3"], 
            "C": ["C1", "C2"],
            "D": ["D1", "D2"],
            "E": ["E1", "E2", "E3"],
            "F": ["F1"],
            "G": ["G"]
        }
        
        # Range di punteggi per classe energetica
        score_ranges = {
            "A": (85, 100),
            "B": (70, 84),
            "C": (55, 69),
            "D": (40, 54),
            "E": (25, 39),
            "F": (10, 24),
            "G": (0, 9)
        }
        
        # Seleziona classe APE dettagliata
        if classe_energetica in ape_class_mapping:
            classe_energetica_ape = random.choice(ape_class_mapping[classe_energetica])
        else:
            classe_energetica_ape = classe_energetica
        
        # Genera punteggi APE
        ape_score_classe = random.randint(1, 5)
        ape_score_impianto = random.randint(1, 5)
        ape_score_involucro = random.randint(1, 5)
        ape_score_rinnovabili = random.randint(1, 5)
        ape_score_total = ape_score_classe + ape_score_impianto + ape_score_involucro + ape_score_rinnovabili
        
        return {
            "classe_energetica_ape": classe_energetica_ape,
            "epglnren_ape": round(random.uniform(20, 200), 2),  # kWh/m² anno
            "classe_target_ape": random.choice(["A1", "A2", "B1", "B2"]),
            "ape_score_classe": ape_score_classe,
            "ape_score_impianto": ape_score_impianto,
            "ape_score_involucro": ape_score_involucro,
            "ape_score_rinnovabili": ape_score_rinnovabili,
            "ape_score_total": ape_score_total,
        }
    
    def generate_poi(self, category: str, idx: int) -> Dict:
        """Genera singolo POI."""
        if category in POI_TEMPLATES and POI_TEMPLATES[category]:
            template = random.choice(POI_TEMPLATES[category])
            lat = template["lat"] + random.gauss(0, 0.002)
            lon = template["lon"] + random.gauss(0, 0.003)
            name = f"{template['name']} {idx}" if idx > 0 else template["name"]
        else:
            zone = random.choice(ZONE_TORINO)
            lat, lon = self.generate_coordinate(zone)
            name = f"{category.title()} {idx+1}"
        
        return {
            "id": f"POI_{category}_{idx:03d}",
            "name": name,
            "category": category,
            "latitude": lat,
            "longitude": lon
        }
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcola distanza haversine in metri."""
        R = 6371000
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
        return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    
    def generate_all(self) -> tuple:
        """Genera tutto il dataset."""
        config = USE_CASE_CONFIGS[self.use_case]
        
        # Svuota cartella synthetic_data
        print("Pulizia cartella synthetic_data...")
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Genera immobili
        print(f"Generando {self.num_immobili} immobili...")
        immobili = []
        for i in range(self.num_immobili):
            zone = random.choice(ZONE_TORINO)
            immobile = self.generate_immobile(i + 1, config, zone)
            immobili.append(immobile)
        
        df_immobili = pd.DataFrame(immobili)
        
        # Genera POI
        print(f"Generando POI...")
        pois = []
        for category in config["poi_categories"]:
            for i in range(self.num_poi_per_category):
                poi = self.generate_poi(category, i)
                pois.append(poi)
        
        # Calcola distanze
        print(f"Calcolando distanze...")
        distances = []
        for immobile in immobili:
            for poi in pois:
                dist = self.haversine_distance(
                    immobile["lat"], immobile["lon"],
                    poi["latitude"], poi["longitude"]
                )
                distances.append({
                    "id_immobile": immobile["id"],
                    "poi_id": poi["id"],
                    "poi_category": poi["category"],
                    "distance_m": round(dist, 2)
                })
        
        df_distances = pd.DataFrame(distances)
        
        # Salva
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        immobili_file = self.output_dir / f"immobili_synthetic_{self.use_case}_{timestamp}.parquet"
        df_immobili.to_parquet(immobili_file, index=False)
        
        poi_file = self.output_dir / f"poi_synthetic_{self.use_case}_{timestamp}.json"
        with open(poi_file, 'w') as f:
            json.dump(pois, f, indent=2)
        
        distances_file = self.output_dir / f"distances_synthetic_{self.use_case}_{timestamp}.csv"
        df_distances.to_csv(distances_file, index=False)
        
        print(f"✓ Dataset generato:")
        print(f"  - Immobili: {immobili_file}")
        print(f"  - POI: {poi_file}")
        print(f"  - Distanze: {distances_file}")
        
        return immobili_file, poi_file, distances_file, df_immobili


# ============================================================================
# VALUTATORE RANKING
# ============================================================================

class RankingEvaluator:
    """Valutatore qualità ranking con ground truth."""
    
    def __init__(self, ground_truth_path: str, dataset_file: Path, k: int = 10, use_case: str = ""):
        self.ground_truth_path = Path(ground_truth_path)
        self.dataset_file = dataset_file
        self.k = k
        self.use_case = use_case
        
        with open(self.ground_truth_path, "r") as f:
            self.ground_truth = json.load(f)
        
        self.results_dir = Path("ranking_evaluation_results")
        self.results_dir.mkdir(exist_ok=True)
        
        # Crea logger per tracciare gli agenti
        self.agent_logs_dir = Path(__file__).parent / "agent_logs"
        self.agent_logs_dir.mkdir(exist_ok=True)
        self.agent_logger = AgentLogger(self.agent_logs_dir)
    
    def run_prediction(self, query: str, prompt_id: str = "", run_number: int = 1) -> Tuple[List[str], float, Optional[str]]:
        """Esegue predizione e ritorna lista ID ordinati."""
        # Genera session_id unico per questa query e imposta env vars per Langfuse
        session_id = f"synthetic_eval_{self.dataset_file.stem}_{hash(query) % 10000}"
        
        # Imposta variabili d'ambiente per tracciamento Langfuse
        import os
        os.environ["LANGFUSE_SESSION_ID"] = session_id
        os.environ["LANGFUSE_USER_ID"] = "ranking_eval_user"
        os.environ["LANGFUSE_TAGS"] = "synthetic_eval,ranking_test"

        def mock_set_progress(progress_data):
            pass
        
        # Inizializza logging per questa run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.agent_logger.start_evaluation(self.use_case, prompt_id, run_number, timestamp)
        
        start_time = time.time()
        
        # Log per debug Langfuse
        print(f"🔍 Running query with session_id: {session_id}")
        print(f"📝 Agent logs: {self.agent_logger.current_log_file}")
        
        try:
            # Monkey patch per catturare le chiamate agli agenti
            self._setup_agent_logging_hooks()
            
            # Load synthetic dataset
            if str(self.dataset_file).endswith('.parquet'):
                synthetic_dataset = pd.read_parquet(str(self.dataset_file))
            else:
                synthetic_dataset = pd.read_csv(str(self.dataset_file))
            
            # Generate unique run_id
            run_id = str(uuid.uuid4())
            
            # Run analysis using the new service with custom dataset
            result = asyncio.run(analysis_service.run_analysis(
                run_id=run_id,
                query=query,
                dataset_key="full",  # Keep for compatibility but won't be used
                map_limit=20,
                llm_limit=10,
                analysis_mode="agent",
                progress_callback=mock_set_progress,
                dataset=synthetic_dataset  # Pass custom dataset
            ))
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract buildings and convert to DataFrame
            buildings = result.get("buildings", [])
            if buildings:
                # Convert buildings to DataFrame
                map_df = pd.DataFrame([b.model_dump() for b in buildings])
                # Rename 'score' to 'evaluation_score' if it exists
                if 'score' in map_df.columns:
                    map_df = map_df.rename(columns={'score': 'evaluation_score'})
            else:
                map_df = None
            
            # Return tuple format expected by old code: (map_df, ...)
            result_tuple = (map_df, None, None, None)  # Mock other return values
            
            if map_df is not None and len(map_df) > 0:
                if "evaluation_score" in map_df.columns:
                    sorted_df = map_df.sort_values("evaluation_score", ascending=False)
                elif "ranking_score" in map_df.columns:
                    sorted_df = map_df.sort_values("ranking_score", ascending=False)
                else:
                    sorted_df = map_df
                
                ids = sorted_df["id"].head(self.k).tolist()
                self.agent_logger.end_evaluation(success=True)
                return ids, latency_ms, None
            else:
                self.agent_logger.end_evaluation(success=False, error_msg="No results returned")
                return [], latency_ms, "No results returned"
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.agent_logger.end_evaluation(success=False, error_msg=str(e))
            return [], latency_ms, str(e)
        
        # Flush immediato dopo ogni query per streaming
        finally:
            try:
                flush_langfuse()
            except:
                pass
            
            # Ripristina gli agent hooks
            try:
                self._restore_agent_hooks()
            except:
                pass
    
    def _setup_agent_logging_hooks(self):
        """Configura hooks per catturare input/output degli agenti."""
        import os
        os.environ["_AGENT_LOGGER_ACTIVE"] = "true"
        
        # Importa tutti gli agenti disponibili
        try:
            from app.services.llm.agents.location_agent import LocationAgent
            from app.services.llm.agents.typology_agent import TypologyAgent
            from app.services.llm.agents.ape_agent import ApeAgent
            from app.services.llm.agents.poi_category_agent import PoiCategoryAgent
            from app.services.llm.agents.poi_amenity_agent import PoiAmenityAgent
            from app.services.llm.agents.normative_agent import NormativeAgent
            from app.services.llm.agents.sql_agent import SQLAgent
            from app.services.llm.agents.evaluation_agent import EvaluationAgent
            from app.services.llm.agents.consistency_agent import ConsistencyAgent
            
            # Lista di classi di agenti da patchare
            agent_classes = [
                LocationAgent,
                TypologyAgent,
                ApeAgent,
                PoiCategoryAgent,
                PoiAmenityAgent,
                NormativeAgent,
                SQLAgent,
                EvaluationAgent,
                ConsistencyAgent
            ]
            
            # Salva i metodi originali per ripristinarli dopo
            if not hasattr(self, '_original_run_methods'):
                self._original_run_methods = {}
            
            # Patch ogni classe di agente
            for agent_class in agent_classes:
                agent_name = agent_class.name if hasattr(agent_class, 'name') else agent_class.__name__
                
                # Salva metodo originale
                if agent_class not in self._original_run_methods:
                    self._original_run_methods[agent_class] = agent_class.run
                
                # Crea wrapper con closure per catturare agent_name
                def create_logged_run(original_run, captured_agent_name, captured_logger):
                    def logged_run(self_agent, **kwargs):
                        agent_start = time.time()
                        input_data = kwargs.copy()
                        
                        try:
                            # Esegui metodo originale
                            result = original_run(self_agent, **kwargs)
                            execution_time = (time.time() - agent_start) * 1000
                            
                            # Se il result ha un prompt, usalo come input invece di kwargs
                            if hasattr(result, 'prompt') and result.prompt:
                                input_data = result.prompt.model_dump()
                            
                            # Log dell'esecuzione
                            captured_logger.log_agent_execution(
                                agent_name=captured_agent_name,
                                input_data=input_data,
                                output_data=result,
                                execution_time_ms=execution_time,
                                metadata={}
                            )
                            
                            return result
                        except Exception as e:
                            execution_time = (time.time() - agent_start) * 1000
                            captured_logger.log_agent_execution(
                                agent_name=captured_agent_name,
                                input_data=input_data,
                                output_data={"error": str(e), "error_type": type(e).__name__},
                                execution_time_ms=execution_time,
                                metadata={"error": True}
                            )
                            raise
                    return logged_run
                
                # Applica il patch
                agent_class.run = create_logged_run(
                    self._original_run_methods[agent_class],
                    agent_name,
                    self.agent_logger
                )
            
            print(f"✓ Agent logging hooks attivati per {len(agent_classes)} agenti")
            
        except Exception as e:
            print(f"⚠️ Impossibile configurare agent hooks: {e}")
            import traceback
            traceback.print_exc()
    
    def _restore_agent_hooks(self):
        """Ripristina i metodi originali degli agenti."""
        if hasattr(self, '_original_run_methods'):
            for agent_class, original_run in self._original_run_methods.items():
                agent_class.run = original_run
            print(f"✓ Agent hooks ripristinati")
    
    def calculate_ndcg(self, predicted_ids: List[str], expected_items: List[Dict]) -> float:
        """Calcola NDCG."""
        if not predicted_ids or not expected_items:
            return 0.0
        
        relevance_map = {item["id"]: item["score_expected"] / 100.0 for item in expected_items}
        
        dcg = sum(relevance_map.get(pred_id, 0.0) / np.log2(i + 2) for i, pred_id in enumerate(predicted_ids))
        
        ideal_relevances = sorted(relevance_map.values(), reverse=True)[:len(predicted_ids)]
        idcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(ideal_relevances))
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def calculate_mrr(self, predicted_ids: List[str], expected_ids: List[str]) -> float:
        """Calcola MRR."""
        for i, pred_id in enumerate(predicted_ids, start=1):
            if pred_id in expected_ids:
                return 1.0 / i
        return 0.0
    
    def jaccard_similarity(self, set1: set, set2: set) -> float:
        """Calcola Jaccard similarity."""
        if not set1 and not set2:
            return 1.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def evaluate_with_consistency(self, use_case: str, prompt_id: str, num_runs: int) -> Tuple[RankingMetrics, Optional[ConsistencyMetrics]]:
        """Valuta prompt con test di consistenza."""
        # Get expected
        use_case_data = self.ground_truth["use_cases"][use_case]
        prompt_data = next(p for p in use_case_data["prompts"] if p["prompt_id"] == prompt_id)
        expected_items = prompt_data["expected_top10"][:self.k]
        expected_ids = [item["id"] for item in expected_items]
        query = prompt_data["query"]
        
        # Genera session_id base per questa query
        session_id = f"synthetic_eval_{self.dataset_file.stem}_{hash(query) % 10000}"
        
        print(f"\n{'='*80}")
        print(f"Evaluating: {prompt_id}")
        if num_runs > 1:
            print(f"Consistency Test: {num_runs} runs")
        print(f"Query: {query}")
        print(f"Expected Top-{self.k}: {expected_ids}")
        print(f"{'='*80}")
        
        if num_runs == 1:
            # Single run
            predicted_ids, latency_ms, error_msg = self.run_prediction(query, prompt_id=prompt_id, run_number=1)
            
            # Flush immediato per streaming
            flush_langfuse()
            
            matched_ids = [pid for pid in predicted_ids if pid in expected_ids]
            missing_ids = [eid for eid in expected_ids if eid not in predicted_ids]
            extra_ids = [pid for pid in predicted_ids if pid not in expected_ids]
            
            recall = len(matched_ids) / len(expected_ids) if expected_ids else 0.0
            precision = len(matched_ids) / len(predicted_ids) if predicted_ids else 0.0
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            ndcg = self.calculate_ndcg(predicted_ids, expected_items)
            mrr = self.calculate_mrr(predicted_ids, expected_ids)
            
            position_deltas = {}
            for item in expected_items:
                eid = item["id"]
                if eid in predicted_ids:
                    position_deltas[eid] = predicted_ids.index(eid) + 1 - item["rank"]
            
            print(f"\n📊 Metrics:")
            print(f"  Matched: {len(matched_ids)}/{len(expected_ids)}")
            print(f"  Recall@{self.k}: {recall:.2%}")
            print(f"  NDCG@{self.k}: {ndcg:.3f}")
            
            metrics = RankingMetrics(
                prompt_id=prompt_id,
                query=query,
                predicted_count=len(predicted_ids),
                expected_count=len(expected_ids),
                matched_count=len(matched_ids),
                recall_at_k=recall,
                precision_at_k=precision,
                f1_at_k=f1,
                ndcg_at_k=ndcg,
                mrr=mrr,
                matched_ids=matched_ids,
                missing_ids=missing_ids,
                extra_ids=extra_ids,
                position_deltas=position_deltas,
                success=error_msg is None,
                error_msg=error_msg,
                latency_ms=latency_ms
            )
            return metrics, None
        
        else:
            # Multiple runs
            print(f"\nEsecuzione {num_runs} run...")
            all_results = []
            all_metrics = []
            
            for i in range(num_runs):
                # Imposta session_id unico per questa run
                run_session_id = f"{session_id}_run_{i+1}"
                trace_name = f"synthetic_eval_run_{i+1}"
                
                os.environ["LANGFUSE_SESSION_ID"] = run_session_id
                os.environ["LANGFUSE_TRACE_NAME"] = trace_name
                
                print(f"  Run {i+1}/{num_runs} - Session ID: {run_session_id}, Trace Name: {trace_name}...", end=" ", flush=True)
                
                predicted_ids, latency_ms, error_msg = self.run_prediction(query, prompt_id=prompt_id, run_number=i+1)
                
                # Flush immediato per streaming dopo ogni run
                flush_langfuse()
                
                if error_msg:
                    print(f"❌ Error")
                    continue
                
                matched_ids = [pid for pid in predicted_ids if pid in expected_ids]
                recall = len(matched_ids) / len(expected_ids) if expected_ids else 0.0
                precision = len(matched_ids) / len(predicted_ids) if predicted_ids else 0.0
                ndcg = self.calculate_ndcg(predicted_ids, expected_items)
                mrr = self.calculate_mrr(predicted_ids, expected_ids)
                
                print(f"✓ {len(matched_ids)}/{len(expected_ids)} matched ({latency_ms:.0f}ms)")
                
                all_results.append((predicted_ids, latency_ms))
                all_metrics.append({
                    "run_number": i + 1,
                    "predicted_ids": predicted_ids,
                    "matched_count": len(matched_ids),
                    "recall": recall,
                    "precision": precision,
                    "ndcg": ndcg,
                    "mrr": mrr,
                    "latency_ms": latency_ms
                })
            
            if len(all_results) < 2:
                print(f"⚠️  Troppo pochi run successo")
                return RankingMetrics(
                    prompt_id=prompt_id, query=query, predicted_count=0, expected_count=len(expected_ids),
                    matched_count=0, recall_at_k=0.0, precision_at_k=0.0, f1_at_k=0.0, ndcg_at_k=0.0,
                    mrr=0.0, matched_ids=[], missing_ids=expected_ids, extra_ids=[], position_deltas={},
                    success=False, error_msg="Insufficient runs", latency_ms=0.0
                ), None
            
            # Calcola consistency
            matched_counts = [m["matched_count"] for m in all_metrics]
            avg_matched = np.mean(matched_counts)
            std_matched = np.std(matched_counts)
            cv = std_matched / avg_matched if avg_matched > 0 else 0.0
            
            jaccard_scores = []
            for (ids1, _), (ids2, _) in combinations(all_results, 2):
                jaccard_scores.append(self.jaccard_similarity(set(ids1), set(ids2)))
            
            js_avg = np.mean(jaccard_scores) if jaccard_scores else 0.0
            js_min = np.min(jaccard_scores) if jaccard_scores else 0.0
            js_max = np.max(jaccard_scores) if jaccard_scores else 0.0
            
            id_positions = {}
            for predicted_ids, _ in all_results:
                for i, pid in enumerate(predicted_ids):
                    if pid not in id_positions:
                        id_positions[pid] = []
                    id_positions[pid].append(i + 1)
            
            position_variances = [np.var(positions) for positions in id_positions.values() if len(positions) >= 2]
            avg_pos_variance = np.mean(position_variances) if position_variances else 0.0
            
            avg_recall = np.mean([m["recall"] for m in all_metrics])
            avg_precision = np.mean([m["precision"] for m in all_metrics])
            avg_ndcg = np.mean([m["ndcg"] for m in all_metrics])
            avg_mrr = np.mean([m["mrr"] for m in all_metrics])
            
            print(f"\n📊 Count Metrics:")
            print(f"  Avg Matched: {avg_matched:.2f} ± {std_matched:.2f}")
            print(f"  CV: {cv:.3f}", end="")
            if cv < 0.1:
                print(" ✅ EXCELLENT")
            elif cv < 0.2:
                print(" ✓ GOOD")
            else:
                print(" ⚠️ MODERATE")
            
            print(f"\n🔗 Jaccard Similarity:")
            print(f"  Avg: {js_avg:.3f}")
            
            consistency = ConsistencyMetrics(
                prompt_id=prompt_id,
                num_runs=len(all_results),
                avg_matched_count=avg_matched,
                std_matched_count=std_matched,
                coefficient_variation=cv,
                jaccard_similarity_avg=js_avg,
                jaccard_similarity_min=js_min,
                jaccard_similarity_max=js_max,
                avg_position_variance=avg_pos_variance,
                avg_recall=avg_recall,
                avg_precision=avg_precision,
                avg_ndcg=avg_ndcg,
                avg_mrr=avg_mrr,
                runs_metrics=all_metrics
            )
            
            # Return metriche medie
            ranking_metrics = RankingMetrics(
                prompt_id=prompt_id,
                query=query,
                predicted_count=int(avg_matched),
                expected_count=len(expected_ids),
                matched_count=int(avg_matched),
                recall_at_k=avg_recall,
                precision_at_k=avg_precision,
                f1_at_k=0.0,
                ndcg_at_k=avg_ndcg,
                mrr=avg_mrr,
                matched_ids=all_metrics[0]["predicted_ids"],
                missing_ids=[],
                extra_ids=[],
                position_deltas={},
                success=True,
                error_msg=None,
                latency_ms=all_metrics[0]["latency_ms"]
            )
            
            return ranking_metrics, consistency


# ============================================================================
# ORCHESTRATORE TEST
# ============================================================================

class SyntheticEvaluationTest:
    """Orchestratore test completo."""
    
    def __init__(self, use_case: str, num_immobili: int, num_poi: int, num_runs: int, ablation_mode: bool = False, disabled_agents: Optional[Set[str]] = None):
        self.use_case = use_case
        self.num_immobili = num_immobili
        self.num_poi = num_poi
        self.num_runs = num_runs
        self.ablation_mode = ablation_mode
        self.disabled_agents = disabled_agents or set()
        self.synthetic_dir = Path("synthetic_data")
        self.synthetic_dir.mkdir(exist_ok=True)
        self.results_dir = Path("test_results")
        self.results_dir.mkdir(exist_ok=True)
        self.ablation_dir = Path("ablation_results")
        self.ablation_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def step1_generate_dataset(self) -> bool:
        """Step 1: Genera dataset sintetico."""
        print("\n" + "🎯 STEP 1: GENERAZIONE DATASET SINTETICO".center(80, "="))
        
        generator = SyntheticDataGenerator(
            num_immobili=self.num_immobili,
            num_poi_per_category=self.num_poi,
            use_case=self.use_case
        )
        
        self.dataset_file, self.poi_file, self.distances_file, self.df_immobili = generator.generate_all()
        
        print(f"✓ Dataset generato con {len(self.df_immobili)} immobili")
        return True
    
    def step2_create_ground_truth(self) -> bool:
        """Step 2: Crea ground truth automatico."""
        print("\n" + "🎯 STEP 2: CREAZIONE GROUND TRUTH".center(80, "="))
        
        ground_truth_path = self.synthetic_dir / f"ground_truth_{self.use_case}_{self.timestamp}.json"
        
        available_ids = self.df_immobili['id'].tolist()[:20]
        
        config = USE_CASE_CONFIGS[self.use_case]
        
        ground_truth = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "description": f"Ground truth auto-generato per test {self.use_case}",
                "dataset_version": self.dataset_file.stem,
                "k": 10,
                "author": "test_script",
                "test_mode": True
            },
            "use_cases": {
                self.use_case: {
                    "description": f"Test case per {self.use_case}",
                    "target_audience": "Test",
                    "prompts": [
                        {
                            "prompt_id": f"{self.use_case}_test_{j+1:03d}",
                            "query": query,
                            "context": "Test automatico",
                            "expected_top10": [
                                {
                                    "rank": i + 1,
                                    "id": available_ids[(j * 10 + i) % len(available_ids)] if available_ids else f"IMM{i+1:03d}",
                                    "score_expected": 95 - (i * 5),
                                    "pros": [
                                        "Posizione strategica per destinazione d'uso",
                                        "Buona accessibilità mezzi pubblici",
                                        "Vicinanza servizi essenziali"
                                    ] if i < 3 else ["Ubicazione discreta", "Superficie adeguata"],
                                    "cons": [
                                        "Necessità interventi di riqualificazione energetica",
                                        "Accessibilità da migliorare"
                                    ] if i > 5 else ["Costi ristrutturazione contenuti"] if i > 2 else [],
                                    "comment": f"Valutazione esperto MEF - edificio dismesso candidato per riqualificazione {self.use_case}"
                                }
                                for i in range(10)
                            ]
                        }
                        for j, query in enumerate(config["test_queries"])
                    ]
                }
            }
        }
        
        with open(ground_truth_path, 'w', encoding='utf-8') as f:
            json.dump(ground_truth, f, indent=2, ensure_ascii=False)
        
        self.ground_truth_path = ground_truth_path
        
        print(f"✓ Ground truth creato: {ground_truth_path}")
        print(f"  - {len(config['test_queries'])} query generate per {self.use_case}")
        return True
    
    def step3_evaluate_ranking(self) -> bool:
        """Step 3: Valuta ranking quality."""
        print("\n" + "🎯 STEP 3: VALUTAZIONE RANKING QUALITY".center(80, "="))
        
        # Set disabled agents in environment
        if self.disabled_agents:
            import os
            os.environ["DISABLED_AGENTS"] = ",".join(self.disabled_agents)
            print(f"⚠️  Agents disabilitati: {', '.join(self.disabled_agents)}")
        
        evaluator = RankingEvaluator(
            ground_truth_path=str(self.ground_truth_path),
            dataset_file=self.dataset_file,
            k=10,
            use_case=self.use_case
        )
        
        # Carica ground truth per sapere quanti prompt ci sono
        with open(self.ground_truth_path, 'r', encoding='utf-8') as f:
            ground_truth_data = json.load(f)
        
        prompts = ground_truth_data["use_cases"][self.use_case]["prompts"]
        num_prompts = len(prompts)
        
        print(f"\nValutazione {num_prompts} query per {self.use_case}...")
        
        all_ranking_metrics = []
        all_consistency_metrics = []
        results = {self.use_case: {}}
        
        for i, prompt_data in enumerate(prompts, 1):
            prompt_id = prompt_data["prompt_id"]
            print(f"\n  [{i}/{num_prompts}] {prompt_id}")
            print(f"  Query: {prompt_data['query'][:80]}...")
            
            ranking_metrics, consistency_metrics = evaluator.evaluate_with_consistency(
                use_case=self.use_case,
                prompt_id=prompt_id,
                num_runs=self.num_runs
            )
            
            all_ranking_metrics.append(ranking_metrics)
            all_consistency_metrics.append(consistency_metrics)
            
            results[self.use_case][prompt_id] = {
                "ranking": asdict(ranking_metrics),
                "consistency": asdict(consistency_metrics) if consistency_metrics else None
            }
            
            print(f"  Recall: {ranking_metrics.recall_at_k:.2%} | NDCG: {ranking_metrics.ndcg_at_k:.3f}")
        
        # Cleanup environment
        if self.disabled_agents:
            import os
            if "DISABLED_AGENTS" in os.environ:
                del os.environ["DISABLED_AGENTS"]
        
        # Salva metriche aggregate
        self.all_ranking_metrics = all_ranking_metrics
        self.all_consistency_metrics = all_consistency_metrics
        
        if self.ablation_mode:
            config_name = "baseline" if not self.disabled_agents else f"without_{'_'.join(sorted(self.disabled_agents))}"
            result_file = self.ablation_dir / f"ablation_{config_name}_{self.timestamp}.json"
        else:
            result_file = self.results_dir / f"test_result_{self.timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.result_file = result_file
        
        print(f"✓ Valutazione completata su {num_prompts} query")
        print(f"📝 Log dettagliati degli agenti (input/output) salvati in: {evaluator.agent_logs_dir}")
        return True
    
    def step4_analyze_results(self) -> bool:
        """Step 4: Analizza risultati."""
        print("\n" + "🎯 STEP 4: ANALISI RISULTATI".center(80, "="))
        
        print("\n" + "="*80)
        print("RISULTATI FINALI - MEDIE SU TUTTE LE QUERY")
        print("="*80)
        
        # Calcola medie
        avg_recall = np.mean([m.recall_at_k for m in self.all_ranking_metrics])
        avg_precision = np.mean([m.precision_at_k for m in self.all_ranking_metrics])
        avg_f1 = np.mean([m.f1_at_k for m in self.all_ranking_metrics])
        avg_ndcg = np.mean([m.ndcg_at_k for m in self.all_ranking_metrics])
        avg_mrr = np.mean([m.mrr for m in self.all_ranking_metrics])
        avg_latency = np.mean([m.latency_ms for m in self.all_ranking_metrics])
        
        print(f"\n📊 Ranking Metrics (media su {len(self.all_ranking_metrics)} query):")
        print(f"    Recall@10:    {avg_recall:.2%}")
        print(f"    Precision@10: {avg_precision:.2%}")
        print(f"    F1@10:        {avg_f1:.2%}")
        print(f"    NDCG@10:      {avg_ndcg:.3f}")
        print(f"    MRR:          {avg_mrr:.3f}")
        print(f"    Latency:      {avg_latency:.0f}ms")
        
        # Metriche consistency medie
        consistency_with_data = [c for c in self.all_consistency_metrics if c is not None]
        if consistency_with_data:
            avg_cv = np.mean([c.coefficient_variation for c in consistency_with_data])
            avg_jaccard = np.mean([c.jaccard_similarity_avg for c in consistency_with_data])
            avg_pos_var = np.mean([c.avg_position_variance for c in consistency_with_data])
            
            print(f"\n    🔬 Consistency (media {self.num_runs} runs per query):")
            print(f"      CV:           {avg_cv:.3f}", end="")
            if avg_cv < 0.1:
                print(" ✅ EXCELLENT")
            elif avg_cv < 0.2:
                print(" ✓ GOOD")
            else:
                print(" ⚠️ MODERATE")
            
            print(f"      Jaccard Avg:  {avg_jaccard:.3f}", end="")
            if avg_jaccard > 0.8:
                print(" ✅ STRONG")
            elif avg_jaccard > 0.6:
                print(" ✓ GOOD")
            else:
                print(" ⚠️ WEAK")
            
            print(f"      Pos Variance: {avg_pos_var:.2f}")
        else:
            avg_cv = 0.0
            avg_jaccard = 0.0
            avg_pos_var = 0.0
        
        # Salva medie aggregate per uso in run_all_use_cases
        self.ranking_metrics = RankingMetrics(
            prompt_id="aggregate",
            query="aggregate",
            predicted_count=0,
            expected_count=0,
            matched_count=0,
            recall_at_k=avg_recall,
            precision_at_k=avg_precision,
            f1_at_k=avg_f1,
            ndcg_at_k=avg_ndcg,
            mrr=avg_mrr,
            matched_ids=[],
            missing_ids=[],
            extra_ids=[],
            position_deltas={},
            success=True,
            error_msg=None,
            latency_ms=avg_latency
        )
        
        if consistency_with_data:
            self.consistency_metrics = ConsistencyMetrics(
                prompt_id="aggregate",
                num_runs=self.num_runs,
                avg_matched_count=0,
                std_matched_count=0,
                coefficient_variation=avg_cv,
                jaccard_similarity_avg=avg_jaccard,
                jaccard_similarity_min=0,
                jaccard_similarity_max=0,
                avg_position_variance=avg_pos_var,
                avg_recall=avg_recall,
                avg_precision=avg_precision,
                avg_ndcg=avg_ndcg,
                avg_mrr=avg_mrr,
                runs_metrics=[]
            )
        else:
            self.consistency_metrics = None
        
        print(f"\n✓ Risultati salvati: {self.result_file}")
        
        return True
    
    def run_full_test(self) -> bool:
        """Esegue test completo."""
        print("\n" + "🚀 SYNTHETIC EVALUATION - TEST COMPLETO".center(80, "="))
        print(f"Use Case: {self.use_case}")
        print(f"Immobili: {self.num_immobili}")
        print(f"POI per categoria: {self.num_poi}")
        print(f"Consistency Runs: {self.num_runs}")
        if self.ablation_mode:
            print(f"Ablation Mode: {'Baseline' if not self.disabled_agents else f'Disabled: {self.disabled_agents}'}")
        print(f"Timestamp: {self.timestamp}")
        
        steps = [
            ("Generazione Dataset", self.step1_generate_dataset),
            ("Creazione Ground Truth", self.step2_create_ground_truth),
            ("Valutazione Ranking", self.step3_evaluate_ranking),
            ("Analisi Risultati", self.step4_analyze_results)
        ]
        
        for i, (name, step_func) in enumerate(steps, 1):
            print(f"\n\n{'#'*80}")
            print(f"# STEP {i}/{len(steps)}: {name}")
            print(f"{'#'*80}")
            
            success = step_func()
            
            if not success:
                print(f"\n❌ Test fallito allo step {i}: {name}")
                return False
        
        print("\n\n" + "="*80)
        print("✅ TEST COMPLETO COMPLETATO CON SUCCESSO!")
        print("="*80)
        if self.ablation_mode:
            print(f"\n📁 Risultati salvati in: {self.ablation_dir}")
        else:
            print(f"\n📁 Risultati salvati in: {self.results_dir}")
        print(f"📊 File risultato: {self.result_file.name}")
        print(f"📝 Log agenti: agent_logs/ (file JSONL e JSON per ogni run)")
        
        return True
    
    def run_full_ablation(self) -> bool:
        """Esegue ablation study completo testando ogni agent."""
        print("\n" + "🔬 ABLATION STUDY - TEST TUTTI GLI AGENT".center(80, "="))
        print(f"Testing {len(AVAILABLE_AGENTS)} agents")
        print(f"Use Case: {self.use_case}")
        print(f"Runs per config: {self.num_runs}")
        print("="*80)
        
        all_results = {}
        
        # 1. Baseline (tutti agent attivi)
        print("\n\n" + "="*80)
        print("BASELINE - Tutti gli agent attivi")
        print("="*80)
        
        baseline_tester = SyntheticEvaluationTest(
            use_case=self.use_case,
            num_immobili=self.num_immobili,
            num_poi=self.num_poi,
            num_runs=self.num_runs,
            ablation_mode=True,
            disabled_agents=set()
        )
        
        if not baseline_tester.run_full_test():
            print("❌ Baseline test fallito")
            return False
        
        all_results["baseline"] = {
            "disabled_agents": [],
            "ranking_metrics": asdict(baseline_tester.ranking_metrics),
            "consistency_metrics": asdict(baseline_tester.consistency_metrics) if baseline_tester.consistency_metrics else None
        }
        
        # 2. Test ogni agent singolarmente
        for agent in AVAILABLE_AGENTS:
            print("\n\n" + "="*80)
            print(f"TEST WITHOUT: {agent}")
            print("="*80)
            
            agent_tester = SyntheticEvaluationTest(
                use_case=self.use_case,
                num_immobili=self.num_immobili,
                num_poi=self.num_poi,
                num_runs=self.num_runs,
                ablation_mode=True,
                disabled_agents={agent}
            )
            
            # Riusa stesso dataset e ground truth del baseline
            agent_tester.dataset_file = baseline_tester.dataset_file
            agent_tester.ground_truth_path = baseline_tester.ground_truth_path
            agent_tester.df_immobili = baseline_tester.df_immobili
            
            # Salta step 1 e 2, vai diretto a valutazione
            success = agent_tester.step3_evaluate_ranking() and agent_tester.step4_analyze_results()
            
            if success:
                all_results[f"without_{agent}"] = {
                    "disabled_agents": [agent],
                    "ranking_metrics": asdict(agent_tester.ranking_metrics),
                    "consistency_metrics": asdict(agent_tester.consistency_metrics) if agent_tester.consistency_metrics else None
                }
            else:
                print(f"⚠️  Test fallito per {agent}")
        
        # 3. Genera report comparativo
        self._generate_ablation_report(all_results)
        
        return True
    
    def _generate_ablation_report(self, all_results: Dict):
        """Genera report comparativo ablation study."""
        print("\n\n" + "="*80)
        print("📊 ABLATION STUDY - REPORT COMPARATIVO")
        print("="*80)
        
        baseline = all_results.get("baseline")
        if not baseline:
            print("❌ Baseline non trovato")
            return
        
        baseline_recall = baseline["ranking_metrics"]["recall_at_k"]
        baseline_ndcg = baseline["ranking_metrics"]["ndcg_at_k"]
        baseline_latency = baseline["ranking_metrics"]["latency_ms"]
        
        print(f"\n🎯 Baseline Performance:")
        print(f"   Recall@10: {baseline_recall:.2%}")
        print(f"   NDCG@10:   {baseline_ndcg:.3f}")
        print(f"   Latency:   {baseline_latency:.0f}ms")
        
        if baseline.get("consistency_metrics"):
            baseline_cv = baseline["consistency_metrics"]["coefficient_variation"]
            baseline_jaccard = baseline["consistency_metrics"]["jaccard_similarity_avg"]
            print(f"   CV:        {baseline_cv:.3f}")
            print(f"   Jaccard:   {baseline_jaccard:.3f}")
        
        print(f"\n🔍 Agent Impact Analysis:\n")
        
        impact_data = []
        
        for agent in AVAILABLE_AGENTS:
            config_key = f"without_{agent}"
            
            if config_key not in all_results:
                continue
            
            config = all_results[config_key]
            metrics = config["ranking_metrics"]
            
            recall = metrics["recall_at_k"]
            ndcg = metrics["ndcg_at_k"]
            latency = metrics["latency_ms"]
            
            recall_delta = recall - baseline_recall
            ndcg_delta = ndcg - baseline_ndcg
            latency_delta = latency - baseline_latency
            
            # Determina criticità
            if abs(recall_delta) > 0.3 or abs(ndcg_delta) > 0.3:
                criticality = "🔴 CRITICAL"
            elif abs(recall_delta) > 0.15 or abs(ndcg_delta) > 0.15:
                criticality = "🟡 IMPORTANT"
            else:
                criticality = "🟢 OPTIONAL"
            
            impact_data.append({
                "agent": agent,
                "criticality": criticality,
                "recall": recall,
                "recall_delta": recall_delta,
                "ndcg": ndcg,
                "ndcg_delta": ndcg_delta,
                "latency": latency,
                "latency_delta": latency_delta
            })
            
            print(f"{criticality} {agent}")
            print(f"   Recall: {recall:.2%} ({recall_delta:+.2%})")
            print(f"   NDCG:   {ndcg:.3f} ({ndcg_delta:+.3f})")
            print(f"   Latency: {latency:.0f}ms ({latency_delta:+.0f}ms)")
            print()
        
        # Ordina per impatto
        impact_data.sort(key=lambda x: abs(x["recall_delta"]) + abs(x["ndcg_delta"]), reverse=True)
        
        print(f"\n📈 Agent Ranking by Impact:\n")
        for i, data in enumerate(impact_data, 1):
            print(f"{i}. {data['agent']}: Recall {data['recall_delta']:+.2%}, NDCG {data['ndcg_delta']:+.3f}")
        
        # Salva report
        report_file = self.ablation_dir / f"ablation_report_{self.timestamp}.json"
        report_data = {
            "timestamp": self.timestamp,
            "use_case": self.use_case,
            "baseline": baseline,
            "configurations": all_results,
            "impact_analysis": impact_data
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Report salvato: {report_file}")


def run_all_use_cases(num_immobili: int, num_poi: int, num_runs: int) -> bool:
    """Esegue test su tutti gli use case e genera report aggregato."""
    
    print("\n" + "="*80)
    print("TEST MULTI-USE-CASE - TUTTI GLI USE CASE".center(80))
    print("="*80)
    print(f"\nConfigurazione:")
    print(f"  - Use Cases: {len(USE_CASE_CONFIGS)}")
    print(f"  - Immobili per use case: {num_immobili}")
    print(f"  - POI per categoria: {num_poi}")
    print(f"  - Consistency runs: {num_runs}")
    print(f"\n" + "="*80)
    
    all_use_case_results = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for i, use_case in enumerate(USE_CASE_CONFIGS.keys(), 1):
        print(f"\n\n" + "#"*80)
        print(f"# USE CASE {i}/{len(USE_CASE_CONFIGS)}: {use_case.upper()}")
        print("#"*80)
        
        tester = SyntheticEvaluationTest(
            use_case=use_case,
            num_immobili=num_immobili,
            num_poi=num_poi,
            num_runs=num_runs
        )
        
        success = tester.run_full_test()
        
        if success:
            all_use_case_results[use_case] = {
                "ranking_metrics": asdict(tester.ranking_metrics),
                "consistency_metrics": asdict(tester.consistency_metrics) if tester.consistency_metrics else None,
                "result_file": str(tester.result_file),
                "query": USE_CASE_CONFIGS[use_case]["test_query"]
            }
        else:
            print(f"\n⚠️ Test fallito per {use_case}")
            all_use_case_results[use_case] = {"error": "Test failed"}
    
    # Genera report aggregato
    print("\n\n" + "="*80)
    print("📊 REPORT AGGREGATO - CONFRONTO TRA USE CASE")
    print("="*80)
    
    print(f"\n{'Use Case':<20} {'Recall@10':<12} {'NDCG@10':<12} {'MRR':<12} {'Latency':<12} {'CV':<10}")
    print("-" * 88)
    
    for use_case, results in all_use_case_results.items():
        if "error" in results:
            print(f"{use_case:<20} {'FAILED':<12}")
            continue
        
        r = results["ranking_metrics"]
        c = results.get("consistency_metrics")
        
        recall = r["recall_at_k"]
        ndcg = r["ndcg_at_k"]
        mrr = r["mrr"]
        latency = r["latency_ms"]
        cv = c["coefficient_variation"] if c else 0.0
        
        print(f"{use_case:<20} {recall:<12.2%} {ndcg:<12.3f} {mrr:<12.3f} {latency:<12.0f} {cv:<10.3f}")
    
    # Analisi best/worst performers
    print(f"\n\n📈 ANALISI PERFORMANCE:\n")
    
    valid_results = {k: v for k, v in all_use_case_results.items() if "error" not in v}
    
    if valid_results:
        # Best Recall
        best_recall = max(valid_results.items(), key=lambda x: x[1]["ranking_metrics"]["recall_at_k"])
        print(f"✅ Miglior Recall: {best_recall[0]} ({best_recall[1]['ranking_metrics']['recall_at_k']:.2%})")
        
        # Best NDCG
        best_ndcg = max(valid_results.items(), key=lambda x: x[1]["ranking_metrics"]["ndcg_at_k"])
        print(f"✅ Miglior NDCG: {best_ndcg[0]} ({best_ndcg[1]['ranking_metrics']['ndcg_at_k']:.3f})")
        
        # Best Consistency
        with_consistency = {k: v for k, v in valid_results.items() if v.get("consistency_metrics")}
        if with_consistency:
            best_consistency = min(with_consistency.items(), key=lambda x: x[1]["consistency_metrics"]["coefficient_variation"])
            print(f"✅ Miglior Consistency: {best_consistency[0]} (CV={best_consistency[1]['consistency_metrics']['coefficient_variation']:.3f})")
        
        # Fastest
        fastest = min(valid_results.items(), key=lambda x: x[1]["ranking_metrics"]["latency_ms"])
        print(f"⚡ Più Veloce: {fastest[0]} ({fastest[1]['ranking_metrics']['latency_ms']:.0f}ms)")
        
        # Medie aggregate
        avg_recall = np.mean([v["ranking_metrics"]["recall_at_k"] for v in valid_results.values()])
        avg_ndcg = np.mean([v["ranking_metrics"]["ndcg_at_k"] for v in valid_results.values()])
        avg_latency = np.mean([v["ranking_metrics"]["latency_ms"] for v in valid_results.values()])
        
        print(f"\n📊 Medie Aggregate:")
        print(f"   Recall@10: {avg_recall:.2%}")
        print(f"   NDCG@10:   {avg_ndcg:.3f}")
        print(f"   Latency:   {avg_latency:.0f}ms")
    
    # Salva report aggregato
    results_dir = Path("test_results")
    aggregate_report_file = results_dir / f"aggregate_report_{timestamp}.json"
    
    aggregate_data = {
        "timestamp": timestamp,
        "test_type": "multi_use_case",
        "configuration": {
            "num_immobili": num_immobili,
            "num_poi": num_poi,
            "num_runs": num_runs
        },
        "use_cases": all_use_case_results,
        "summary": {
            "total_use_cases": len(USE_CASE_CONFIGS),
            "successful": len(valid_results),
            "failed": len(all_use_case_results) - len(valid_results)
        } if valid_results else {}
    }
    
    with open(aggregate_report_file, 'w', encoding='utf-8') as f:
        json.dump(aggregate_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Report aggregato salvato: {aggregate_report_file}")
    
    print("\n" + "="*80)
    print("✅ TEST MULTI-USE-CASE COMPLETATO!")
    print("="*80)
    
    return len(valid_results) == len(USE_CASE_CONFIGS)


# ============================================================================
# MAIN
# ============================================================================

def main():
    
    print("\n" + "="*80)
    print("SYNTHETIC EVALUATION - TEST SISTEMA COMPLETO".center(80))
    print("="*80)
    print("\nConfigurazione fissa:")
    print("  - Test multi-use-case su tutti e 5 gli use case")
    print("  - 50 immobili per use case")
    print("  - 5 POI per categoria")
    print("  - 3 run per consistency test")
    print("="*80)
    
    # Inizializza client Langfuse per tracciamento
    langfuse_client = get_langfuse_client()
    if langfuse_client:
        print("\n✓ Langfuse tracing attivo - i dati saranno visibili su cloud.langfuse.com")
    else:
        print("\n⚠ Langfuse tracing non attivo - verifica le credenziali nel file .env")
    
    # Configurazione fissa
    success = run_all_use_cases(
        num_immobili=50,
        num_poi=5,
        num_runs=3
    )
    
    # Flush finale dei dati Langfuse prima di terminare
    if langfuse_client:
        print("\nAttendo completamento invio dati asincroni...")
        time.sleep(2)  # Attendi che le richieste asincrone completino
        flush_langfuse()
    
    print("\n" + "="*80)
    print("📝 DOVE TROVARE I LOG DEGLI AGENTI:")
    print("="*80)
    print("I log dettagliati di input/output per ogni agente sono salvati in:")
    print("  - agent_logs/")
    print("\nFormati disponibili:")
    print("  - .jsonl - Log in formato streaming (una riga per evento)")
    print("  - .json  - Log strutturato completo per ogni run")
    print("\nNome file: agent_traces_{use_case}_{prompt_id}_run{N}_{timestamp}.{jsonl|json}")
    print("="*80)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

