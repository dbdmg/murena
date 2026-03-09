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
from app.core.constants import NORMATIVE_AGENT_COLUMNS
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json
from app.utils.scoring import calculate_continuous_score, calculate_discrete_score

def load_normative_documents() -> tuple[str, list[str], List[Dict[str, Any]]]:
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
        
        normative_docs, sources, images = load_normative_documents()
        
        # Inseriamo le colonne disponibili nel prompt
        # Priority to specifically passed available_columns, fallback to constants
        cols_list = available_columns or NORMATIVE_AGENT_COLUMNS
        columns_str = "\n".join([f"- `{col}`" for col in cols_list]) if cols_list else "N/D"
        
        # Gestione statistiche (Data Distribution)
        stats_str = "Nessuna statistica disponibile."
        if statistics:
            stats_str = json.dumps(statistics, indent=2, ensure_ascii=False)

        # Prepare inputs for templates
        prompt_inputs = {
            "query": query, 
            "normative_documents": normative_docs,
            "statistics": stats_str,
            "reference_columns": columns_str
        }
        
        user_text = self.render_template(self.user_template, **prompt_inputs).strip()
        system_text = self.render_template(self.system_prompt, **prompt_inputs).strip()
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
            # Tenta la conversione numerica per distinguere la logica (numerica vs categorica)
            try:
                target_num = float(target_val)
                is_numeric = True
            except (ValueError, TypeError):
                is_numeric = False
            
            if is_numeric and op in [">=", ">", "<=", "<", "=="]:
                vals = pd.to_numeric(df_ranked[col], errors="coerce").fillna(0)
                
                # Global vs Local Normalization
                col_stats = global_stats.get(col) if global_stats else None
                
                # Usa l'utilità centralizzata per variabili continue
                if op in [">=", ">", "<=", "<"]:
                    exclusive = req.get("exclusive", False)
                    req_score = calculate_continuous_score(vals, target_num, op, exclusive)
                else: # ==
                    diff = np.abs(vals - target_num)
                    
                    # Normalizzazione relativa tramite range del dataset (preferibilmente globale)
                    range_val = 0
                    if col_stats:
                        range_val = float(col_stats.get("max", 0)) - float(col_stats.get("min", 0))
                        
                    if range_val > 0:
                        req_score = (100 - (diff / range_val * 100)).clip(0, 100)
                    else:
                        req_score = (vals == target_num).astype(float) * 100.0
            
                col_name = f"normative_partial_score_{col}"
                # Handle duplicate names if multiple requirements exist for the same column
                if col_name in df_ranked.columns:
                    idx = 1
                    while f"{col_name}_{idx}" in df_ranked.columns:
                        idx += 1
                    col_name = f"{col_name}_{idx}"
                
                # Store partial score for this numeric requirement
                df_ranked[col_name] = req_score.round(1)
                transparency_cols.append(col_name)
            
            else:
                # Gestione categorica / stringhe
                vals = df_ranked[col].astype(str).str.lower().str.strip()
                target_str = str(target_val).lower().strip()
                
                if col == "tipologia_bene_immobile":
                    # Punteggio basato sulla posizione nel ranking (come PropertyTechnicalAgent)
                    if isinstance(target_val, str):
                        target_list = [v.lower().strip().strip("'\"") for v in target_val.split(",")]
                    elif isinstance(target_val, list):
                        target_list = [str(v).lower().strip().strip("'\"") for v in target_val]
                    else:
                        target_list = [target_str.strip("'\"")]

                    # Usa l'utilità centralizzata per variabili discrete
                    req_score = calculate_discrete_score(df_ranked[col], target_list)
                    rank_pos = np.where(req_score > 0, 1, "N/A") # Placeholder per posizionalità
                else:
                    # Determine match (boolean series)
                    if op == "==":
                        # Usa l'utilità centralizzata come match secco (single choice = 100)
                        req_score = calculate_discrete_score(df_ranked[col], [target_str])
                    elif op == "LIKE" or op == "IN":
                        if isinstance(target_val, str):
                            target_list = [v.lower().strip() for v in target_val.split(",")]
                        elif isinstance(target_val, list):
                            target_list = [str(v).lower().strip() for v in target_val]
                        else:
                            target_list = [target_str]
                        
                        # Usa l'utilità centralizzata per set di valori
                        req_score = calculate_discrete_score(df_ranked[col], target_list)
                    else:
                        req_score = (vals == target_str).astype(float) * 100.0
                    
                    is_match = req_score > 0
                    rank_pos = np.where(is_match, 1, "N/A")
                
                # Transparency Metadata for Categorical
                
                pos_col = f"normative_rank_position_{col}"
                if pos_col in df_ranked.columns:
                    idx = 1
                    while f"{pos_col}_{idx}" in df_ranked.columns:
                        idx += 1
                    pos_col = f"{pos_col}_{idx}"
                df_ranked[pos_col] = rank_pos
                transparency_cols.append(pos_col)
                
                # Store partial score for this categorical requirement
                col_name = f"normative_partial_score_{col}"
                if col_name in df_ranked.columns:
                    idx = 1
                    while f"{col_name}_{idx}" in df_ranked.columns:
                        idx += 1
                    col_name = f"{col_name}_{idx}"
                
                df_ranked[col_name] = req_score
                transparency_cols.append(col_name)
                
                # Special handling for property_technical: also show the original property_technical rank if available
                if col == "tipologia_bene_immobile" and "property_technical_rank_position" in df_ranked.columns:
                    transparency_cols.append("property_technical_rank_position")
                
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