import json
import re
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:
    ChatPromptTemplate = None

_active_evaluation_logger: Optional['AgentLogger'] = None

def set_active_evaluation_logger(logger: 'AgentLogger'):
    global _active_evaluation_logger
    _active_evaluation_logger = logger

def get_active_evaluation_logger() -> Optional['AgentLogger']:
    return _active_evaluation_logger

class AgentLogger:
    """Logger per tracciare input/output di ogni agente."""
    
    def __init__(self, log_dir: Optional[Path] = None):
        if log_dir:
            self.log_dir = log_dir
            self.log_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.log_dir = None
            
        self.current_log_file = None
        self.log_data = []
    
    def start_evaluation(self, use_case: str, prompt_id: str, run_number: int, timestamp: str):
        """Inizializza un nuovo file di log per una specifica valutazione."""
        self.log_data = []
        
        # Scrivi header
        header = {
            "use_case": use_case,
            "prompt_id": prompt_id,
            "user_query": getattr(self, 'last_query', None), # Fallback if we have it
            "run_number": run_number,
            "timestamp": datetime.now().isoformat()
        }
        self.log_data.append(header)
        
        if self.log_dir:
            log_filename = f"agent_traces_{use_case}_{prompt_id}_run{run_number}_{timestamp}.jsonl"
            self.current_log_file = self.log_dir / log_filename
            self._write_log_entry(header)
    
    def log_agent_execution(self, agent_name: str, input_data: Any, output_data: Any, 
                           execution_time_ms: float, agent_mode: str = "filtering", metadata: Optional[Dict] = None):
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
        elif isinstance(input_data, list):
            input_extracted = input_data
        else:
            input_extracted = input_data
        
        # Estrai output dall'output (se presente)
        output_extracted = None

        # Case 1: result is a DataFrame (Ranking or Mapping mode)
        if isinstance(output_data, pd.DataFrame):
            agent_type = agent_name.replace("-agent", "").replace("-extractor", "").replace("-extraction", "").replace("_", "-")
            
            # Mappa prefissi colonne per ogni agente
            prefix_map = {
                "typology": "typology_",
                "location": "location_",
                "ape": "ape_",
                "normative": "normative_",
                "poi": "poi_"
            }
            prefix = None
            for k, v in prefix_map.items():
                if k in agent_type:
                    prefix = v
                    break
            
            if agent_mode == "ranking" and prefix:
                # REPLICATE FORMULA LOGIC FROM GRAPH_AGENT
                involved_cols = ["id"]
                score_col = f"{prefix}score"
                transparency_cols = [c for c in output_data.columns if c.startswith(prefix) or c.startswith(f"{prefix}rank_") or c.startswith(f"{prefix}weight_")]
                involved_cols.extend([c for c in transparency_cols if c not in involved_cols])
                
                # Aggiungiamo colonne di input rilevanti definite nelle costanti (lazy import inside method if needed)
                try:
                    from app.core.constants import APE_AGENT_COLUMNS, TYPOLOGY_AGENT_COLUMNS, NORMATIVE_AGENT_COLUMNS, POI_AGENT_COLUMNS
                    source_cols_map = {
                        "typology": TYPOLOGY_AGENT_COLUMNS,
                        "location": ["distanza_km", "poi_riferimento"],
                        "ape": APE_AGENT_COLUMNS,
                        "normative": NORMATIVE_AGENT_COLUMNS,
                        "poi": POI_AGENT_COLUMNS
                    }
                    agent_key = next((k for k in source_cols_map if k in agent_type), None)
                    source_cols = []
                    if agent_key:
                        source_cols = [c for c in source_cols_map[agent_key] if c in output_data.columns]
                        involved_cols.extend([c for c in source_cols if c not in involved_cols])
                except:
                    source_cols = []

                # INPUT: Nomi delle colonne coinvolte (solo sorgenti)
                input_extracted = ", ".join(source_cols) if source_cols else ", ".join([c for c in involved_cols if c != "id"])
                
                # OUTPUT: Formula per immobile (Full)
                ranking_entries = []
                for _, row in output_data.iterrows():
                    if agent_name == "ranking-agent":
                        # Final global ranking score
                        scores = []
                        for agent in ["location", "normative", "ape", "typology", "poi"]:
                            sc = row.get(f"{agent}_score", 0.0)
                            w = row.get(f"ranking_weight_{agent}", 0.0)
                            scores.append(f"{agent}_score({sc}) * Weight({w})")
                        
                        formula_list = ["RankingSum("] + [f"  {s}," for s in scores[:-1]] + [f"  {scores[-1]}", ")"]
                    elif "typology" in agent_type:
                        rank_pos = row.get(f"{prefix}rank_position", "N/A")
                        formula_list = [f"100 / Position({rank_pos})" if rank_pos != "N/A" else "0 (Non corrispondente)"]
                    elif "location" in agent_type:
                        dist = row.get("distanza_km", 0)
                        # Formula: 100 * exp(-(dist/2.5)^3)
                        formula_list = [f"100 * exp(-({dist:.2f}/2.5)^3)"]
                    elif any(x in agent_type for x in ["poi", "ape", "normative"]):
                        # Queste logiche usano mediamente dei partial scores (0-100)
                        partial_cols = [c for c in output_data.columns if f"{prefix}partial_score_" in c]
                        
                        if partial_cols:
                            weighted_parts = []
                            for pc in partial_cols:
                                col_name = pc.replace(f"{prefix}partial_score_", "")
                                if col_name not in output_data.columns:
                                    continue
                                
                                val_raw = row.get(col_name)
                                score_pt = row.get(pc)
                                weight = row.get(f"{prefix}weight_{col_name}", 1.0 / len(partial_cols))
                                
                                # Caso Speciale: Classe Energetica (Categorico)
                                if col_name == "classe_energetica_ape":
                                    rank_pos = row.get(f"ape_rank_position_{col_name}", "N/A")
                                    if rank_pos != "N/A":
                                        desc = f"{col_name}({val_raw})[Rank {rank_pos}/10]: 100*(1-{int(rank_pos)-1}/9)={score_pt}"
                                    else:
                                        desc = f"{col_name}({val_raw}): {score_pt}"
                                
                                # Caso Speciale: Normative Typology Rank
                                elif col_name == "tipologia_bene_immobile" and "normative" in agent_type:
                                    rank_pos = row.get(f"normative_rank_position_{col_name}", "N/A")
                                    if rank_pos != "N/A":
                                        desc = f"{col_name}({val_raw})[Rank {rank_pos}]: {score_pt}"
                                    else:
                                        desc = f"{col_name}({val_raw}): {score_pt}"

                                # Caso Numerico (Min-Max Scaling relativo al dataset attuale)
                                else:
                                    try:
                                        if pd.api.types.is_numeric_dtype(output_data[col_name]):
                                            c_vals = pd.to_numeric(output_data[col_name], errors='coerce').dropna()
                                            c_min = c_vals.min()
                                            c_max = c_vals.max()
                                            val_num = float(val_raw) if val_raw not in [None, "N/D", "N/A"] else 0
                                            
                                            if c_max == c_min:
                                                desc = f"{col_name}({val_raw}): 100"
                                            else:
                                                f_up = round(100 * (val_num - c_min) / (c_max - c_min), 1)
                                                f_down = round(100 * (c_max - val_num) / (c_max - c_min), 1)
                                                
                                                if abs(f_up - score_pt) < 1.0:
                                                    desc = f"{col_name}: 100*({val_num}-{c_min})/({c_max}-{c_min})={score_pt}"
                                                elif abs(f_down - score_pt) < 1.0:
                                                    desc = f"{col_name}: 100*({c_max}-{val_num})/({c_max}-{c_min})={score_pt}"
                                                else:
                                                    desc = f"{col_name}({val_num}) [Min {c_min}, Max {c_max}]: {score_pt}"
                                        else:
                                            desc = f"{col_name}({val_raw}): {score_pt} (Match)"
                                    except:
                                        desc = f"{col_name}({val_raw}): {score_pt}"
                                
                                weighted_parts.append(f"{desc} * Weight({weight:.3f})")

                            if len(weighted_parts) > 1:
                                formula_list = ["Sum("] + [f"  {p}," for p in weighted_parts[:-1]] + [f"  {weighted_parts[-1]}", ")"]
                            else:
                                formula_list = [f"{weighted_parts[0]}"]
                        else:
                            # Fallback generico
                            val_main = row.get(source_cols[0], "N/D") if source_cols else "N/D"
                            formula_list = [f"Score({val_main})"]
                    else:
                        formula_list = ["Logic Default"]

                    ranking_entries.append({
                        "id": row["id"],
                        "score": row.get(score_col, 0),
                        "formula": formula_list
                    })
                
                output_extracted = ranking_entries
            else:
                # Comportamento standard per DataFrame (es. filtraggio)
                if not output_data.columns.is_unique:
                    output_data = output_data.loc[:, ~output_data.columns.duplicated()]
                output_extracted = json.loads(output_data.to_json(orient="records"))
                input_extracted = f"{agent_mode.capitalize()} mode: {len(output_data)} records"
        
        elif agent_name == "relaxation-agent":
            # Per l'agente di rilassamento, mostriamo i tentativi effettuati come input
            # e la query finale scelta come output
            if hasattr(output_data, 'attempts') and output_data.attempts:
                input_extracted = output_data.attempts
                output_extracted = getattr(output_data, 'final_sql', None) or getattr(output_data, 'raw_text', "N/A")
            else:
                input_extracted = getattr(output_data, 'raw_text', "N/A")
                output_extracted = "Nessuna proposta applicata"

        elif agent_name == "ranking-agent":
            if hasattr(output_data, 'ranking') and output_data.ranking:
                output_extracted = {"ranking": output_data.ranking.ranking}
            elif hasattr(output_data, 'weights'):
                output_extracted = output_data.weights.model_dump()
        
        elif agent_name == "poi-agent":
            if hasattr(output_data, 'requisiti'):
                output_extracted = {"requisiti": output_data.requisiti}
            elif hasattr(output_data, 'raw_text'):
                output_extracted = output_data.raw_text
        
        elif hasattr(output_data, 'raw_text'):
            output_extracted = output_data.raw_text
        elif isinstance(output_data, dict) and 'raw_text' in output_data:
            output_extracted = output_data['raw_text']
        elif hasattr(output_data, 'model_dump'):
            output_extracted = output_data.model_dump()
        else:
            output_extracted = str(output_data)
        
        log_entry = {
            "agent_name": agent_name,
            "agent_mode": agent_mode,
            "timestamp": datetime.now().isoformat(),
            "execution_time_ms": execution_time_ms,
            "input": self._serialize_data(input_extracted) if input_extracted is not None else None,
            "output": self._serialize_data(output_extracted) if output_extracted is not None else None
        }
        self.log_data.append(log_entry)
        
        if self.current_log_file:
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
        
        # In memory log data implies we are done with collection.
        # If logging to file, process JSON creation and HTML generation.
        if self.current_log_file:
            self._finalize_file_log(footer)

    def _finalize_file_log(self, footer):
        # ... logic to convert to JSON and HTML ...
        json_file = self.current_log_file.with_suffix(".json")
        try:
            # Prendi l'evaluation_start come base
            eval_start = self.log_data[0] if self.log_data and "use_case" in self.log_data[0] else {}
            
            # Estrai le proprietà della run
            run_props = {
                "use_case": eval_start.get("use_case"),
                "prompt_id": eval_start.get("prompt_id"),
                "user_query": eval_start.get("user_query"),
                "run_number": eval_start.get("run_number"),
                "run_timestamp": eval_start.get("timestamp")
            }
            
            agent_executions = self._process_log_data_for_export(self.log_data, run_props)
            
            # Crea oggetto finale solo con agent_executions
            log_data_final = {"agent_executions": agent_executions}
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(log_data_final, f, indent=2, ensure_ascii=False)
        
            # Elimina il file JSONL dopo aver creato il JSON aggregato
            if self.current_log_file.exists():
                try:
                    self.current_log_file.unlink()
                except Exception as e:
                    print(f"⚠️ Errore nell'eliminare JSONL {self.current_log_file.name}: {e}")
            
            print(f"💾 JSON trace salvato: {json_file.name}")
            
        except Exception as e:
            print(f"⚠️ Errore nel finalizzare log: {e}")
            import traceback
            traceback.print_exc()

    def _process_log_data_for_export(self, raw_log_data, run_props):
        """Processa i dati raw in una struttura pulita per export."""
        agent_executions = []
        batch_counter = 1
        
        try:
            for e in raw_log_data:
                if not isinstance(e, dict) or "agent_name" not in e:
                    continue
                    
                # Copia entry
                entry = e.copy()
                
                # Retrieve already serialized input/output
                # In log_agent_execution, we already apply _serialize_data. 
                # However, for the context of JSON export, we want to ensure they are 
                # fully recursive-friendly for json.dump.
                # If they are already dicts/lists, _serialize_data handles them fine (recursive).
                # If they are strings that look like JSON, _serialize_data will parse them.
                
                input_val = entry.get("input")
                output_val = entry.get("output")
                
                # Re-run serialize to catch any nested JSON strings or non-serializable objects
                # that might have been passed directly. 
                # NOTE: careful about double serialization if they are already strings.
                
                try:
                    serialized_input = self._serialize_data(input_val)
                    serialized_output = self._serialize_data(output_val)
                except Exception as ex:
                    print(f"⚠️ Errore durante la serializzazione dell'entry {entry.get('agent_name')}: {ex}")
                    serialized_input = str(input_val)
                    serialized_output = str(output_val)
                
                if entry["agent_name"] == "evaluation-agent":
                    # Estrai la lista di valutazioni se presente in un dizionario
                    items_to_log = []
                    
                    # Logica per gestire batch di valutazioni
                    val_data = serialized_output
                    if isinstance(val_data, list):
                        items_to_log = val_data
                    elif isinstance(val_data, dict):
                        # Cerca chiavi comuni che contengono liste di risultati
                        for k in ["evaluations", "results", "valutazioni"]:
                            if k in val_data and isinstance(val_data[k], list):
                                items_to_log = val_data[k]
                                break
                        if not items_to_log:
                            items_to_log = [val_data]
                    else:
                        items_to_log = [val_data]

                    # Crea esecuzioni separate per ogni item nel batch
                    for item in items_to_log:
                        agent_entry = {
                            **run_props,
                            "agent_name": "evaluation-agent",
                            "agent_mode": entry.get("agent_mode", "evaluation"),
                            "batch_id": batch_counter,
                            "timestamp": entry.get("timestamp"),
                            "execution_time_ms": entry.get("execution_time_ms"),
                            "input": serialized_input,
                            "output": item
                        }
                        agent_executions.append(agent_entry)
                        batch_counter += 1
                else:
                    agent_entry = {
                        **run_props, 
                        **entry, 
                        "input": serialized_input,
                        "output": serialized_output,
                        "batch_id": None
                    }
                    agent_executions.append(agent_entry)
        except Exception as global_ex:
            print(f"❌ Errore critico in _process_log_data_for_export: {global_ex}")
            import traceback
            traceback.print_exc()
        
        return agent_executions

    def generate_html_view(self, agent_executions: List[Dict], title: str, json_filename: Optional[str] = None, view_mode: str = "table") -> str:
        """Genera la stringa HTML completa per la visualizzazione tabellare o a tab."""
        
        # DataFrame per TUTTE le agent executions
        agent_rows = []
        for execution in agent_executions:
            # Funzione helper per convertire input/output in stringa o tabella HTML
            def to_display_value(value, field_name=None):
                if value is None:
                    return None
                elif isinstance(value, dict):
                    return self._dict_to_html_table(value)
                elif isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        return self._list_of_dicts_to_html_table(value)
                    else:
                        return "<br>".join(str(item) for item in value)
                else:
                    text = str(value)
                    # Convert literal \n to actual line breaks
                    text = text.replace('\\n', '<br>')
                    # Convert actual newlines to HTML breaks
                    text = text.replace('\n', '<br>')
                    if field_name == "output":
                        return self._parse_markdown_simple(text)
                    else:
                        return text
            
            agent_rows.append({
                "use_case": execution.get("use_case"),
                "prompt_id": execution.get("prompt_id"),
                "user_query": execution.get("user_query"),
                "run_number": execution.get("run_number"),
                "run_timestamp": execution.get("run_timestamp"),
                "batch_id": execution.get("batch_id"),
                "agent_name": execution.get("agent_name"),
                "agent_mode": execution.get("agent_mode"),
                "timestamp": execution.get("timestamp"),
                "execution_time_ms": execution.get("execution_time_ms"),
                "input": to_display_value(execution.get("input"), "input"),
                "output": to_display_value(execution.get("output"), "output")
            })
        
        df = pd.DataFrame(agent_rows)
        
        if df.empty:
             return "<html><body><h1>Nessun dato registrato</h1></body></html>"

        # Raggruppa per retry
        df['retry_id'] = df.groupby(['agent_name', 'run_number', 'batch_id', 'agent_mode'], dropna=False).cumcount() + 1
        
        desired_order = [
            'agent_name', 'agent_mode', 'output', 'input', 
            'use_case', 'prompt_id', 'user_query', 'run_number', 'run_timestamp', 
            'batch_id', 'retry_id', 'timestamp', 'execution_time_ms'
        ]
        existing_columns = [col for col in desired_order if col in df.columns]
        # Add any other columns at the end
        other_cols = [col for col in df.columns if col not in desired_order]
        df = df[existing_columns + other_cols]
        
        # Format timestamps
        if "run_timestamp" in df.columns:
            df["run_timestamp"] = pd.to_datetime(df["run_timestamp"], errors='coerce')
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')

        return self._render_html_template(df, title, json_filename, view_mode=view_mode)

    def _render_html_template(self, df: pd.DataFrame, title: str, json_filename: Optional[str] = None, view_mode: str = "table") -> str:
        """Renderizza il template HTML con i dati del DataFrame usando il layout specificato."""
        
        wide_columns = ['input', 'output']
        html_content = f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITLE__</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg: #f8fafc;
            --card: #ffffff;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --warning: #f59e0b;
        }}

        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            font-size: 13px;
            line-height: 1.5;
            margin: 0;
            padding: 24px;
            background-color: var(--bg);
            color: var(--text-main);
        }}

        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }}

        h1 {{
            font-size: 24px;
            font-weight: 700;
            margin: 0;
            color: #0f172a;
        }}

        .controls-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .section-title {{
            font-size: 14px;
            font-weight: 600;
            margin: 0 0 12px 0;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .column-checkboxes {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .checkbox-container {{
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            padding: 6px 12px;
            background: #f1f5f9;
            border-radius: 6px;
            transition: all 0.2s;
        }}

        .checkbox-container:hover {{
            background: #e2e8f0;
        }}

        .checkbox-container input {{
            accent-color: var(--primary);
        }}

        .btn-group {{
            display: flex;
            gap: 8px;
            margin-top: 16px;
        }}

        button {{
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 500;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid var(--border);
            background: white;
            color: var(--text-main);
        }}

        button:hover {{
            background: #f8fafc;
        }}

        button.btn-primary {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        button.btn-primary:hover {{
            background: var(--primary-hover);
        }}

        .table-container {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow-x: auto;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            background: #f1f5f9;
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: #475569;
            font-size: 12px;
            border-bottom: 2px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            vertical-align: top;
            font-family: 'Inter', sans-serif;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover td {{
            background-color: #f8fafc;
        }}

        .wide-column {{ min-width: 450px; }}
        .narrow-column {{ min-width: 100px; }}
        .numeric-column {{ min-width: 80px; text-align: right; }}
        .timestamp-column {{ min-width: 150px; color: var(--text-muted); font-size: 11px; }}

        .hidden-column {{ display: none !important; }}

        details {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-top: 4px;
        }}

        summary {{
            padding: 8px 12px;
            cursor: pointer;
            font-weight: 500;
            color: var(--primary);
            user-select: none;
        }}

        summary:hover {{
            color: var(--primary-hover);
        }}

        .detail-content {{
            padding: 12px;
            border-top: 1px solid #e2e8f0;
            font-family: 'Fira Code', monospace;
            font-size: 12px;
            white-space: pre-wrap;
            overflow-x: auto;
        }}



        .status-badge {{
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}

        .status-filtering {{ background: #dcfce7; color: #166534; }}
        .status-ranking {{ background: #ede9fe; color: #5b21b6; }}
        .status-evaluation {{ background: #fee2e2; color: #991b1b; }}



        /* Nuovi stili per visualizzazione a Tab */
        .tabs-header {{
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding: 12px 4px;
            margin-bottom: 24px;
            border-bottom: 2px solid var(--border);
            scrollbar-width: thin;
        }}

        .tab-btn {{
            padding: 10px 20px;
            background: #e2e8f0;
            border: 1px solid var(--border);
            border-radius: 12px 12px 0 0;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s;
            color: var(--text-muted);
            font-size: 13px;
        }}

        .tab-btn:hover {{
            background: #cbd5e1;
        }}

        .tab-btn.active {{
            background: var(--card);
            color: var(--primary);
            border-bottom-color: var(--card);
            margin-bottom: -2px;
            box-shadow: 0 -4px 6px -1px rgba(0,0,0,0.05);
        }}

        .tab-pane {{
            display: none;
            flex-direction: column;
            gap: 16px;
            animation: fadeIn 0.3s ease;
        }}

        .tab-pane.active {{
            display: flex;
        }}

        .record-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 0;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        }}

        .record-property {{
            display: grid;
            grid-template-columns: 200px 1fr;
            border-bottom: 1px solid var(--border);
        }}

        .record-property:last-child {{
            border-bottom: none;
        }}

        .property-label {{
            padding: 16px 20px;
            background: #f8fafc;
            font-weight: 700;
            color: #475569;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-right: 1px solid var(--border);
            display: flex;
            align-items: center;
        }}

        .property-value {{
            padding: 16px 20px;
            font-size: 13px;
            line-height: 1.6;
            word-break: break-word;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(5px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        @media (max-width: 768px) {{
            .record-property {{
                grid-template-columns: 1fr;
            }}
            .property-label {{
                border-right: none;
                border-bottom: 1px solid var(--border);
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>__TITLE__</h1>
    </div>
    
    <div class="controls-card">
        <div class="btn-group" style="margin-top: 0;">
            <button onclick="toggleAllDetails(true)">Espandi Tutto</button>
            <button onclick="toggleAllDetails(false)">Comprimi Tutto</button>
        </div>
    </div>
"""

        # Render table or tabs based on view_mode
        if view_mode == "tabs":
            # Tabbed interface
            html_content += """
    <div class="tabs-header" id="tabsHeader">
"""
            for i, row in df.iterrows():
                agent_name = row.get('agent_name', f'Record {i+1}')
                agent_mode = row.get('agent_mode', '')
                
                # Calcola il nome della tab in base al tipo di agente
                if agent_name.lower() == "sql-agent":
                    retry_label = f"relaxation iter. {int(row['retry_id'])}"
                    display_name = f"{agent_name} ({retry_label})"
                else:
                    display_name = f"{agent_name} ({agent_mode})"
                
                # Aggiungi batch_id se presente come intero
                batch_info = f" (Batch {int(row['batch_id'])})" if pd.notna(row.get('batch_id')) else ""
                html_content += f'        <button class="tab-btn {"active" if i == 0 else ""}" onclick="showTab({i})">{display_name}{batch_info}</button>\n'
            
            html_content += """
    </div>
    
    <div id="tabPanes">
"""
            for i, row in df.iterrows():
                html_content += f'        <div class="tab-pane {"active" if i == 0 else ""}" id="tab-{i}">\n'
                html_content += '            <div class="record-card">\n'
                
                for col in df.columns:
                    value = row[col]
                    display_value = ""
                    
                    if col == "notes":
                        continue
                    elif pd.isna(value):
                        display_value = '<span style="color: #94a3b8; font-style: italic;">vuoto</span>'
                    else:
                        if 'timestamp' in col.lower() and isinstance(value, pd.Timestamp):
                            display_value = value.strftime('%Y-%m-%d %H:%M:%S')
                        elif 'execution_time' in col.lower() and isinstance(value, (int, float)):
                            display_value = f"{int(value)}ms"
                        elif col == 'agent_mode':
                            display_value = f'<span class="status-badge status-{value}">{value}</span>'
                        else:
                            display_value = str(value).replace('\\n', '<br>').replace('\\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
                    
                    # Rendi le colonne larghe comprimibili
                    if col in wide_columns and display_value and not display_value.startswith('<span'):
                        summary_text = f"Dettaglio {col}"
                        if col == 'output' and 'agent_name' in row:
                            summary_text = f"Output {row['agent_name']}"
                        
                        display_value = f'<details class="cell-details" open><summary>{summary_text}</summary><div class="detail-content">{display_value}</div></details>'

                    html_content += f'                <div class="record-property">\n'
                    html_content += f'                    <div class="property-label">{col}</div>\n'
                    html_content += f'                    <div class="property-value">{display_value}</div>\n'
                    html_content += f'                </div>\n'
                
                html_content += '            </div>\n'
                html_content += '        </div>\n'
            
            html_content += '    </div>\n'
        else:
            # Traditional table view
            html_content += """
    <div class="table-container">
        <table id="dataTable">
            <thead>
                <tr>
"""
            for col in df.columns:
                col_class = "narrow-column"
                if col in wide_columns: col_class = "wide-column"
                elif pd.api.types.is_numeric_dtype(df[col]): col_class = "numeric-column"
                elif 'timestamp' in col.lower(): col_class = "timestamp-column"
                
                html_content += f'<th class="{col_class}" data-column="{col}">{col}</th>'
            
            html_content += """
                </tr>
            </thead>
            <tbody>
"""
            for i, row in df.iterrows():
                html_content += f'        <tr data-index="{i}">'
                for col in df.columns:
                    value = row[col]
                    display_value = ""
                    
                    if col == "notes":
                        continue
                    elif pd.isna(value):
                        display_value = ""
                    else:
                        if 'timestamp' in col.lower() and isinstance(value, pd.Timestamp):
                            display_value = value.strftime('%Y-%m-%d %H:%M:%S')
                        elif 'execution_time' in col.lower() and isinstance(value, (int, float)):
                            display_value = f"{int(value)}ms"
                        elif col == 'agent_mode':
                            display_value = f'<span class="status-badge status-{value}">{value}</span>'
                        else:
                            display_value = str(value).replace('\\n', '<br>').replace('\\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
                    
                    # Rendi le colonne larghe comprimibili
                    if col in wide_columns and display_value:
                        summary_text = f"Dettaglio {col}"
                        if col == 'output' and 'agent_name' in row:
                            summary_text = f"Output {row['agent_name']}"
                        
                        display_value = f'<details class="cell-details" open><summary>{summary_text}</summary><div class="detail-content">{display_value}</div></details>'

                    col_class = "narrow-column"
                    if col in wide_columns: col_class = "wide-column"
                    elif pd.api.types.is_numeric_dtype(df[col]): col_class = "numeric-column"
                    elif 'timestamp' in col.lower(): col_class = "timestamp-column"
                    
                    html_content += f'<td class="{col_class}" data-column="{col}">{display_value}</td>'
                html_content += "</tr>\n"
            
            html_content += """
            </tbody>
        </table>
    </div>
"""

        html_content += """
    <script>
        // Stato locale dei dati
        let localData = {
"""
        html_content += f"            json_file: '{json_filename or ''}',\n"
        html_content += """            executions: [] 
        };

        localData.executions = [];

        function showTab(index) {
            // Update buttons
            document.querySelectorAll('.tab-btn').forEach((btn, i) => {
                btn.classList.toggle('active', i === index);
            });
            // Update panes
            document.querySelectorAll('.tab-pane').forEach((pane, i) => {
                pane.classList.toggle('active', i === index);
            });
        }

        function toggleAllDetails(open) {
            document.querySelectorAll('details').forEach(d => d.open = open);
        }

        function toggleColumn(columnName) {
            const isChecked = document.querySelector(`input[data-column="${columnName}"]`)?.checked;
            if (isChecked === undefined) return;
            
            document.querySelectorAll(`th[data-column="${columnName}"], td[data-column="${columnName}"]`).forEach(element => {
                element.classList.toggle('hidden-column', !isChecked);
            });
            
            // Per la vista a TAB, nascondiamo i record-property
            document.querySelectorAll('.record-property').forEach(prop => {
                if (prop.querySelector('.property-label').innerText === columnName) {
                    prop.style.display = isChecked ? 'grid' : 'none';
                }
            });
        }

        document.addEventListener('DOMContentLoaded', function() {
            // Inizializza eventuali stati necessari
        });
    </script>
</body>
</html>"""
        return html_content.replace("__TITLE__", title)

    def _write_log_entry(self, entry: Dict):
        """Scrive una singola entry nel file JSONL."""
        if self.current_log_file:
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def _dict_to_html_table(self, data: dict) -> str:
        """Converte un dizionario in una tabella HTML inline."""
        if not data:
            return ""
        
        html = '<details open><summary style="font-size:10px;">Dict ({})</summary>'.format(len(data))
        html += '<table class="subtable" style="font-size: 11px;">'
        
        sorted_keys = sorted(data.keys(), key=lambda k: (0 if k.lower() == 'id' else 1 if 'score' in k.lower() else 2, k))
        
        for key in sorted_keys:
            value = data[key]
            if isinstance(value, dict):
                display_value = self._dict_to_html_table(value)
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    display_value = self._list_of_dicts_to_html_table(value)
                else:
                    display_value = '<br>'.join(str(item) for item in value)
            else:
                display_value = str(value).replace('\\n', '<br>')
            
            html += f'<tr><td style="background-color: #f9f9f9; font-weight: bold;">{key}</td>'
            html += f'<td>{display_value}</td></tr>'
        
        html += '</table></details>'
        return html
    
    def _list_of_dicts_to_html_table(self, data: list) -> str:
        """Converte una lista di dizionari in una tabella HTML inline."""
        if not data:
            return ""
        
        if isinstance(data[0], dict):
            all_keys = set()
            for item in data:
                if isinstance(item, dict):
                    all_keys.update(item.keys())
            
            if not all_keys:
                return str(data)
            
            html = '<details open><summary style="font-size:10px;">List [{} items]</summary>'.format(len(data))
            html += '<table class="subtable" style="font-size: 11px;">'
            
            sorted_keys = sorted(all_keys, key=lambda k: (0 if k.lower() == 'id' else 1 if 'score' in k.lower() else 2, k))
            
            html += '<tr>'
            for key in sorted_keys:
                html += f'<th style="background-color: #e8f5e8;">{key}</th>'
            html += '</tr>'
            
            for item in data:
                if isinstance(item, dict):
                    html += '<tr>'
                    for key in sorted_keys:
                        value = item.get(key, '')
                        if isinstance(value, dict):
                            display_value = self._dict_to_html_table(value)
                        elif isinstance(value, list):
                            if value and isinstance(value[0], dict):
                                display_value = self._list_of_dicts_to_html_table(value)
                            else:
                                display_value = '<br>'.join(str(item) for item in value)
                        else:
                            display_value = str(value).replace('\\n', '<br>')
                        html += f'<td>{display_value}</td>'
                    html += '</tr>'
            
            html += '</table></details>'
            return html
        else:
            return '<br>'.join(str(item) for item in data)
    
    def _parse_markdown_simple(self, text: str) -> str:
        """Parsing markdown semplice per output non-JSON."""
        if not isinstance(text, str):
            return str(text)
        
        text = re.sub(r'^##\s+(.+)$', r'<strong>\1</strong>', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        
        return text

    def _serialize_data(self, data: Any) -> Any:
        """Serializza i dati in formato JSON-compatibile con parsing intelligente e unescaping ricorsivo."""
        
        try:
            def _unescape_string(text: str) -> str:
                if not isinstance(text, str):
                    return text
                
                try:
                    # Rimuovi escaping eccessivo se presente
                    while '\\\\' in text and len(text) < 10000: # Protezione per stringhe enormi
                        text = text.replace('\\\\', '\\')
                    
                    unescape_map = {
                        '\\n': '\n', '\\t': '\t', '\\r': '\r', '\\"': '"', "\\'": "'", '\\\\': '\\'
                    }
                    
                    for escaped, unescaped in unescape_map.items():
                        text = text.replace(escaped, unescaped)
                except Exception:
                    pass
                
                return text
            
            def _looks_like_json(s: str) -> bool:
                # Fast pre-check to avoid json.loads exceptions that break the debugger
                s_trimmed = s.strip()
                if len(s_trimmed) < 2:
                    return False
                
                # Case 1: JSON Object
                if s_trimmed.startswith('{') and s_trimmed.endswith('}'):
                    if s_trimmed == '{}':
                        return True
                    # A non-empty JSON object must have double quotes for keys followed by :
                    # This captures the majority of actual JSON while skipping things like "{ some text }"
                    return '":' in s_trimmed
                
                # Case 2: JSON Array
                if s_trimmed.startswith('[') and s_trimmed.endswith(']'):
                    if s_trimmed == '[]':
                        return True
                    # Check first significant char after [
                    inner = s_trimmed[1:].lstrip()
                    if not inner:
                        return False
                    # Must start with ", {, [, number, true, false, null
                    return inner[0] in ('"', '{', '[', '-', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 't', 'f', 'n')
                
                return False

            def _process_string_value(text: str, try_json: bool = True) -> Any:
                if not text or not isinstance(text, str):
                    return text
                
                text_stripped = text.strip()
                # Se sembra JSON, prova a parsarlo
                if try_json and _looks_like_json(text_stripped):
                    try:
                        parsed = json.loads(text_stripped)
                        return self._serialize_data(parsed)
                    except Exception:
                        pass 
                
                unescaped = _unescape_string(text)
                unescaped_stripped = unescaped.strip()
                
                # Prova a parsare di nuovo dopo unescaping se sembra JSON
                if try_json and _looks_like_json(unescaped_stripped):
                    try:
                        # Pulizia euristica per quote non valide dentro i valori
                        repaired = re.sub(r'(:\s*")(.+?)("\s*[,}])', 
                                         lambda m: m.group(1) + m.group(2).replace('"', "'") + m.group(3), 
                                         unescaped_stripped, flags=re.DOTALL)
                        repaired = re.sub(r'(,\s*")(.+?)("\s*[,\]])', 
                                         lambda m: m.group(1) + m.group(2).replace('"', "'") + m.group(3), 
                                         repaired, flags=re.DOTALL)
                        repaired = re.sub(r'(\[\s*")(.+?)("\s*[,\]])', 
                                         lambda m: m.group(1) + m.group(2).replace('"', "'") + m.group(3), 
                                         repaired, flags=re.DOTALL)
                        
                        if repaired != unescaped_stripped:
                            try:
                                parsed = json.loads(repaired)
                                return self._serialize_data(parsed)
                            except:
                                pass
                        # In ogni caso proviamo un loads su quello unescaped se non riparato
                        else:
                            try:
                                parsed = json.loads(unescaped_stripped)
                                return self._serialize_data(parsed)
                            except:
                                pass
                    except Exception:
                        pass
                
                # Se la stringa è molto lunga e ha ritorni a capo, dividila (per tabella)
                if len(unescaped) > 200 and '\n' in unescaped:
                    return unescaped.split('\n')
                
                return unescaped
            
            if isinstance(data, str):
                return _process_string_value(data)
            elif isinstance(data, (int, float, bool, type(None))):
                return data
            elif isinstance(data, dict):
                # Caso speciale per PromptRecord (classe pydantic vista come dict)
                if 'full_text' in data and 'system' in data and 'user' in data:
                    return _process_string_value(data['full_text'], try_json=False)
                result = {}
                for k, v in data.items():
                    result[k] = self._serialize_data(v)
                return result
            elif isinstance(data, (list, tuple)):
                return [self._serialize_data(item) for item in data]
            elif isinstance(data, pd.DataFrame):
                return {
                    "_type": "DataFrame",
                    "shape": data.shape,
                    "columns": data.columns.tolist(),
                    "data_preview": data.head(5).to_dict('records') if len(data) > 0 else []
                }
            elif ChatPromptTemplate is not None and isinstance(data, ChatPromptTemplate):
                try:
                    messages = []
                    for msg in data.messages:
                        if hasattr(msg, 'content'):
                            msg_type = "SYSTEM" if msg.__class__.__name__ == "SystemMessage" else "USER"
                            messages.append(f"[{msg_type}]\n{msg.content}")
                        else:
                            messages.append(str(msg))
                    return "\n\n".join(messages)
                except Exception:
                    return f"ChatPromptTemplate: {str(data)}"
            elif hasattr(data, 'model_dump'):
                return self._serialize_data(data.model_dump())
            elif hasattr(data, '__dict__'):
                return self._serialize_data(data.__dict__)
            else:
                return str(data)
        except Exception as e:
            # Fallback estremo per non crashare mai
            return f"[Serialization Error: {str(e)}]"
