"""
build_gemini_prompt.py

Assembla il prompt completo per il modello LLM includendo:
  - Le istruzioni di ragionamento a layer (gemini_pipeline_prompt.txt)
  - I metadati e statistiche del dataset
  - Il dataset IMMOBILI in formato CSV (colonne selezionate)

Può operare in due modalità:
  1. Solo assemblaggio  — salva il prompt su file o stdout (comportamento default).
  2. Invio al modello   — aggiunta di --send per spedire il prompt all'LLM scelto.

#   Esegue la pipeline in modalità baseline (default):
#     python scripts/build_gemini_prompt.py --query "Cerca un appartamento..."
#
#   Esegue in modalità multi-agente:
#     python scripts/build_gemini_prompt.py --query "..." --mode multiagent
#
#   Sceglie un modello specifico:
#     python scripts/build_gemini_prompt.py --query "..." --model gpt-oss-120b
#
#   Solo assemblaggio del testo del prompt (debug):
#     python scripts/build_gemini_prompt.py --query "..." --stdout --no-send
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import duckdb

# ---------------------------------------------------------------------------
# Path setup — aggiunto backend/ al sys.path per poter importare app.*
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

PARQUET_PATH = ROOT / "backend" / "data" / "FOLDER_META" / "immobili_with_meta_and_ape_full_cleaned.parquet"
PROMPT_TEMPLATE_PATH = ROOT / "docs" / "gemini_pipeline_prompt.txt"
METADATA_PATH = ROOT / "backend" / "app" / "data" / "db_metadata_lite.json"

# Colonne incluse nel CSV inline — bilancio tra completezza e dimensione token
DATASET_COLUMNS = [
    "id",
    "indirizzo",
    "numero_civico",
    "latitudine",
    "longitudine",
    "tipologia_bene_immobile",
    "superficie_di_riferimento_mq",
    "epoca_costruzione",
    "finalita",
    "numero_immobili_per_catasto",
    "vincolo_culturale_paesaggistico",
    "meta_immobile",
    "classe_energetica_ape",
    "epglnren_ape",
    "ape_score_total",
    "commerciale",
    "educazione",
    "mobilita",
    "sanita",
    "sport",
    "verde",
]

# Colonne numeriche per le quali calcolare statistiche distribuzione
NUMERIC_STAT_COLS = [
    "superficie_di_riferimento_mq",
    "epglnren_ape",
    "ape_score_total",
    "commerciale",
    "educazione",
    "mobilita",
    "sanita",
    "sport",
    "verde",
]

# Colonne categoriche per le quali elencare i valori distinti
CATEGORICAL_STAT_COLS = [
    "tipologia_bene_immobile",
    "classe_energetica_ape",
    "epoca_costruzione",
    "finalita",
    "vincolo_culturale_paesaggistico",
]


# ---------------------------------------------------------------------------
# Helpers — dataset
# ---------------------------------------------------------------------------

def load_dataset(path: Path) -> pd.DataFrame:
    """Carica il parquet e seleziona le colonne utili."""
    df = pd.read_parquet(path)
    available = [c for c in DATASET_COLUMNS if c in df.columns]
    return df[available].copy()


def compute_statistics(df: pd.DataFrame) -> dict:
    """Calcola statistiche di distribuzione per ogni colonna rilevante."""
    stats: dict = {"total_records": len(df)}

    for col in NUMERIC_STAT_COLS:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        stats[col] = {
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
            "mean": round(float(series.mean()), 2),
            "median": round(float(series.median()), 2),
            "percentiles": {
                "25%": round(float(series.quantile(0.25)), 2),
                "50%": round(float(series.quantile(0.50)), 2),
                "75%": round(float(series.quantile(0.75)), 2),
            },
        }

    for col in CATEGORICAL_STAT_COLS:
        if col not in df.columns:
            continue
        counts = df[col].value_counts(dropna=True).to_dict()
        stats[col] = {str(k): int(v) for k, v in sorted(counts.items(), key=lambda x: -x[1])}

    return stats


def dataset_to_csv_string(df: pd.DataFrame) -> str:
    """Restituisce il DataFrame come stringa CSV (senza indice)."""
    return df.to_csv(index=False)


def load_prompt_template(path: Path) -> str:
    """Legge il template del prompt dalle istruzioni di ragionamento."""
    return path.read_text(encoding="utf-8")


def load_metadata(path: Path) -> dict:
    """Carica i metadati del dataset (valori ammessi per colonne categoriche)."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def assemble_prompt(
    query: str,
    template: str,
    statistics: dict,
    metadata: dict,
    normative: str = "",
) -> str:
    """Assembla il prompt finale concatenando query, metadati, statistiche, normativa e istruzioni.
    Non include più il dataset CSV completo per risparmiare token e focalizzare il modello sulla generazione SQL.
    """
    stats_json = json.dumps(statistics, ensure_ascii=False, indent=2)
    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)

    sections = [
        "================================================================================",
        "QUERY UTENTE (INPUT)",
        "================================================================================",
        "",
        query.strip(),
        "",
        "================================================================================",
        "METADATI DATASET (Schema & Valori ammessi)",
        "================================================================================",
        "",
        meta_json,
        "",
        "================================================================================",
        "STATISTICHE DISTRIBUZIONE DATASET (Per soglie e percentili)",
        "================================================================================",
        "",
        stats_json,
        "",
        "================================================================================",
        "NORMATIVA DI RIFERIMENTO",
        "================================================================================",
        "",
        normative,
        "",
        "================================================================================",
        "ISTRUZIONI DI RAGIONAMENTO & OUTPUT FORMAT",
        "================================================================================",
        "",
        template.strip(),
        "",
    ]

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Helper — invio al modello
# ---------------------------------------------------------------------------

def call_llm(prompt: str, model_key: str) -> str:
    """Invia il prompt al modello specificato e restituisce la risposta testuale.

    Configura settings tramite apply_model_config (stessa logica dei test script)
    e usa get_llm() per ottenere il client LangChain corretto.

    Args:
        prompt: Testo del prompt completo da inviare.
        model_key: Chiave in MODEL_OPTIONS (es. 'gpt-5-nano', 'gpt-oss-120b').

    Returns:
        Risposta testuale del modello.

    Raises:
        ValueError: Se model_key non è registrato in MODEL_OPTIONS.
        RuntimeError: Se la chiamata al modello fallisce.
    """
    from dotenv import load_dotenv
    load_dotenv(BACKEND_ROOT / ".env")

    from app.core.config import settings
    from tests.model_config import apply_model_config
    from app.services.llm.langchain_client import get_llm
    from langchain_core.messages import HumanMessage

    apply_model_config(settings, model_key)

    cfg_model = settings.OPENAI_MODEL_FAST
    cfg_base = settings.OPENAI_API_BASE or "default OpenAI"
    print(f"[MODEL]  {model_key} -> {cfg_model}  (base_url: {cfg_base})", file=sys.stderr)

    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])

    if hasattr(response, "content"):
        return response.content
    return str(response)


# ---------------------------------------------------------------------------
# Pipeline Execution — "Il resto della pipeline"
# ---------------------------------------------------------------------------

def run_pipeline(query: str, df: pd.DataFrame, dataset_path: Path, metadata: dict, model_key: Optional[str] = None, mode: str = "baseline") -> Dict[str, Any]:
    """Esegue la pipeline architetturale sfruttando GraphOrchestratorAgent con il setup desiderato."""
    from app.services.llm.agents.graph_agent import GraphOrchestratorAgent
    from app.services.analysis.executor import execute_sql_query
    
    if model_key:
        from app.core.config import settings
        from tests.model_config import apply_model_config
        apply_model_config(settings, model_key)
        
    print(f"[MODE]   Esecuzione in modalità {mode.upper()} ({model_key or 'default model'})...", file=sys.stderr)
    
    # Generiamo un mini schema per l'agente
    db_schema = {col: {"type": str(df[col].dtype)} for col in df.columns}
    
    # Pass architecture flag (baseline or multiagent) to the orchestrator
    agent = GraphOrchestratorAgent(execute_sql_fn=execute_sql_query, architecture=mode)
    result = agent.run(
        query=query,
        dataset_key="script_test",
        base_dataset=df,
        db_schema=db_schema,
        dataset_path=str(dataset_path),
        use_data_knowledge=True
    )
    
    return {
        "analysis_plan": result.gemini_responses,
        "results_count": len(result.map_df) if result.map_df is not None else 0,
        "rankings": json.loads(result.map_df.head(20).to_json(orient="records")) if result.map_df is not None and not result.map_df.empty else [],
        "evaluations": [
            ev.model_dump() if hasattr(ev, "model_dump") else ev.dict() if hasattr(ev, "dict") else ev 
            for ev in getattr(result.context, "evaluation_results", [])
        ],
        "sql": result.sql_query,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    # Import lazily: lo script resta usabile senza il venv backend
    # quando --send non è specificato.
    try:
        from tests.model_config import MODEL_CHOICES
    except ImportError:
        MODEL_CHOICES = []

    parser = argparse.ArgumentParser(
        description="Assembla il prompt con dati e istruzioni, opzionalmente inviandolo a un LLM."
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Query utente in linguaggio naturale.",
    )
    parser.add_argument(
        "--mode",
        choices=["baseline", "multiagent"],
        default="baseline",
        help="Scegli l'architettura: 'baseline' (prompt unificato singolo) o 'multiagent' (Grafo LangGraph).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path di output per il risultato (JSON) o il prompt (TXT).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Stampa il prompt su stdout invece di scriverlo su file.",
    )
    parser.add_argument(
        "--model",
        choices=MODEL_CHOICES if MODEL_CHOICES else None,
        default="gpt-5-nano",
        metavar="MODEL",
        help=(
            "Chiave del modello da usare. "
            f"Di default 'gpt-5-nano'. Opzioni: {', '.join(MODEL_CHOICES) if MODEL_CHOICES else 'vedi model_config.py'}."
        ),
    )
    parser.add_argument(
        "--send",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Invia il prompt al modello e stampa la risposta (default: True).",
    )
    args = parser.parse_args()

    # Se l'utente specifica un output o stdout e non ha forzato --send, di default non eseguire?
    # No, manteniamo send=True a meno che non si dica --no-send.

    if args.mode == "baseline":
        if args.send and not args.model:
            parser.error("L'esecuzione in modalità baseline richiede --model <chiave_modello>.")
        if not args.send and not args.output and not args.stdout:
            # Se non c'è né output né modello, di default mostriamo a video il prompt?
            # Oppure mettiamo un modello di default.
            args.stdout = True

    # Carica componenti base
    df = load_dataset(PARQUET_PATH)
    metadata = load_metadata(METADATA_PATH)

    if args.send or args.mode == "multiagent":
        final_output = run_pipeline(
            query=args.query,
            df=df,
            dataset_path=PARQUET_PATH,
            metadata=metadata,
            model_key=args.model,
            mode=args.mode
        )
        
        output_json = json.dumps(final_output, indent=2, ensure_ascii=False)
        
        # Stampa sempre a video per feedback immediato
        print("\n" + "=" * 80)
        print(f"OUTPUT FINALE PIPELINE ({args.mode.upper()})")
        print("=" * 80)
        print(output_json)

        # Se specificato --output, salva il JSON dei risultati
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_json, encoding="utf-8")
            size_kb = round(len(output_json.encode("utf-8")) / 1024, 2)
            print(f"\n[SAVE] Risultati salvati in: {out_path} ({size_kb} KB)", file=sys.stderr)
            
        return

    # LOGICA SOLO ASSEMBLAGGIO (per debug offline prompt)
    statistics = compute_statistics(df)
    template = load_prompt_template(PROMPT_TEMPLATE_PATH)

    # Caricamento Normativa
    try:
        from app.services.llm.agents.normative_agent import load_normative_documents
        normativa_text, _, _ = load_normative_documents()
    except ImportError:
        normativa_text = "Nessun documento normativo disponibile (Errore import)."

    prompt = assemble_prompt(
        query=args.query,
        template=template,
        statistics=statistics,
        metadata=metadata,
        normative=normativa_text,
    )

    if args.stdout:
        sys.stdout.write(prompt)
    elif args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt, encoding="utf-8")
        size_mb = round(len(prompt.encode("utf-8")) / 1024 / 1024, 2)
        print(f"Prompt scritto in: {out_path}  ({size_mb} MB, {len(prompt.splitlines())} righe)")


if __name__ == "__main__":
    main()
