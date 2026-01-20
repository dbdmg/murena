"""
Script di simulazione completa della pipeline agentica.

Questo script esegue l'intera pipeline di analisi e salva i risultati
in un formato simile a gemini_responses.json.

Output:
- Crea una cartella in runs/test/ con tutti i file di output
- Stampa un riepilogo dei risultati

⚠️ ATTENZIONE: Questo script consuma token reali!

Uso:
    cd backend
    python tests/simulate_full_pipeline.py --query "il tuo prompt" --save

Esempio:
    python tests/simulate_full_pipeline.py --query "cerca immobili di 150mq vicino a piazza castello"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Setup path e dotenv
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")


def run_full_pipeline(
    query: str,
    dataset_key: str = "full",
    llm_limit: int = 5,
    save_results: bool = True,
) -> dict:
    """Esegue la pipeline completa e ritorna i risultati."""

    print("\n" + "=" * 70)
    print("🚀 SIMULAZIONE PIPELINE AGENTICA COMPLETA")
    print("=" * 70)
    print(f"📝 Query: {query}")
    print(f"📊 Dataset: {dataset_key}")
    print(f"🔢 LLM Limit: {llm_limit}")
    print("=" * 70)

    from app.services.analysis_service import AnalysisService
    import uuid

    service = AnalysisService()
    run_id = f"test_sim_{uuid.uuid4().hex[:8]}"

    print(f"🆔 Run ID: {run_id}")
    print("⏳ Esecuzione in corso...")
    print("-" * 70)

    start_time = datetime.now()

    # Esegui l'analisi
    result = asyncio.run(
        service.run_analysis(
            run_id=run_id,
            query=query,
            dataset_key=dataset_key,
            map_limit=100,
            llm_limit=llm_limit,
            analysis_mode="agent",
        )
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    print("-" * 70)
    print(f"✅ Completato in {elapsed:.1f} secondi\n")

    # Prepara output formattato
    buildings = result.get("buildings", [])
    gemini_responses = result.get("gemini_responses", {})
    location = result.get("location", [])

    print("📊 RISULTATI:")
    print(f"   ├─ Status: {result.get('status')}")
    print(f"   ├─ Buildings trovati: {len(buildings)}")
    print(f"   ├─ Location: {location}")
    print(f"   ├─ Steps agentici: {len(gemini_responses)}")
    print(f"   └─ Filtri applicati: {result.get('filters_applied', {})}")

    # Mostra un riepilogo dei Gemini Steps
    if gemini_responses:
        print("\n📋 STEPS AGENTICI:")
        for key, value in gemini_responses.items():
            if isinstance(value, dict):
                if "response" in value:
                    resp_preview = (
                        str(value["response"])[:100] + "..."
                        if len(str(value["response"])) > 100
                        else str(value["response"])
                    )
                    print(f"   ├─ {key}: {resp_preview}")
                elif "places" in value:
                    print(f"   ├─ {key}: {value['places']}")
                elif "sql_query" in value:
                    print(f"   ├─ {key}: SQL generato")
            else:
                print(f"   ├─ {key}: {type(value)}")

    # Mostra sample buildings
    if buildings:
        print(f"\n🏢 TOP 3 BUILDINGS (su {len(buildings)} totali):")
        for i, b in enumerate(buildings[:3]):
            b_dict = (
                b
                if isinstance(b, dict)
                else b.__dict__ if hasattr(b, "__dict__") else {}
            )
            print(f"   {i+1}. ID: {b_dict.get('id', 'N/A')}")
            print(f"      Indirizzo: {b_dict.get('indirizzo', 'N/A')}")
            print(
                f"      Superficie: {b_dict.get('superficie_di_riferimento_mq', 'N/A')} mq"
            )
            print(f"      Tipologia: {b_dict.get('tipologia_bene_immobile', 'N/A')}")
            if "evaluation_text" in b_dict:
                eval_preview = b_dict["evaluation_text"][:100] + "..."
                print(f"      Valutazione: {eval_preview}")
            print()

    # Salva risultati se richiesto
    if save_results:
        output_dir = (
            BACKEND_ROOT.parent
            / "runs"
            / "tests"
            / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_id}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Salva gemini_responses.json
        gemini_file = output_dir / "gemini_responses.json"
        with open(gemini_file, "w", encoding="utf-8") as f:
            json.dump(gemini_responses, f, indent=2, ensure_ascii=False, default=str)

        # Salva results.json
        results_file = output_dir / "results.json"
        results_data = {
            "run_id": run_id,
            "query": query,
            "dataset_key": dataset_key,
            "elapsed_seconds": elapsed,
            "status": result.get("status"),
            "buildings_count": len(buildings),
            "location": location,
            "filters_applied": result.get("filters_applied", {}),
        }
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False, default=str)

        # Salva buildings.json
        buildings_file = output_dir / "buildings.json"
        buildings_serializable = []
        for b in buildings:
            if hasattr(b, "__dict__"):
                buildings_serializable.append(b.__dict__)
            elif isinstance(b, dict):
                buildings_serializable.append(b)
        with open(buildings_file, "w", encoding="utf-8") as f:
            json.dump(
                buildings_serializable, f, indent=2, ensure_ascii=False, default=str
            )

        print(f"\n💾 RISULTATI SALVATI IN: {output_dir}")
        print(f"   ├─ gemini_responses.json")
        print(f"   ├─ results.json")
        print(f"   └─ buildings.json")

    print("\n" + "=" * 70)
    print("🎉 SIMULAZIONE COMPLETATA!")
    print("=" * 70)

    return result


def main():
    parser = argparse.ArgumentParser(description="Simula la pipeline agentica completa")
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default="cerca immobili di 150mq vicino a piazza castello adatti per uno studio dentistico",
        help="Query da analizzare",
    )
    parser.add_argument(
        "--dataset",
        "-d",
        type=str,
        default="full",
        choices=["full", "meta", "ape"],
        help="Dataset da usare",
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=5, help="Limite immobili da valutare con LLM"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Non salvare i risultati su file"
    )

    args = parser.parse_args()

    result = run_full_pipeline(
        query=args.query,
        dataset_key=args.dataset,
        llm_limit=args.limit,
        save_results=not args.no_save,
    )

    # Exit code basato sul risultato
    if result.get("status") == "completed":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
