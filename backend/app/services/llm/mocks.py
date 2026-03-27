"""
mocks.py
========
Dummy responses for testing the UI/UX pipeline without burning tokens.
"""

from app.services.llm.agents.schema import (
    BuildingAgentResult,
    Place,
    LocationAgentResult,
    EvaluationAgentResponse,
    EvaluationResult,
    PromptRecord,
)

import json

# Mock Building Result
MOCK_BUILDING = BuildingAgentResult(
    raw_text=json.dumps({"typologies": ["Office", "Barracks"]}, ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
)

# Mock Location (Rome center)
MOCK_LOCATION = LocationAgentResult(
    raw_text=json.dumps({"places": [{"name": "Rome Center", "city": "Rome", "lat": 41.9028, "lon": 12.4964}]}, ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
)

# Mock SQL Query
MOCK_SQL_QUERY = "SELECT * FROM IMMOBILI LIMIT 10"

# Mock Evaluation Results
MOCK_EVALUATION = EvaluationAgentResponse(
    raw_text=json.dumps([
        {
            "id": 12345,
            "evaluation_text": "Excellent simulated property for testing.",
            "final_ranking_score": 95,
            "pros": ["Affordable", "Central", "Renovated"],
            "cons": ["High floor without elevator"],
        },
        {
            "id": 67890,
            "evaluation_text": "Good simulated alternative.",
            "final_ranking_score": 88,
            "pros": ["Spacious", "Bright"],
            "cons": ["Needs renovation"],
        },
    ], ensure_ascii=False),
    prompt=PromptRecord(system="Mock", user="Mock"),
)

# Mock Broker Summary
MOCK_BROKER_SUMMARY = """
**Executive Summary (Simulation)**

The analysis of candidates highlights property **ID 12345** as the primary choice.
Despite the absence of an elevator, the central location and low cost make it ideal for the requested office use.

The alternative **ID 67890** offers more space but requires significant investment for renovation.

**Recommendation:** Proceed with ID 12345 if the budget is a constraint.
"""
