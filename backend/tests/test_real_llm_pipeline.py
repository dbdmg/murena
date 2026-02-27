"""
Test per la pipeline agentica REALE con modelli LLM veri.

 ATTENZIONE: Questi test consumano token reali!
 NON vengono eseguiti automaticamente nella suite pytest normale.

Per eseguirli, usa UNA delle seguenti opzioni:

1. Con variabile d'ambiente (RACCOMANDATO):
   $env:RUN_REAL_LLM_TESTS="1"; python -m pytest tests/test_real_llm_pipeline.py -v -s

2. Direttamente come script Python:
   python tests/test_real_llm_pipeline.py

3. Con marker pytest esplicito:
   python -m pytest -m "real_llm" tests/test_real_llm_pipeline.py -v -s

Il test verifica:
- Connessione alle API Gemini/OpenAI
- Inizializzazione del GraphOrchestratorAgent
- Esecuzione di una query semplice
- Ritorno di risultati validi
"""

from __future__ import annotations

import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path

# =============================================================================
# SETUP PATH E ENVIRONMENT (necessario per esecuzione diretta come script)
# =============================================================================
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Carica .env dal backend
from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

import pytest


# =============================================================================
# PROTEZIONE ANTI-ESECUZIONE ACCIDENTALE
# =============================================================================
# Questi test NON vengono mai eseguiti a meno che:
# 1. La variabile RUN_REAL_LLM_TESTS sia impostata a "1", "true", o "yes"
# 2. Il file venga eseguito direttamente come script Python
# =============================================================================


def should_run_real_llm_tests() -> bool:
    """Determina se eseguire i test reali con LLM.

    Returns:
        True solo se esplicitamente abilitato via env var o esecuzione diretta.
    """
    # Check variabile d'ambiente
    if os.getenv("RUN_REAL_LLM_TESTS", "").lower() in ("1", "true", "yes"):
        return True
    return False


# Marker per escludere dalla suite normale + skip condizionale
# Il marker "real_llm" permette: pytest -m "not real_llm" per escludere esplicitamente
real_llm_test = pytest.mark.real_llm

# Skip automatico se il flag non è attivo
skip_if_no_real_llm = pytest.mark.skipif(
    not should_run_real_llm_tests(),
    reason=" Test LLM reale SKIPPATO (usa RUN_REAL_LLM_TESTS=1 per abilitare)",
)


@real_llm_test
@skip_if_no_real_llm
def test_api_keys_configured():
    """Verifica che le API keys siano configurate."""
    print("\n" + "=" * 60)
    print(" Verifica API Keys")
    print("=" * 60)

    gemini_key = os.getenv("GEMINI_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    assert gemini_key, "GEMINI_KEY non configurata nel .env"
    print(f" GEMINI_KEY: {gemini_key[:10]}...{gemini_key[-4:]}")

    # OpenAI è opzionale per alcuni agenti
    if openai_key:
        print(f" OPENAI_API_KEY: {openai_key[:10]}...{openai_key[-4:]}")
    else:
        print(
            " OPENAI_API_KEY non configurata (alcuni agenti potrebbero non funzionare)"
        )


@real_llm_test
@skip_if_no_real_llm
def test_langchain_client_gemini():
    """Verifica che il client Gemini funzioni."""
    print("\n" + "=" * 60)
    print(" Test LangChain Client")
    print("=" * 60)

    from app.services.llm.langchain_client import get_llm

    llm = get_llm()
    assert llm is not None, "LLM client è None"
    print(f" LLM client inizializzato: {type(llm).__name__}")

    # Test semplice invocazione
    response = llm.invoke("Rispondi solo con 'OK' senza altro testo.")
    content = response.content if hasattr(response, "content") else str(response)
    print(f" Risposta ricevuta: {content[:50]}...")
    assert content, "Risposta vuota dal modello"


@real_llm_test
@skip_if_no_real_llm
def test_graph_agent_initialization():
    """Verifica che il GraphOrchestratorAgent si inizializzi correttamente."""
    print("\n" + "=" * 60)
    print(" Test Inizializzazione GraphOrchestratorAgent")
    print("=" * 60)

    from app.services.llm.agents.graph_agent import GraphOrchestratorAgent
    from app.services.analysis.executor import execute_sql_query

    agent = GraphOrchestratorAgent(
        analysis_mode="agent",
        execute_sql_fn=execute_sql_query,
    )
    assert agent is not None, "Agent è None"
    print(f" GraphOrchestratorAgent inizializzato")
    print(f"   Mode: {agent.analysis_mode}")


@real_llm_test
@skip_if_no_real_llm
def test_full_analysis_pipeline():
    """Test completo della pipeline di analisi con LLM reali.

    NOTA: Questo test consuma token significativi e potrebbe richiedere 30-60 secondi.
    """
    print("\n" + "=" * 60)
    print(" Test Pipeline Completa di Analisi")
    print("=" * 60)

    from app.services.analysis_service import AnalysisService
    from app.models.responses import BuildingResponse
    import uuid

    service = AnalysisService()
    run_id = f"test_real_{uuid.uuid4().hex[:8]}"

    # Query semplice per test veloce
    test_query = "Appartamenti a Torino centro con 2 camere"

    print(f" Query: {test_query}")
    print(f" Run ID: {run_id}")
    print(" Esecuzione in corso (può richiedere 30-60 secondi)...")

    start_time = datetime.now()

    # Esegui l'analisi
    results = asyncio.run(
        service.run_analysis(
            run_id=run_id,
            query=test_query,
            dataset_key="full",
            map_limit=50,  # Limitato per test veloci
            llm_limit=5,  # Limitato per test veloci
            analysis_mode="agent",
        )
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n Analisi completata in {elapsed:.1f} secondi")
    print(f"   Status: {results.get('status')}")
    print(f"   Buildings trovati: {len(results.get('buildings', []))}")
    print(f"   Location: {results.get('location')}")

    if results.get("broker_summary"):
        summary = results["broker_summary"]
        print(
            f"   Broker Summary: {summary[:200]}..."
            if len(summary) > 200
            else f"   Broker Summary: {summary}"
        )

    # Verifica risultati
    assert (
        results.get("status") == "completed"
    ), f"Status non è 'completed': {results.get('status')}"
    assert results.get("run_id") == run_id, "Run ID non corrisponde"

    # Verifica che ci sia almeno qualche risultato o info utile
    buildings = results.get("buildings", [])
    location = results.get("location")
    gemini_responses = results.get("gemini_responses", {})

    print("\n Dettagli Risultati:")
    print(f"   ├─ Buildings: {len(buildings)}")
    print(f"   ├─ Location data: {'' if location else ''}")
    print(f"   ├─ Gemini responses: {len(gemini_responses)} steps")
    print(f"   └─ Filters applied: {results.get('filters_applied', {})}")

    # Almeno uno dei risultati deve essere presente per un test valido
    has_results = len(buildings) > 0 or location or len(gemini_responses) > 0
    assert has_results, "Nessun risultato significativo dalla pipeline"

    print("\n Pipeline agentica reale funzionante!")


@real_llm_test
@skip_if_no_real_llm
def test_single_agent_location():
    """Test singolo del Location Agent."""
    print("\n" + "=" * 60)
    print(" Test Location Agent")
    print("=" * 60)

    from app.services.llm.agents.location_agent import LocationAgent

    agent = LocationAgent()
    # NOTA: run() richiede query come keyword argument (def run(self, *, query))
    result = agent.run(query="Appartamenti vicino al Politecnico di Torino")

    print(f" Location Agent response:")
    print(
        f"   Raw: {result.raw_text[:100]}..."
        if len(result.raw_text) > 100
        else f"   Raw: {result.raw_text}"
    )
    print(f"   Places: {result.places}")

    assert result.places is not None, "places è None"
    assert len(result.places) > 0, f"Lista posti vuota. Raw response: {result.raw_text}"

    # Verifica che Torino sia riconosciuto (può essere nel name o city)
    found_torino = False
    for p in result.places:
        name_lower = (p.name or "").lower()
        city_lower = (p.city or "").lower()
        if (
            "torino" in name_lower
            or "torino" in city_lower
            or "politecnico" in name_lower
        ):
            found_torino = True
            break

    assert (
        found_torino
    ), f"Torino/Politecnico non identificato nei places: {result.places}"

    print(f" Location correttamente identificata: {result.places[0]}")


def run_all_tests():
    """Esegue tutti i test in sequenza quando chiamato direttamente."""
    print("\n" + "=" * 60)
    print(" TEST PIPELINE AGENTICA REALE")
    print("=" * 60)
    print("  ATTENZIONE: Questi test consumano token reali!")
    print("=" * 60)

    # Forza il flag a True quando eseguito come main
    os.environ["RUN_REAL_LLM_TESTS"] = "1"

    tests = [
        ("API Keys Configurate", test_api_keys_configured),
        ("LangChain Client Gemini", test_langchain_client_gemini),
        ("Graph Agent Init", test_graph_agent_initialization),
        ("Location Agent", test_single_agent_location),
        ("Pipeline Completa", test_full_analysis_pipeline),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
            print(f"\n {name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"\n {name}: FAILED - {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Risultato: {passed}/{len(tests)} test passati")
    print("=" * 60)

    if failed > 0:
        print(" Alcuni test sono falliti!")
        sys.exit(1)
    else:
        print(" Tutti i test passati!")
        print("\n La pipeline agentica reale funziona correttamente!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
