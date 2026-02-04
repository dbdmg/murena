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
        if file_path.is_file() and file_path.suffix.lower() in [".txt", ".md", ".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
            try:
                if file_path.suffix.lower() in [".txt", ".md"]:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        documents.append(f"--- Documento: {file_path.name} ---\n{content}\n")
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
            return self._run_ranking(**kwargs)
        else:
            raise ValueError(f"Modalità '{mode}' non supportata dal NormativeAgent.")

    def _run_filtering(self, query: str, available_columns: List[str] = None, statistics: dict = None) -> NormativeAgentResult:
        if USE_MOCK_NORMATIVE_AGENT:
            # ... (mock stays mostly same but could include stats if needed)
            mock_json = {
                "found": True,
                "requisiti": [
                    {
                        "categoria": "destinazione_uso",
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

        prompt_inputs = {
            "query": query, 
            "normative_documents": normative_docs,
            "available_columns": columns_str,
            "statistics": stats_str
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

    def _run_ranking(self, *, df: pd.DataFrame, requirements: List[Dict[str, Any]]) -> pd.DataFrame:
        """Modalità ranking: calcolo score deterministico 0-100 basato sui requisiti normativi."""
        if df is None or df.empty or not requirements:
            if df is not None:
                df["normative_score"] = 0
            return df

        df_ranked = df.copy()
        
        total_scores = pd.Series(0.0, index=df_ranked.index)
        valid_req_count = 0

        for req in requirements:
            col = req.get("colonna_target")
            target_val = req.get("valore")
            op = str(req.get("operatore", ">=")).upper()

            if not col or col not in df_ranked.columns or target_val is None:
                continue

            valid_req_count += 1
            
            # Gestione tipi numerici vs categorici
            if op in [">=", "<=", "=="] and isinstance(target_val, (int, float)):
                vals = pd.to_numeric(df_ranked[col], errors="coerce").fillna(0)
                target_num = float(target_val)
                
                if op == ">=":
                    max_val = vals.max()
                    if max_val <= target_num:
                        req_score = (vals / (target_num + 1e-6) * 100).clip(0, 100)
                    else:
                        req_score = np.where(
                            vals >= target_num,
                            50 + 50 * (vals - target_num) / (max_val - target_num + 1e-6),
                            50 * (vals / (target_num + 1e-6))
                        )
                elif op == "<=":
                    min_val = vals.min()
                    if min_val >= target_num:
                        req_score = (target_num / (vals + 1e-6) * 100).clip(0, 100)
                    else:
                        req_score = np.where(
                            vals <= target_num,
                            50 + 50 * (target_num - vals) / (target_num - min_val + 1e-6),
                            50 * (target_num / (vals + 1e-6))
                        )
                else: # ==
                    diff = np.abs(vals - target_num)
                    req_score = (100 - (diff / (target_num + 1e-6) * 100)).clip(0, 100)
            
            else:
                # Gestione categorica / stringhe
                vals = df_ranked[col].astype(str).str.lower().str.strip()
                target_str = str(target_val).lower().strip()
                
                if op == "==":
                    req_score = (vals == target_str).astype(float) * 100
                elif op == "LIKE":
                    req_score = vals.str.contains(target_str, na=False).astype(float) * 100
                elif op == "IN":
                    # Se target_val è una lista o stringa separata da virgole
                    if isinstance(target_val, str):
                        target_list = [v.lower().strip() for v in target_val.split(",")]
                    elif isinstance(target_val, list):
                        target_list = [str(v).lower().strip() for v in target_val]
                    else:
                        target_list = [target_str]
                    req_score = vals.isin(target_list).astype(float) * 100
                else:
                    # Fallback per operatori non supportati su stringhe
                    req_score = (vals == target_str).astype(float) * 100
                
            total_scores += req_score

        if valid_req_count > 0:
            df_ranked["normative_score"] = (total_scores / valid_req_count).round(1)
        else:
            df_ranked["normative_score"] = 0.0

        return df_ranked