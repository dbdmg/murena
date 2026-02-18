"""
mocks.py
========
Dummy responses for testing the UI/UX pipeline without burning tokens.
"""

from app.services.llm.agents.schema import (
    PropertyTechnicalAgentResult,
    Place,
    LocationAgentResult,
    EvaluationAgentResponse,
    EvaluationResult,
    PromptRecord,
    RelaxationAgentResult,
    RelaxationProposal,
)

import json

# Mock Property Technical
MOCK_PROPERTY_TECHNICAL = PropertyTechnicalAgentResult(
    raw_text=json.dumps({"typologies": ["Ufficio", "Caserma"]}, ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
)

# Mock Location (Rome center)
MOCK_LOCATION = LocationAgentResult(
    raw_text=json.dumps({"places": [{"name": "Roma Centro", "city": "Roma", "lat": 41.9028, "lon": 12.4964}]}, ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
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

# Mock Relaxation
MOCK_RELAXATION = RelaxationAgentResult(
    raw_text=json.dumps([
        {
            "condizione_iniziale": "superficie_mq >= 100",
            "condizione_relaxed": "superficie_mq >= 80",
            "strategia": "Allargamento intervallo superficie",
            "motivazione": "Il dataset mostra pochi immobili sopra i 100mq, 80mq è una soglia vicina e più popolata.",
            "livello_rilassamento": "low"
        }
    ], ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
    proposals=[
        RelaxationProposal(
            condizione_iniziale="superficie_mq >= 100",
            condizione_relaxed="superficie_mq >= 80",
            strategia="Allargamento intervallo superficie",
            motivazione="Il dataset mostra pochi immobili sopra i 100mq, 80mq è una soglia vicina e più popolata.",
            livello_rilassamento="low"
        )
    ]
)
