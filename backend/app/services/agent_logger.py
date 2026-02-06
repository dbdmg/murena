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
        
        # Estrai output dall'output (se presente)
        output_extracted = None
        if agent_name.lower() == "ape-agent" and hasattr(output_data, 'suggested_filters'):
            output_extracted = output_data.suggested_filters
        elif agent_name == "ranking-agent":
            # Per il ranking agent, preferiamo il ranking ordinato se presente, altrimenti i pesi
            if hasattr(output_data, 'ranking') and output_data.ranking:
                output_extracted = {"ranking": output_data.ranking.ranking}
            elif hasattr(output_data, 'weights'):
                output_extracted = output_data.weights.model_dump()
        elif agent_name == "poi-agent":
            # Per il POI agent (filtering), mostriamo categorie e punteggi minimi
            if hasattr(output_data, 'categories') and hasattr(output_data, 'punteggi_minimi'):
                output_extracted = {
                    "ordered_categories": output_data.categories,
                    "min_scores": output_data.punteggi_minimi
                }
        elif hasattr(output_data, 'raw_text'):
            output_extracted = output_data.raw_text
        elif isinstance(output_data, dict) and 'raw_text' in output_data:
            output_extracted = output_data['raw_text']
        elif isinstance(output_data, pd.DataFrame):
            # Safe conversion to list of dicts to handle NaNs for JSON serialization
            output_extracted = json.loads(output_data.to_json(orient="records"))
        
        log_entry = {
            "agent_name": agent_name,
            "agent_mode": agent_mode,
            "timestamp": datetime.now().isoformat(),
            "execution_time_ms": execution_time_ms,
            "input": self._serialize_data(input_extracted) if input_extracted is not None else None,
            "output": self._serialize_data(output_extracted) if output_extracted is not None else None,
            "output_structure": self._serialize_data(output_data) if output_data is not None else None
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
            
            # === SALVATAGGIO HTML ===
            # Usa il metodo generate_html_view per ottenere la stringa HTML
            html_content = self.generate_html_view(agent_executions, f"Agent Executions (Run {run_props.get('run_number')})")
            
            html_dir = self.log_dir
            agent_html = html_dir / f"agent_executions_{run_props.get('use_case')}_{run_props.get('prompt_id')}_run{run_props.get('run_number')}.html"
            
            with open(agent_html, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            print(f"💾 HTML salvato: {agent_html.name}")
            
            # Elimina il file JSON dopo aver creato l'HTML
            if json_file.exists():
                try:
                    json_file.unlink()
                except Exception as e:
                    print(f"⚠️ Errore nell'eliminare JSON {json_file.name}: {e}")
                    
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
                    
                # Copia entry e serializza input/output per uniformità (importante per il live)
                entry = e.copy()
                
                # Applichiamo la stessa serializzazione usata in testing per uniformare la visualizzazione
                input_val = entry.get("input")
                output_val = entry.get("output")
                
                try:
                    serialized_input = self._serialize_data(input_val) if input_val is not None else None
                    serialized_output = self._serialize_data(output_val) if output_val is not None else None
                except Exception as ex:
                    print(f"⚠️ Errore durante la serializzazione dell'entry {entry.get('agent_name')}: {ex}")
                    serialized_input = str(input_val)
                    serialized_output = str(output_val)
                
                if entry["agent_name"] == "evaluation-agent":
                    # Estrai la lista di valutazioni se presente in un dizionario
                    items_to_log = []
                    if isinstance(serialized_output, list):
                        items_to_log = serialized_output
                    elif isinstance(serialized_output, dict):
                        # Cerca chiavi comuni che contengono liste di risultati
                        for k in ["evaluations", "results", "valutazioni"]:
                            if k in serialized_output and isinstance(serialized_output[k], list):
                                items_to_log = serialized_output[k]
                                break
                        if not items_to_log:
                            items_to_log = [serialized_output]
                    else:
                        items_to_log = [serialized_output]

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

    def generate_html_view(self, agent_executions: List[Dict], title: str) -> str:
        """Genera la stringa HTML completa per la visualizzazione tabellare."""
        
        # DataFrame per TUTTE le agent executions
        agent_rows = []
        for execution in agent_executions:
            # Funzione helper per convertire input/output in stringa o tabella HTML
            def to_display_value(value, field_name=None):
                if value is None:
                    return None
                elif field_name == "output_structure" and isinstance(value, dict):
                    # Per output_structure, mostra solo le chiavi
                    return "<br>".join(sorted(value.keys()))
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
                "run_number": execution.get("run_number"),
                "run_timestamp": execution.get("run_timestamp"),
                "batch_id": execution.get("batch_id"),
                "agent_name": execution.get("agent_name"),
                "agent_mode": execution.get("agent_mode"),
                "timestamp": execution.get("timestamp"),
                "execution_time_ms": execution.get("execution_time_ms"),
                "input": to_display_value(execution.get("input"), "input"),
                "output_structure": to_display_value(execution.get("output_structure"), "output_structure"),
                "output": to_display_value(execution.get("output"), "output")
            })
        
        df = pd.DataFrame(agent_rows)
        
        if df.empty:
             return "<html><body><h1>Nessun dato registrato</h1></body></html>"

        # Raggruppa per retry
        df['retry_id'] = df.groupby(['agent_name', 'run_number', 'batch_id', 'agent_mode'], dropna=False).cumcount() + 1
        
        desired_order = [
            'use_case', 'prompt_id', 'run_number', 'run_timestamp', 
            'agent_name', 'agent_mode', 'batch_id', 'retry_id', 'timestamp',
            'execution_time_ms', 'input', 'output_structure', 'output'
        ]
        existing_columns = [col for col in desired_order if col in df.columns]
        df = df[existing_columns]
        
        # Format timestamps
        if "run_timestamp" in df.columns:
            df["run_timestamp"] = pd.to_datetime(df["run_timestamp"], errors='coerce')
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')

        return self._render_html_template(df, title)

    def _render_html_template(self, df: pd.DataFrame, title: str) -> str:
        """Renderizza il template HTML con i dati del DataFrame."""
        
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
        }}
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
        }}
        table.subtable td {{
            padding: 2px 4px;
            border-bottom: 1px solid #eee;
        }}
        td {{
            padding: 8px;
            border-bottom: 1px solid #ddd;
            vertical-align: top;
            overflow: hidden;
        }}
        .wide-column {{
             width: 400px;
             min-width: 300px;
             word-wrap: break-word;
             white-space: pre-wrap;
             word-break: break-word;
             overflow-wrap: break-word;
        }}
        .narrow-column {{ width: 75px; word-wrap: break-word; }}
        .numeric-column {{ text-align: right; width: 50px; }}
        .timestamp-column {{ width: 90px; }}
        .hidden-column {{ display: none !important; }}
        details {{
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 4px;
            background-color: #fcfcfc;
            margin: 2px 0;
        }}
        summary {{ cursor: pointer; font-weight: bold; color: #2196F3; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    
    <div class="column-controls">
        <h3>Mostra/Nascondi Colonne</h3>
        <div class="column-checkboxes" id="columnCheckboxes">
"""
        wide_columns = ['input', 'output', 'output_structure']
        for col in df.columns:
            # Per default, nascondi colonne tecniche, mostra colonne dati
            default_hidden = col in ['use_case', 'prompt_id', 'run_number', 'batch_id', 'run_timestamp', 'timestamp', 'execution_time_ms', 'output_structure']
            checked = "" if default_hidden else "checked"
            # Single braces for variables in f-string
            html_content += f'<label><input type="checkbox" {checked} data-column="{col}" onchange="toggleColumn(\'{col}\')"> {col}</label>'

        html_content += """
        </div>
        <div style="margin-top: 15px; border-top: 1px solid #eee; padding-top: 10px;">
            <button onclick="toggleAllDetails(true)">Espandi Tutti i Dettagli</button>
            <button onclick="toggleAllDetails(false)">Comprimi Tutti i Dettagli</button>
        </div>
    </div>
    
    <div style="overflow-x: auto;">
        <table id="dataTable">
"""
        # Header
        html_content += "        <thead><tr>"
        for col in df.columns:
            col_class = "wide-column" if col in wide_columns else "narrow-column"
            if pd.api.types.is_numeric_dtype(df[col]):
                col_class = "numeric-column"
            elif 'timestamp' in col.lower():
                col_class = "timestamp-column"
            
            html_content += f'<th class="{col_class}" data-column="{col}">{col}</th>'
        html_content += "</tr></thead>\\n"
        
        # Body
        html_content += "        <tbody>\\n"
        for _, row in df.iterrows():
            html_content += "        <tr>"
            for col in df.columns:
                value = row[col]
                if pd.isna(value):
                    display_value = ""
                else:
                    if 'timestamp' in col.lower() and isinstance(value, pd.Timestamp):
                        display_value = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif 'execution_time' in col.lower() and isinstance(value, (int, float)):
                        display_value = f"{int(value)}"
                    elif col == 'batch_id' and isinstance(value, (int, float)):
                        display_value = f"{int(value)}"
                    else:
                        display_value = str(value).replace('\\n', '<br>').replace('\\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
                
                # Rendi le colonne larghe comprimibili
                if col in wide_columns and display_value:
                    summary_text = f"Dettaglio {col}"
                    if col == 'output' and 'agent_name' in row:
                        summary_text = f"Output {row['agent_name']}"
                    
                    display_value = f'<details class="cell-details"><summary>{summary_text}</summary><div style="margin-top:5px;">{display_value}</div></details>'

                col_class = "wide-column" if col in wide_columns else "narrow-column"
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_class = "numeric-column"
                elif 'timestamp' in col.lower():
                    col_class = "timestamp-column"
                
                html_content += f'<td class="{col_class}" data-column="{col}">{display_value}</td>'
            html_content += "</tr>\\n"
        
        html_content += """        </tbody>
    </table>
    </div>

    <script>
        function toggleAllDetails(open) {
            document.querySelectorAll('details').forEach(d => d.open = open);
        }
        function toggleColumn(columnName) {
            const isChecked = document.querySelector(`input[data-column="${columnName}"]`).checked;
            document.querySelectorAll(`th[data-column="${columnName}"], td[data-column="${columnName}"]`).forEach(element => {
                element.classList.toggle('hidden-column', !isChecked);
            });
        }
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                toggleColumn(checkbox.dataset.column);
            });
        });
    </script>
</body>
</html>"""
        return html_content

    def _write_log_entry(self, entry: Dict):
        """Scrive una singola entry nel file JSONL."""
        if self.current_log_file:
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def _dict_to_html_table(self, data: dict) -> str:
        """Converte un dizionario in una tabella HTML inline."""
        if not data:
            return ""
        
        html = '<details><summary style="font-size:10px;">Dict ({})</summary>'.format(len(data))
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
            
            html = '<details><summary style="font-size:10px;">List [{} items]</summary>'.format(len(data))
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

