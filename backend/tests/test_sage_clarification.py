"""Focused tests for the isolated SAGE-inspired clarification layer."""

import json
import os
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from pydantic import BaseModel

from app.database.models import Base, ClarificationSession
from app.core.config import settings
from app.models.requests import AnalysisRequest
from app.models.responses import ClarificationResponse
from app.api.v1.endpoints import analysis as analysis_endpoint
from app.services.sage_clarification.service import SageClarifier
from app.services.sage_clarification.prompt_loader import render_prompt
from app.services.llm.codex_exec import CodexExecChatModel
from app.services.llm.providers import build_chat_model
from app.services.sage_clarification.uncertainty import (
    evpi,
    normalized_beliefs,
    parameter_specificity,
    question_score,
)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, payload, answer_relation="consistent", rewritten_query="Rewritten search prompt.",
                 location_answer=None, answer_intent="REQUIREMENT", answer_evidence=None,
                 omission_responses=None):
        self.payload = payload
        self.answer_relation = answer_relation
        self.rewritten_query = rewritten_query
        self.answer_intent = answer_intent
        self.answer_evidence = answer_evidence
        self.omission_responses = list(omission_responses or [])
        self.location_answer = location_answer or {
            "intent": "REQUIREMENT", "city": "Torino", "evidence": "Torino",
            "selected_alternative": None,
        }
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if prompt.startswith("Rewrite this real-estate search request"):
            return FakeMessage(self.rewritten_query)
        if prompt.startswith("Resolve the user's answer to a question asking which city"):
            return FakeMessage(json.dumps(self.location_answer))
        if prompt.startswith("Classify the user's answer"):
            relation = self.answer_relation
            if isinstance(relation, list):
                relation = relation.pop(0) if relation else "unclear"
            return FakeMessage(json.dumps({
                "relation": relation,
                "intent": self.answer_intent,
                "evidence": self.answer_evidence,
            }))
        if prompt.startswith("Extract the user's answer to a grouped question"):
            response = self.omission_responses.pop(0) if self.omission_responses else {
                "intent": "NO_PREFERENCE", "evidence": "No preference", "updates": {},
            }
            return FakeMessage(json.dumps(response))
        return FakeMessage(json.dumps(self.payload))


class GroupAnswerLLM(FakeLLM):
    def __init__(self, payload, updates, answer_relation="consistent", rewritten_query="Rewritten search prompt.",
                 location_answer=None):
        super().__init__(payload, answer_relation, rewritten_query, location_answer)
        self.updates = updates
        self.requirement_update_used = False

    def invoke(self, prompt):
        if prompt.startswith("Extract the user's answer to a grouped question"):
            if not self.requirement_update_used:
                self.requirement_update_used = True
                return FakeMessage(json.dumps({"intent": "REQUIREMENT", "updates": self.updates}))
            return FakeMessage(json.dumps({
                "intent": "NO_PREFERENCE", "evidence": "No preference", "updates": {},
            }))
        return super().invoke(prompt)


def _payload(*, location_status="NOT_REQUESTED", questions=None):
    dimensions = {
        key: {"value": None, "status": "NOT_REQUESTED", "evidence": None, "alternatives": []}
        for key in ("I", "D", "L", "Cb", "Ce", "Cp")
    }
    if location_status == "SPECIFIED":
        dimensions["L"] = {"value": "Turin", "status": "SPECIFIED", "evidence": "in Turin", "alternatives": []}
    elif location_status in {"AMBIGUOUS", "MISSING_CRITICAL"}:
        dimensions["L"] = {"value": None, "status": location_status, "evidence": "near the university", "alternatives": []}
    return {"dimensions": dimensions, "questions": questions or []}


def _payload_with_resolved_others(*, location_status, questions=None):
    payload = _payload(location_status=location_status, questions=questions)
    for key in ("I", "D", "Cb", "Ce", "Cp"):
        payload["dimensions"][key] = {
            "value": f"explicit {key}", "status": "SPECIFIED",
            "evidence": f"explicit {key}", "alternatives": [],
        }
    return payload


def _question(alternatives=None, blocking=True):
    return {
        "question": "Which university do you mean?",
        "target_dimensions": ["L"],
        "target_parameters": ["university"],
        "reason": "The reference has multiple interpretations.",
        "blocking": blocking,
        "alternatives": (
            alternatives if alternatives is not None
            else ["Politecnico di Torino", "Università di Torino"]
        ),
    }


def _db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_structured_specificity_and_normalization():
    assert parameter_specificity(specified=True, domain_size=4) == 1.0
    assert parameter_specificity(specified=False, domain_size=4) == 0.25
    assert parameter_specificity(specified=False, domain_size=None) == 1e-4
    assert normalized_beliefs({"a": 2, "b": 2}) == {"a": 0.5, "b": 0.5}


def test_sage_prompts_are_loaded_and_rendered_from_markdown():
    prompt = render_prompt(
        "query_parser", OUTPUT_SCHEMA='{"dimensions":{}}',
        LANGUAGE="Italian", QUERY='"Uffici a Torino"',
    )
    assert "offices/uffici" in prompt
    assert '"Uffici a Torino"' in prompt
    assert "{{" not in prompt

    answer_prompt = render_prompt(
        "omission_answer", UPDATE_SCHEMA='{"I":{}}',
        DIMENSION_LABELS='{"I":"tipologia"}', QUESTION='"Che tipologia?"',
        ANSWER='"Uffici"',
    )
    assert '"updates": {"I":{}}' in answer_prompt
    assert "{{" not in answer_prompt

    consistency_prompt = render_prompt(
        "answer_consistency", ORIGINAL_QUERY='"offices"',
        CONFIRMED_CLARIFICATIONS="[]", TARGET_DIMENSIONS='["D"]',
        DIMENSION_LABELS='{"D":"intended use"}', QUESTION='"intended use?"',
        ANSWER='"student housing"',
    )
    assert "current physical typology" in consistency_prompt
    assert 'Target dimensions: ["D"]' in consistency_prompt
    assert "{{" not in consistency_prompt

    location_prompt = render_prompt(
        "location_answer", PLACE='"Porta Nuova"', ORIGINAL_QUERY='"near Porta Nuova"',
        QUESTION='"Which city?"', ANSWER='"Torino"',
        ALTERNATIVES='["Torino", "Milano"]',
    )
    assert '"Torino"' in location_prompt
    assert '"Milano"' in location_prompt
    assert "Do not infer a city" in location_prompt
    assert "{{" not in location_prompt

    rewrite_prompt = render_prompt(
        "query_rewriter", ORIGINAL_QUERY='"Uffici vicino a Porta Nuova"',
        CLARIFICATIONS='[{"answer":"Torino"}]',
    )
    assert "genuine rewrite" in rewrite_prompt
    assert '"Torino"' in rewrite_prompt
    assert "Return only the rewritten prompt as plain text" in rewrite_prompt
    assert "{{" not in rewrite_prompt


def test_codex_exec_adapter_uses_requested_model_and_disables_tools():
    event = json.dumps({
        "type": "item.completed",
        "item": {"type": "agent_message", "text": '{"ok":true}'},
    })
    with patch("app.services.llm.codex_exec.shutil.which", return_value="/usr/bin/codex"), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "must-not-be-forwarded"}), \
         patch("app.services.llm.codex_exec.subprocess.run", return_value=SimpleNamespace(
             returncode=0, stdout=event, stderr=""
         )) as run:
        response = CodexExecChatModel(model_name="gpt-6-luna").invoke("synthetic query")

    assert response.content == '{"ok":true}'
    args, kwargs = run.call_args
    command = args[0]
    assert command[command.index("--model") + 1] == "gpt-6-luna"
    assert "--disable" in command and "shell_tool" in command
    assert "--disable" in command and "multi_agent" in command
    assert "--disable" in command and "apps" in command
    assert "synthetic query" in kwargs["input"]
    assert "OPENAI_API_KEY" not in kwargs["env"]
    assert kwargs["timeout"] == settings.CODEX_TIMEOUT_SECONDS


def test_codex_exec_adapter_fails_closed_without_final_message():
    with patch("app.services.llm.codex_exec.shutil.which", return_value="/usr/bin/codex"), \
         patch("app.services.llm.codex_exec.subprocess.run", return_value=SimpleNamespace(
             returncode=0, stdout='{"type":"turn.completed"}\n', stderr=""
         )):
        with unittest.TestCase().assertRaisesRegex(RuntimeError, "no LLM response"):
            CodexExecChatModel(model_name="gpt-6-luna").invoke("synthetic query")


def test_codex_provider_is_built_by_the_shared_provider_factory():
    model = build_chat_model(
        provider="codex_exec", model_name="gpt-6-luna", temperature=0.0
    )
    assert isinstance(model, CodexExecChatModel)
    assert model.reasoning_effort == "low"


def test_codex_structured_output_uses_schema_constrained_json():
    class TinyOutput(BaseModel):
        relation: str

    event = json.dumps({
        "type": "item.completed",
        "item": {"type": "agent_message", "text": '{"relation":"consistent"}'},
    })
    with patch("app.services.llm.codex_exec.shutil.which", return_value="/usr/bin/codex"), \
         patch("app.services.llm.codex_exec.subprocess.run", return_value=SimpleNamespace(
             returncode=0, stdout=event, stderr=""
         )) as run:
        result = CodexExecChatModel(model_name="gpt-6-luna").with_structured_output(
            TinyOutput, method="function_calling"
        ).invoke("Classify this answer")

    assert result == TinyOutput(relation="consistent")
    command = run.call_args.args[0]
    assert "--output-schema" in command


def test_codex_structured_output_falls_back_for_arbitrary_dict_fields():
    class DynamicOutput(BaseModel):
        requirements: list[dict[str, Any]]

    event = json.dumps({
        "type": "item.completed",
        "item": {"type": "agent_message", "text": '{"requirements":[{"operator":"gte"}]}'},
    })
    with patch("app.services.llm.codex_exec.shutil.which", return_value="/usr/bin/codex"), \
         patch("app.services.llm.codex_exec.subprocess.run", return_value=SimpleNamespace(
             returncode=0, stdout=event, stderr=""
         )) as run:
        result = CodexExecChatModel(model_name="gpt-6-luna").with_structured_output(
            DynamicOutput
        ).invoke("Extract a requirement")

    assert result.requirements == [{"operator": "gte"}]
    command = run.call_args.args[0]
    assert "--output-schema" not in command
    assert "Preserve arbitrary object keys" in run.call_args.kwargs["input"]


def test_evpi_resolved_partition_and_irrelevant_question():
    beliefs = {"a": 0.5, "b": 0.5}
    assert evpi(beliefs, {"a": "A", "b": "B"}) == 0.5
    assert evpi(beliefs, {"a": "same", "b": "same"}) == 0.0
    assert evpi(beliefs, {"a": "A", "b": "B"}) >= 0.0


def test_redundancy_cost_reduces_question_score():
    beliefs = {"a": 0.5, "b": 0.5}
    outcomes = {"a": "A", "b": "B"}
    first = question_score(beliefs, outcomes, redundancy_count=0, redundancy_lambda=0.5)
    repeated = question_score(beliefs, outcomes, redundancy_count=1, redundancy_lambda=0.5)
    assert first == (0.5, 0.5)
    assert repeated == (0.5, 0.0)


def test_fully_specified_is_ready_and_absent_dimensions_are_confirmed_one_at_a_time():
    db = _db()
    fully_specified = _payload(location_status="SPECIFIED")
    for dimension in ("I", "D", "Cb", "Ce", "Cp"):
        fully_specified["dimensions"][dimension] = {
            "value": f"explicit {dimension}", "status": "SPECIFIED",
            "evidence": f"explicit {dimension}", "alternatives": [],
        }
    ready = SageClarifier(llm=FakeLLM(fully_specified)).process(
        db=db, user_input="Find a building in Turin"
    )
    assert ready.status == "READY"
    assert ready.question is None

    absent_clarifier = SageClarifier(llm=FakeLLM(_payload()), max_turns=6)
    absent = absent_clarifier.process(
        db=db, user_input="Find a building in Turin"
    )
    assert absent.status == "ASK"
    assert "property type" in absent.question
    row = db.query(ClarificationSession).filter_by(session_id=absent.session_id).first()
    assert row.state["dimensions"]["Ce"]["status"] == "UNCONFIRMED_ABSENT"
    pending = absent_clarifier._select_question(row.state)
    assert pending["target_dimensions"] == ["I"]
    db.close()


def test_explicit_office_typology_is_not_asked_again():
    db = _db()
    payload = _payload()
    payload["dimensions"]["L"] = {
        "value": "Torino", "status": "SPECIFIED", "evidence": "Torino", "alternatives": [],
    }
    payload["dimensions"]["I"] = {
        "value": "uffici", "status": "SPECIFIED",
        "evidence": "Uffici", "alternatives": [],
    }
    payload["dimensions"]["Ce"] = {
        "value": "classe energetica alta", "status": "SPECIFIED",
        "evidence": "classe energetica alta", "alternatives": [],
    }
    result = SageClarifier(llm=FakeLLM(payload), max_turns=6).process(
        db=db, user_input="Uffici a Torino con classe energetica alta",
        language="it",
    )
    assert result.status == "ASK"
    assert "tipologia" not in result.question.lower()
    assert "destinazione d'uso" in result.question.lower()
    row = db.query(ClarificationSession).filter_by(session_id=result.session_id).first()
    assert row.state["dimensions"]["I"]["status"] == "SPECIFIED"
    assert row.state["dimensions"]["I"]["value"] == "uffici"
    db.close()


def test_explicit_qualitative_energy_requirement_is_not_asked_again():
    db = _db()
    query = "Uffici vicino a Porta Nuova con classe energetica alta"
    payload = _payload()
    payload["dimensions"]["I"] = {
        "value": "uffici", "status": "SPECIFIED", "evidence": "Uffici", "alternatives": [],
    }
    payload["dimensions"]["Ce"] = {
        "value": "classe energetica alta", "status": "SPECIFIED",
        "evidence": "classe energetica alta", "alternatives": [],
    }
    result = SageClarifier(llm=FakeLLM(payload), max_turns=6).process(
        db=db, user_input=query, language="it"
    )
    assert result.status == "ASK"
    assert "prestazioni energetiche" not in result.question.lower()
    row = db.query(ClarificationSession).filter_by(session_id=result.session_id).first()
    assert row.state["dimensions"]["Ce"]["status"] == "SPECIFIED"
    assert row.state["dimensions"]["Ce"]["value"] == "classe energetica alta"
    assert all("Ce" not in question["target_dimensions"]
               for question in row.state["questions"])
    db.close()


def test_named_porta_nuova_is_disambiguated_after_intended_use_answer():
    db = _db()
    payload = _payload()
    payload["dimensions"]["I"] = {
        "value": "uffici", "status": "SPECIFIED", "evidence": "Uffici", "alternatives": [],
    }
    payload["dimensions"]["Ce"] = {
        "value": "classe energetica alta", "status": "SPECIFIED",
        "evidence": "classe energetica alta", "alternatives": [],
    }
    payload["dimensions"]["L"] = {
        "value": "Porta Nuova", "status": "AMBIGUOUS",
        "evidence": "Porta Nuova", "alternatives": [],
    }
    payload["questions"] = [{
        **_question(alternatives=["Torino", "Milano"]),
        "question": "Porta Nuova potrebbe essere a Torino o Milano. Intendi una di queste o un'altra città?",
        "target_parameters": ["city"],
        "kind": "location_disambiguation",
    }]
    clarifier = SageClarifier(
        llm=GroupAnswerLLM(payload, {
            "D": {
                "status": "SPECIFIED", "value": "studentato",
                "evidence": "studentato",
            },
        }),
        max_turns=6,
    )
    query = "Uffici vicino a Porta Nuova con classe energetica alta"
    first = clarifier.process(db=db, user_input=query, language="it")
    assert first.status == "ASK"
    assert "torino o milano" in first.question.lower()
    assert "un'altra città" in first.question.lower()
    first_row = db.query(ClarificationSession).filter_by(session_id=first.session_id).first()
    pending_location = clarifier._select_question(first_row.state)
    assert pending_location["alternatives"] == ["Torino", "Milano"]
    city_beliefs, city_outcomes = clarifier._question_belief(pending_location)
    assert len(city_beliefs) == 3
    assert None in city_outcomes.values()  # EVPI includes the open "another city" response.

    second = clarifier.process(
        db=db, user_input=query, session_id=first.session_id,
        clarification_response="Torino",
    )
    assert second.status == "ASK"
    assert "destinazione d'uso" in second.question.lower()

    row = db.query(ClarificationSession).filter_by(session_id=first.session_id).first()
    assert row.state["dimensions"]["D"]["status"] == "UNCONFIRMED_ABSENT"
    assert row.state["dimensions"]["L"]["status"] == "SPECIFIED"
    assert row.state["dimensions"]["L"]["value"] == "Porta Nuova, Torino"

    third = clarifier.process(
        db=db, user_input=query, session_id=first.session_id,
        clarification_response="Voglio farci uno studentato",
    )
    assert third.status == "ASK"
    assert "vincoli edilizi" in third.question.lower()
    row = db.query(ClarificationSession).filter_by(session_id=first.session_id).first()
    assert row.state["dimensions"]["L"]["status"] == "SPECIFIED"
    assert row.state["dimensions"]["L"]["value"] == "Porta Nuova, Torino"
    assert row.state["dimensions"]["D"]["status"] == "SPECIFIED"
    assert row.state["dimensions"]["D"]["value"] == "studentato"
    db.close()


def test_grouped_omissions_allow_partial_answer_then_ready():
    db = _db()
    payload = _payload(location_status="SPECIFIED")
    answer_updates = {
        "I": {"status": "SPECIFIED", "value": "offices", "evidence": "Offices"},
    }
    clarifier = SageClarifier(
        llm=GroupAnswerLLM(payload, answer_updates, rewritten_query="Find offices near Turin."),
        max_turns=6,
    )
    first = clarifier.process(db=db, user_input="Find a building in Turin")
    assert first.status == "ASK"
    partial = clarifier.process(
        db=db, user_input="Find a building in Turin", session_id=first.session_id,
        clarification_response="Offices",
    )
    assert partial.status == "ASK"
    assert "intended use" in partial.question
    row = db.query(ClarificationSession).filter_by(session_id=first.session_id).first()
    assert row.state["dimensions"]["I"]["value"] == "offices"
    assert row.state["dimensions"]["D"]["status"] == "UNCONFIRMED_ABSENT"
    assert clarifier._select_question(row.state)["target_dimensions"] == ["D"]

    next_result = partial
    while next_result.status == "ASK":
        next_result = clarifier.process(
            db=db, user_input="Find a building in Turin", session_id=first.session_id,
            clarification_response="No preference",
        )
    final = next_result
    assert final.status == "READY"
    assert "offices" in final.refined_query
    assert "building constraints" not in final.refined_query
    db.close()


def test_explicit_no_preference_confirms_all_omitted_dimensions():
    db = _db()
    clarifier = SageClarifier(
        llm=FakeLLM(
            _payload(location_status="SPECIFIED"),
            rewritten_query="Find a building in Turin",
        ),
        max_turns=6,
    )
    first = clarifier.process(db=db, user_input="Find a building in Turin")
    assert first.status == "ASK"
    ready = first
    while ready.status == "ASK":
        ready = clarifier.process(
            db=db, user_input="Find a building in Turin", session_id=first.session_id,
            clarification_response="No preference",
        )
    assert ready.status == "READY"
    row = db.query(ClarificationSession).filter_by(session_id=first.session_id).first()
    assert all(row.state["dimensions"][key]["status"] == "NOT_REQUESTED"
               for key in ("I", "D", "Cb", "Ce", "Cp"))
    assert ready.refined_query == "Find a building in Turin"
    db.close()


def test_italian_not_interested_confirms_only_current_dimension():
    db = _db()
    clarifier = SageClarifier(llm=FakeLLM(
        _payload(location_status="SPECIFIED"),
        omission_responses=[{
            "intent": "NO_PREFERENCE", "evidence": "Non mi interessa", "updates": {},
        }],
    ), max_turns=6)
    first = clarifier.process(
        db=db, user_input="Cerco un immobile a Turin", language="it"
    )
    result = clarifier.process(
        db=db, user_input="Cerco un immobile a Turin", session_id=first.session_id,
        clarification_response="Non mi interessa",
    )
    row = db.query(ClarificationSession).filter_by(session_id=first.session_id).first()
    assert row.state["dimensions"]["I"]["status"] == "NOT_REQUESTED"
    assert result.status == "ASK"
    assert SageClarifier(llm=FakeLLM(_payload()))._select_question(row.state)["target_dimensions"] == ["D"]
    db.close()


def test_ambiguous_and_missing_critical_are_asked():
    db = _db()
    for status in ("AMBIGUOUS", "MISSING_CRITICAL"):
        result = SageClarifier(llm=FakeLLM(_payload_with_resolved_others(
            location_status=status, questions=[_question(alternatives=[])]
        ))).process(
            db=db, user_input="Find a building near the university"
        )
        assert result.status == "ASK"
        assert "university" in result.question
        row = db.query(ClarificationSession).filter_by(session_id=result.session_id).first()
        assert row.state["questions"][0]["alternatives"] == []
    db.close()


def test_answer_updates_state_and_refines_query():
    db = _db()
    llm = FakeLLM(
        _payload_with_resolved_others(location_status="AMBIGUOUS", questions=[_question()]),
        rewritten_query="Find a building near Politecnico di Torino.",
    )
    clarifier = SageClarifier(llm=llm)
    first = clarifier.process(db=db, user_input="Find a building near the university")
    ready = clarifier.process(
        db=db, user_input="Find a building near the university", session_id=first.session_id,
        clarification_response="Politecnico di Torino",
    )
    assert ready.status == "READY"
    assert ready.refined_query == "Find a building near Politecnico di Torino."
    rewrite_prompt = next(prompt for prompt in llm.prompts
                          if prompt.startswith("Rewrite this real-estate search request"))
    assert '"Find a building near the university"' in rewrite_prompt
    assert '"Politecnico di Torino"' in rewrite_prompt
    db.close()


def test_rewritten_query_is_natural_model_output_with_only_confirmed_details():
    llm = FakeLLM(
        {},
        rewritten_query=(
            "Trova uffici vicino a Porta Nuova, a Torino, da destinare a studentato, "
            "con classe energetica alta e vicino alle scuole."
        ),
    )
    clarifier = SageClarifier(llm=llm)
    refined = clarifier._refine({
        "language": "it",
        "original_query": "Uffici vicino a Porta Nuova con classe energetica alta",
        "clarifications": [
            {
                "question": "In quale città si trova Porta Nuova?",
                "text": "Torino",
                "target_dimensions": ["L"],
                "values": {"L": "Porta Nuova, Torino"},
            },
            {
                "question": "Qual è la destinazione d'uso?",
                "text": "Voglio farci uno studentato",
                "target_dimensions": ["D"],
                "values": {"D": "studentato"},
            },
            {
                "question": "Quali servizi di prossimità?",
                "text": "Vicino alle scuole",
                "target_dimensions": ["Cp"],
                "values": {"Cp": "Vicino alle scuole"},
            },
        ],
    })
    assert refined == llm.rewritten_query
    assert "l'utente ha specificato" not in refined
    rewrite_prompt = llm.prompts[-1]
    assert "examples from questions into requirements" in rewrite_prompt
    assert '"studentato"' in rewrite_prompt
    assert '"Vicino alle scuole"' in rewrite_prompt


def test_location_selection_can_resolve_reference_to_an_offered_option():
    clarifier = SageClarifier(llm=FakeLLM(
        {},
        location_answer={
            "intent": "REQUIREMENT", "city": "Torino", "evidence": "la prima",
            "selected_alternative": "Torino",
        },
    ))
    state = {
        "dimensions": {"L": {"value": "Porta Nuova"}},
        "original_query": "Uffici vicino a Porta Nuova",
    }
    question = {"question": "Torino o Milano?", "alternatives": ["Torino", "Milano"]}
    assert clarifier._interpret_location_answer(state, question, "La prima")["city"] == "Torino"


def test_unknown_answer_does_not_repeat_question_and_blocks():
    db = _db()
    clarifier = SageClarifier(llm=FakeLLM(
        _payload_with_resolved_others(location_status="MISSING_CRITICAL", questions=[_question()]),
        answer_intent="UNKNOWN", answer_evidence="I don't know",
    ))
    first = clarifier.process(db=db, user_input="Near the university")
    blocked = clarifier.process(
        db=db, user_input="Near the university", session_id=first.session_id,
        clarification_response="I don't know",
    )
    assert blocked.status == "BLOCKED"
    assert blocked.question is None
    db.close()


def test_nonblocking_ambiguity_does_not_prevent_readiness():
    db = _db()
    result = SageClarifier(llm=FakeLLM(_payload_with_resolved_others(
        location_status="AMBIGUOUS", questions=[_question(blocking=False)]
    ))).process(db=db, user_input="Broad search")
    assert result.status == "READY"
    db.close()


def test_rejected_candidates_without_replacement_are_blocked():
    db = _db()
    clarifier = SageClarifier(llm=FakeLLM(
        _payload_with_resolved_others(location_status="AMBIGUOUS", questions=[_question()]),
        answer_intent="REJECTED", answer_evidence="Neither",
    ))
    first = clarifier.process(db=db, user_input="Near a university")
    blocked = clarifier.process(
        db=db, user_input="Near a university", session_id=first.session_id,
        clarification_response="Neither",
    )
    assert blocked.status == "BLOCKED"
    db.close()


def test_contradictory_answer_is_blocked():
    db = _db()
    clarifier = SageClarifier(
        llm=FakeLLM(_payload_with_resolved_others(location_status="AMBIGUOUS", questions=[_question()]),
                    answer_relation="contradictory")
    )
    first = clarifier.process(db=db, user_input="Near a university")
    blocked = clarifier.process(
        db=db, user_input="Near a university", session_id=first.session_id,
        clarification_response="Politecnico di Torino, but no education proximity",
    )
    assert blocked.status == "BLOCKED"
    assert "conflicts" in blocked.message
    db.close()


def test_no_preference_resolves_to_optional_dimension_absence():
    db = _db()
    question = _question()
    question["kind"] = "location_disambiguation"
    clarifier = SageClarifier(llm=FakeLLM(
        _payload_with_resolved_others(location_status="AMBIGUOUS", questions=[question]),
        rewritten_query="Search without a geographic preference",
        location_answer={
            "intent": "NO_PREFERENCE", "city": None,
            "evidence": "Non mi interessa", "selected_alternative": None,
        },
    ))
    first = clarifier.process(db=db, user_input="Search near the university")
    ready = clarifier.process(
        db=db, user_input="Search near the university", session_id=first.session_id,
        clarification_response="Non mi interessa",
    )
    assert ready.status == "READY"
    assert ready.refined_query == "Search without a geographic preference"
    row = db.query(ClarificationSession).filter_by(session_id=first.session_id).first()
    assert row.state["dimensions"]["L"]["status"] == "NOT_REQUESTED"
    db.close()


def test_italian_query_gets_italian_location_question():
    db = _db()
    question = _question()
    question["question"] = "A quale università ti riferisci? Puoi indicarne il nome o la sede."
    result = SageClarifier(llm=FakeLLM(_payload(
        location_status="AMBIGUOUS", questions=[question]
    ))).process(db=db, user_input="Vicino all'università", language="it")
    assert result.status == "ASK"
    assert result.question == "A quale università ti riferisci? Puoi indicarne il nome o la sede."
    db.close()


def test_readiness_does_not_delegate_when_question_is_missing():
    db = _db()
    result = SageClarifier(llm=FakeLLM(_payload(location_status="MISSING_CRITICAL"))).process(
        db=db, user_input="Near the city center"
    )
    assert result.status == "BLOCKED"
    db.close()


class TestSageClarification(unittest.TestCase):
    """Expose the standalone checks to Python's built-in unittest runner."""

    def test_specificity(self):
        test_structured_specificity_and_normalization()

    def test_prompt_markdown_loading(self):
        test_sage_prompts_are_loaded_and_rendered_from_markdown()

    def test_codex_provider_factory(self):
        test_codex_provider_is_built_by_the_shared_provider_factory()

    def test_codex_tool_restrictions(self):
        test_codex_exec_adapter_uses_requested_model_and_disables_tools()

    def test_codex_fail_closed(self):
        test_codex_exec_adapter_fails_closed_without_final_message()

    def test_codex_structured_output(self):
        test_codex_structured_output_uses_schema_constrained_json()

    def test_codex_structured_arbitrary_dict_output(self):
        test_codex_structured_output_falls_back_for_arbitrary_dict_fields()

    def test_evpi(self):
        test_evpi_resolved_partition_and_irrelevant_question()

    def test_redundancy(self):
        test_redundancy_cost_reduces_question_score()

    def test_ready_queries(self):
        test_fully_specified_is_ready_and_absent_dimensions_are_confirmed_one_at_a_time()

    def test_explicit_office_type(self):
        test_explicit_office_typology_is_not_asked_again()

    def test_explicit_energy_requirement(self):
        test_explicit_qualitative_energy_requirement_is_not_asked_again()

    def test_porta_nuova_disambiguation(self):
        test_named_porta_nuova_is_disambiguated_after_intended_use_answer()

    def test_grouped_partial_answer(self):
        test_grouped_omissions_allow_partial_answer_then_ready()

    def test_confirm_omissions(self):
        test_explicit_no_preference_confirms_all_omitted_dimensions()

    def test_italian_no_interest_answer(self):
        test_italian_not_interested_confirms_only_current_dimension()

    def test_ambiguous_queries(self):
        test_ambiguous_and_missing_critical_are_asked()

    def test_answer_update(self):
        test_answer_updates_state_and_refines_query()

    def test_natural_model_rewrite(self):
        test_rewritten_query_is_natural_model_output_with_only_confirmed_details()

    def test_location_suggestion_selection(self):
        test_location_selection_can_resolve_reference_to_an_offered_option()

    def test_unknown_answer(self):
        test_unknown_answer_does_not_repeat_question_and_blocks()

    def test_nonblocking_ambiguity(self):
        test_nonblocking_ambiguity_does_not_prevent_readiness()

    def test_rejected_candidates(self):
        test_rejected_candidates_without_replacement_are_blocked()

    def test_contradiction(self):
        test_contradictory_answer_is_blocked()

    def test_no_preference(self):
        test_no_preference_resolves_to_optional_dimension_absence()

    def test_italian_question(self):
        test_italian_query_gets_italian_location_question()

    def test_readiness_gate(self):
        test_readiness_does_not_delegate_when_question_is_missing()

    def test_disabled_flag_preserves_original_query_and_skips_sage(self):
        request = AnalysisRequest(query="Find a building")
        with patch.object(settings, "ENABLE_SAGE_CLARIFICATION", False), patch(
            "app.services.sage_clarification.service.SageClarifier.process"
        ) as process:
            clarification, query = analysis_endpoint._apply_sage_if_enabled(request, MagicMock(), None)
        self.assertIsNone(clarification)
        self.assertEqual(query, request.query)
        process.assert_not_called()


class TestSageAnalysisBoundary(unittest.IsolatedAsyncioTestCase):
    async def test_ready_query_waits_for_review_then_invokes_existing_analysis_once(self):
        db = _db()
        request = AnalysisRequest(query="Find a large building", dataset_key="full")
        background = BackgroundTasks()
        queued = []
        background.add_task = lambda func, *args, **kwargs: queued.append((func, args, kwargs))
        expected_query = "Find a large building. Clarification provided by the user: area over 500 sqm."
        analysis_result = MagicMock()
        analysis_result.model_dump.return_value = {
            "run_id": "run-test", "gemini_responses": {}, "location": [],
            "broker_summary": "completed", "results_count": 0,
        }
        with (
            patch.object(settings, "ENABLE_SAGE_CLARIFICATION", True),
            patch("app.services.sage_clarification.service.SageClarifier.process", return_value=ClarificationResponse(
                status="READY", session_id="session-test", refined_query=expected_query
            )),
            patch.object(analysis_endpoint.RunRepository, "create_run"),
            patch("app.services.analysis_service.analysis_service.run_analysis", new_callable=AsyncMock, return_value={}) as run_analysis,
            patch("app.models.responses.AnalysisResults.model_validate", return_value=analysis_result),
            patch.object(analysis_endpoint, "make_json_safe", side_effect=lambda value: value),
            patch("app.services.agent_logger.AgentLogger") as agent_logger_cls,
        ):
            trace_logger = MagicMock()
            agent_logger_cls.return_value = trace_logger
            review = await analysis_endpoint.start_analysis(request, background, db, None)
            self.assertEqual(review.status, "REVIEW")
            self.assertEqual(review.refined_query, expected_query)
            self.assertEqual(len(queued), 0)
            run_analysis.assert_not_awaited()

            db.add(ClarificationSession(
                session_id="session-test", user_id=None, state={"refined_query": expected_query},
                status="ready",
            ))
            db.commit()
            confirmed_request = AnalysisRequest(
                query="Edited query approved by the user",
                dataset_key="full",
                clarification_session_id="session-test",
                clarification_confirmed=True,
            )
            response = await analysis_endpoint.start_analysis(confirmed_request, background, db, None)
            self.assertEqual(response.status, "processing")
            self.assertEqual(len(queued), 1)
            task, args, kwargs = queued[0]
            await task(*args, **kwargs)
            run_analysis.assert_awaited_once()
            self.assertEqual(run_analysis.await_args.kwargs["query"], "Edited query approved by the user")
        db.close()
