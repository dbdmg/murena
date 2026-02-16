import base64
import json
import os
from pathlib import Path
from typing import Any, List, Dict, Union
import pandas as pd
import numpy as np

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

from app.core.config import AGENT_MODELS, USE_MOCK_NORMATIVE_AGENT
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import NormativeAgentResult, PromptRecord, NormativeResponse
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json

def _load_normative_documents() -> tuple[str, list[str], List[Dict[str, Any]]]:
    """
    Carica tutti i documenti normativi dalla cartella docs/knowledge/normativa/
    Restituisce una tupla: (testo_concatenato, lista_percorsi_file, lista_immagini_base64)
    """
    backend_dir = Path(__file__).parent.parent.parent.parent.parent
    normative_dir = backend_dir / "docs" / "knowledge" / "normativa"
    
    if not normative_dir.exists():
        return "Nessun documento normativo disponibile.", [], []
    
    documents = []
    sources = []
    images = []
    
    for file_path in normative_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in [".txt", ".md", ".json", ".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
            try:
                if file_path.suffix.lower() in [".txt", ".md"]:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        documents.append(f"--- Documento: {file_path.name} ---\n{content}\n")
                        sources.append(str(file_path.relative_to(normative_dir.parent.parent.parent)))
                elif file_path.suffix.lower() == ".json":
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = json.load(f)
                        content_str = json.dumps(content, indent=2, ensure_ascii=False)
                        documents.append(f"--- Documento: {file_path.name} (JSON) ---\n{content_str}\n")
                        sources.append(str(file_path.relative_to(normative_dir.parent.parent.parent)))
                elif file_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
                    with open(file_path, "rb") as f:
                        image_data = base64.b64encode(f.read()).decode('utf-8')
                        mime_type = f"image/{file_path.suffix.lower()[1:]}"
                        if file_path.suffix.lower() in [".jpg", ".jpeg"]:
                            mime_type = "image/jpeg"
                        images.append({
                            "name": file_path.name,
                            "data": image_data,
                            "mime_type": mime_type
                        })
                        documents.append(f"--- Immagine: {file_path.name} (inclusa per analisi visiva) ---\n")
                        sources.append(str(file_path.relative_to(normative_dir.parent.parent.parent)))
                elif file_path.suffix.lower() in [".pdf", ".doc", ".docx"]:
                    documents.append(f"--- Documento: {file_path.name} (file binario) ---\n")
                    sources.append(str(file_path.relative_to(normative_dir.parent.parent.parent)))
            except Exception:
                continue
    
    if not documents:
        return "Nessun documento normativo disponibile.", [], []
    
    return "\n\n".join(documents), sources, images


class NormativeAgent(BaseAgent):
    name = "normative-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name or AGENT_MODELS.get("normative_agent") or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)
        
        self.system_prompt = get_system_prompt("normative_agent")
        self.user_template = get_user_template("normative_agent")

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )
        self.parser = StrOutputParser()
        self.chain = self.prompt | self.llm | self.parser

    @log_llm_usage
    @handle_agent_error(
        fallback_value=NormativeAgentResult(raw_text="{}", sources=[], prompt=None)
    )
    def run(self, *, query: str = None, mode: str = "filtering", **kwargs) -> Union[NormativeAgentResult, pd.DataFrame]:
        """
        Esegue l'agente in due modalità:
        - filtering: Estrae i requisiti normativi dai documenti.
        - ranking: Calcola uno score deterministico (0-100) basato sull'aderenza ai requisiti.
        """
        if mode == "filtering":
            return self._run_filtering(
                query=query, 
                available_columns=kwargs.get("available_columns"),
                statistics=kwargs.get("statistics")
            )
        elif mode == "ranking":
            return self._run_ranking(
                df=kwargs.get("df"),
                requirements=kwargs.get("requirements"),
                available_columns=kwargs.get("available_columns"),
                global_stats=kwargs.get("global_stats")
            )
        else:
            raise ValueError(f"Modalità '{mode}' non supportata dal NormativeAgent.")

    def _run_filtering(self, query: str, available_columns: List[str] = None, statistics: dict = None) -> NormativeAgentResult:
        if USE_MOCK_NORMATIVE_AGENT:
            # ... (mock stays mostly same but could include stats if needed)
            mock_json = {
                "found": True,
                "requisiti": [
                    {
                        "categoria": "use_case",
                        "tipo": "destinazione ammessa",
                        "valore": "Abitazione",
                        "unita": "N/A",
                        "operatore": "LIKE",
                        "colonna_target": "tipologia_bene_immobile",
                        "normativa": "D.M. 5/7/1975",
                        "ambito": "per alloggi",
                        "descrizione": "Solo immobili residenziali"
                    }
                ]
            }
            return NormativeAgentResult(
                raw_text=json.dumps(mock_json, indent=2, ensure_ascii=False),
                sources=["https://mock-normativa.it"],
                has_requirements=True,
                prompt=PromptRecord(system="N/D", user=query),
            )
        
        normative_docs, sources, images = _load_normative_documents()
        
        # Inseriamo le colonne disponibili nel prompt
        columns_str = ", ".join(available_columns) if available_columns else "N/D"
        
        # Gestione statistiche (Data Distribution)
        stats_str = "Nessuna statistica disponibile."
        if statistics:
            stats_str = json.dumps(statistics, indent=2, ensure_ascii=False)

        # Prepare inputs for templates
        user_inputs = {
            "query": query, 
            "normative_documents": normative_docs,
            "statistics": stats_str
        }
        
        system_inputs = {
            "available_columns": columns_str
        }
        
        user_text = self.render_template(self.user_template, **user_inputs).strip()
        system_text = self.render_template(self.system_prompt, **system_inputs).strip()
        full_text = f"[SYSTEM]\n{system_text}\n\n[USER]\n{user_text}"

        
        if images:
            content = [{"type": "text", "text": full_text}]
            for img in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{img['mime_type']};base64,{img['data']}"}
                })
            message = HumanMessage(content=content)
            chain = self.llm | StrOutputParser()
            raw = chain.invoke([message])
        else:
            raw = invoke_with_langfuse(
                self.chain,
                {"system_content": system_text, "user_content": user_text},
            )
        
        norm_data = safe_extract_json(raw, schema=NormativeResponse)
        has_requirements = norm_data.found if norm_data else False

        return NormativeAgentResult(
            raw_text=raw,
            sources=sources,
            has_requirements=has_requirements,
            prompt=PromptRecord(
                system=system_text,
                user=user_text,
                full_text=full_text,
            ),
        )

    def _run_ranking(self, *, df: pd.DataFrame, requirements: List[Dict[str, Any]], available_columns: List[str] = None, global_stats: Dict[str, Any] = None) -> pd.DataFrame:
        """Modalità ranking: calcolo score deterministico 0-100 basato sui requisiti normativi."""
        if df is None or df.empty or not requirements:
            if df is not None:
                df["normative_score"] = 0
            return df

        df_ranked = df.copy()
        
        # Identifica tutte le colonne per cui è stato espresso un requisito (che esistono nel DF)
        all_req_columns = set()
        for req in requirements:
            col = req.get("colonna_target")
            if col and col in df_ranked.columns:
                all_req_columns.add(col)

        total_scores = pd.Series(0.0, index=df_ranked.index)
        valid_req_count = 0
        used_columns = set() # we still track used_columns for debug if needed, but we'll return all_req_columns
        transparency_cols = []

        for req in requirements:
            col = req.get("colonna_target")
            target_val = req.get("valore")
            op = str(req.get("operatore", ">=")).upper()

            # Filtro rigoroso sulle colonne ammesse per il CALCOLO dello score
            if not col or col not in df_ranked.columns or target_val is None:
                continue
            
            if available_columns and col not in available_columns:
                continue

            valid_req_count += 1
            used_columns.add(col)
            
            # Gestione tipi numerici vs categorici
            if op in [">=", "<=", "=="] and isinstance(target_val, (int, float)):
                vals = pd.to_numeric(df_ranked[col], errors="coerce").fillna(0)
                
                # Global vs Local Normalization
                col_stats = global_stats.get(col) if global_stats else None
                if col_stats and isinstance(col_stats, dict) and "min" in col_stats and "max" in col_stats:
                    min_val = float(col_stats["min"])
                    max_val = float(col_stats["max"])
                else:
                    min_val = vals.min()
                    max_val = vals.max()
                
                if max_val == min_val:
                    req_score = pd.Series(100.0, index=df_ranked.index)
                else:
                    if op in [">=", ">"]:
                        # Linear growth with threshold T and cap at 2T
                        # Score 0 at T, Score 100 at 2T
                        T = float(target_val)
                        if T > 0:
                            req_score = ((vals - T) / T * 100).clip(0, 100)
                        else:
                            req_score = pd.Series(100.0, index=df_ranked.index)
                    elif op in ["<=", "<"]:
                        # Linear decay with threshold T and cap at T/2
                        # Score 0 at T, Score 100 at T/2
                        T = float(target_val)
                        if T > 0:
                            req_score = ((T - vals) / (T / 2) * 100).clip(0, 100)
                        else:
                            req_score = pd.Series(0.0, index=df_ranked.index)
                    else: # ==
                        target_num = float(target_val)
                        diff = np.abs(vals - target_num)
                        
                        # Normalizzazione relativa tramite range del dataset (preferibilmente globale)
                        range_val = (max_val - min_val) if max_val != min_val else 0
                        if range_val > 0:
                            req_score = (100 - (diff / range_val * 100)).clip(0, 100)
                        else:
                            max_diff = diff.max()
                            min_diff = diff.min()
                            if max_diff == min_diff:
                                 req_score = pd.Series(100.0, index=df_ranked.index)
                            else:
                                 req_score = ((max_diff - diff) / (max_diff - min_diff) * 100).clip(0, 100)
            
                # Store partial score for this numeric requirement
                df_ranked[f"normative_partial_score_{col}"] = req_score.round(1)
                transparency_cols.append(f"normative_partial_score_{col}")
            
            else:
                # Gestione categorica / stringhe
                vals = df_ranked[col].astype(str).str.lower().str.strip()
                target_str = str(target_val).lower().strip()
                
                if col == "tipologia_bene_immobile":
                    # Punteggio basato sulla posizione nel ranking (come TypologyAgent)
                    if isinstance(target_val, str):
                        target_list = [v.lower().strip().strip("'\"") for v in target_val.split(",")]
                    elif isinstance(target_val, list):
                        target_list = [str(v).lower().strip().strip("'\"") for v in target_val]
                    else:
                        target_list = [target_str.strip("'\"")]

                    def get_rank_and_score(v):
                        v_str = str(v).lower().strip()
                        for idx, t in enumerate(target_list):
                            # Corrispondenza precisa o parziale
                            if t == v_str or t in v_str or v_str in t:
                                return round(100.0 / (idx + 1), 1), idx + 1
                        return 0.0, "N/A"

                    details = vals.apply(get_rank_and_score)
                    req_score = details.apply(lambda x: x[0])
                    rank_pos = details.apply(lambda x: x[1])
                else:
                    # Determine match (boolean series)
                    if op == "==":
                        # Strict match first
                        strict_match = (vals == target_str)
                        # Relaxed match: if target is contained in the value or vice-versa
                        partial_match = vals.str.contains(target_str, na=False, regex=False) | pd.Series([target_str in v for v in vals], index=vals.index)
                        is_match = strict_match | partial_match
                    elif op == "LIKE":
                        is_match = vals.str.contains(target_str, na=False, regex=False)
                    elif op == "IN":
                        if isinstance(target_val, str):
                            target_list = [v.lower().strip() for v in target_val.split(",")]
                        elif isinstance(target_val, list):
                            target_list = [str(v).lower().strip() for v in target_val]
                        else:
                            target_list = [target_str]
                        
                        # Exact matches in list OR any item in list is contained in value
                        is_match = vals.isin(target_list)
                        for t in target_list:
                            is_match = is_match | vals.str.contains(t, na=False, regex=False)
                    else:
                        is_match = (vals == target_str)
                    
                    # Calculate Score: 100 for match, 0 otherwise
                    req_score = is_match.astype(float) * 100
                    rank_pos = np.where(is_match, 1, "N/A")
                
                # Transparency Metadata for Categorical
                # Match = Rank N, Multiplier calculated from position
                # No Match = Rank N/A, Multiplier 0.0
                
                df_ranked[f"normative_rank_position_{col}"] = rank_pos
                
                transparency_cols.append(f"normative_rank_position_{col}")
                
                # Store partial score for this categorical requirement
                df_ranked[f"normative_partial_score_{col}"] = req_score
                transparency_cols.append(f"normative_partial_score_{col}")
                
                # Special handling for typology: also show the original typology rank if available
                if col == "tipologia_bene_immobile" and "typology_rank_position" in df_ranked.columns:
                    transparency_cols.append("typology_rank_position")
                
            total_scores += req_score

        if valid_req_count > 0:
            df_ranked["normative_score"] = (total_scores / valid_req_count).round(1)
            
            # Add transparency: weight per column
            # Since we average, the weight is simply 1 / valid_req_count for all used columns
            weight = round(1.0 / valid_req_count, 3)
            for col in used_columns:
                df_ranked[f"normative_weight_{col}"] = weight
        else:
            df_ranked["normative_score"] = 0.0

        weight_cols = [f"normative_weight_{c}" for c in used_columns]
        
        # Ensure weight columns exist (safety check)
        for wc in weight_cols:
            if wc not in df_ranked.columns:
                df_ranked[wc] = 0.0

        # Combine all requested columns and deduplicate while preserving order
        all_requested_cols = ["id", "normative_score"] + list(all_req_columns) + weight_cols + transparency_cols
        unique_cols = []
        for c in all_requested_cols:
            if c not in unique_cols and c in df_ranked.columns:
                unique_cols.append(c)
                
        return df_ranked[unique_cols]