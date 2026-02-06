"""
mocks.py
========
Dummy responses for testing the UI/UX pipeline without burning tokens.
"""

from app.services.llm.agents.schema import (
    TypologyAgentResult,
    Place,
    LocationAgentResult,
    NeedsMetricPlan,
    DatasetStrategy,
    ApeUsagePlan,
    MetricDefinition,
    EvaluationAgentResponse,
    EvaluationResult,
    PromptRecord,
)

import json

# Mock Typology
MOCK_TYPOLOGY = TypologyAgentResult(
    raw_text=json.dumps({"typologies": ["Ufficio", "Caserma"]}, ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
)

# Mock Location (Rome center)
MOCK_LOCATION = LocationAgentResult(
    raw_text=json.dumps({"places": [{"name": "Roma Centro", "city": "Roma", "lat": 41.9028, "lon": 12.4964}]}, ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
)

# Mock Strategy
MOCK_STRATEGY = NeedsMetricPlan(
    summary="Strategia simulata per test UI/UX.",
    metrics=[
        {"name": "Prezzo", "goal": "Basso", "weight": 0.8},
        {"name": "Stato", "goal": "Ottimo", "weight": 0.6},
    ],
    dataset_strategy={
        "filters": ["stato_conservazione = 'OTT'", "prezzo < 500000"],
        "sort_by": "prezzo ASC",
        "top_k": 50,
    },
    ape_strategy={"use_ape": True, "strategy": "Preferire classe A o B"},
    prompt=PromptRecord(system="Mock", user="Mock"),
    raw_text="Mock strategy raw text",
)

# Mock SQL Query
MOCK_SQL_QUERY = "SELECT * FROM IMMOBILI LIMIT 10"

# Mock Evaluation Results
MOCK_EVALUATION = EvaluationAgentResponse(
    raw_text=json.dumps([
        {
            "id": 12345,
            "evaluation_text": "Ottimo immobile simulato per test.",
            "final_ranking_score": 95,
            "pros": ["Economico", "Centrale", "Ristrutturato"],
            "cons": ["Piano alto senza ascensore"],
        },
        {
            "id": 67890,
            "evaluation_text": "Buona alternativa simulata.",
            "final_ranking_score": 88,
            "pros": ["Ampio", "Luminoso"],
            "cons": ["Da ristrutturare"],
        },
    ], ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
)

# Mock Broker Summary
MOCK_BROKER_SUMMARY = """
**Executive Summary (Simulazione)**

L'analisi dei candidati evidenzia l'immobile **ID 12345** come scelta primaria.
Nonostante l'assenza di ascensore, la posizione centrale e il costo contenuto lo rendono ideale per l'uso ufficio richiesto.

L'alternativa **ID 67890** offre più spazio ma richiede investimenti significativi per la ristrutturazione.

**Raccomandazione:** Procedere con ID 12345 se il budget è vincolante.
"""
