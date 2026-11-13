"""Persistent orchestration for the pre-analysis clarification wrapper."""

from __future__ import annotations

import json
import logging
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import ClarificationSession
from app.models.responses import ClarificationResponse
from app.services.llm.langchain_client import get_llm
from app.services.sage_clarification.prompt_loader import render_prompt
from app.services.sage_clarification.uncertainty import (
    EPSILON,
    parameter_specificity,
    question_score,
    normalized_beliefs,
)

logger = logging.getLogger(__name__)

DIMENSIONS = ("I", "D", "L", "Cb", "Ce", "Cp")
ANSWER_INTENTS = {"REQUIREMENT", "NO_PREFERENCE", "UNKNOWN", "REJECTED", "UNCLEAR"}
STATUSES = {
    "SPECIFIED", "NOT_REQUESTED", "UNCONFIRMED_ABSENT", "AMBIGUOUS",
    "MISSING_CRITICAL",
}
def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in normalized).split()
    )


def _normalize_phrase(text: str) -> str:
    return _normalize_text(text)


def _llm_text(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get("type") in (None, "text"):
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return "\n".join(text_parts)
    return str(content) if content is not None else ""


def _parse_llm_json(result: Any) -> Any:
    """Parse the JSON-only response requested by a structured SAGE prompt."""
    content = _llm_text(result).strip()
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Clarification model returned invalid JSON") from exc


DIMENSION_LABELS = {
    "it": {
        "I": "tipologia dell'immobile / intento di ricerca",
        "D": "destinazione d'uso e requisiti normativi",
        "L": "località",
        "Cb": "vincoli edilizi o strutturali, inclusi superficie e capienza/occupazione",
        "Ce": "prestazioni energetiche",
        "Cp": "servizi vicini d'interesse: sanità, mobilità, verde, sport, commercio e istruzione",
    },
    "en": {
        "I": "property type / search intent",
        "D": "intended use and regulatory requirements",
        "L": "location",
        "Cb": "building or structural constraints, including floor area and occupancy capacity",
        "Ce": "energy performance",
        "Cp": "nearby services of interest: healthcare, mobility, green spaces, sports, commerce, and education",
    },
}

class SageClarifier:
    """SAGE-inspired, query-dimension wrapper; never invokes MURENA agents."""

    def __init__(self, *, max_turns: Optional[int] = None,
                 redundancy_lambda: Optional[float] = None,
                 stop_alpha: Optional[float] = None, llm: Any = None):
        self.max_turns = max_turns if max_turns is not None else settings.SAGE_MAX_TURNS
        self.redundancy_lambda = (
            redundancy_lambda if redundancy_lambda is not None
            else settings.SAGE_REDUNDANCY_LAMBDA
        )
        self.stop_alpha = stop_alpha if stop_alpha is not None else settings.SAGE_EVPI_STOP_ALPHA
        self._llm = llm

    def _model(self):
        # SAGE and all MURENA agents use the same centralized provider choice.
        return self._llm or get_llm(temperature=0.0)

    def _generate_omission_questions(
        self,
        query: str,
        dimensions: list[str],
        language: str,
        context: Optional[dict] = None,
    ) -> list[dict]:
        """Ask the configured LLM to write a natural question for each omitted dimension."""
        output_schema = {
            "questions": [
                {"target_dimension": dimension, "question": "A natural, targeted user-facing question."}
                for dimension in dimensions
            ]
        }
        prompt = render_prompt(
            "omission_question",
            OUTPUT_SCHEMA=json.dumps(output_schema, ensure_ascii=False),
            LANGUAGE="Italian" if language == "it" else "English",
            QUERY=json.dumps(query, ensure_ascii=False),
            DIMENSIONS=json.dumps(
                {dimension: DIMENSION_LABELS[language][dimension] for dimension in dimensions},
                ensure_ascii=False,
            ),
            CONTEXT=json.dumps(context or {}, ensure_ascii=False),
        )
        data = _parse_llm_json(self._model().invoke(prompt))
        raw_questions = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(raw_questions, list):
            raise ValueError("Clarification model returned no questions for omitted dimensions")

        generated: dict[str, str] = {}
        allowed = set(dimensions)
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            dimension = item.get("target_dimension")
            question = item.get("question")
            if not isinstance(dimension, str) or dimension not in allowed or dimension in generated:
                continue
            if isinstance(question, str) and question.strip():
                generated[dimension] = question.strip()
        if set(generated) != allowed:
            missing = sorted(allowed - set(generated))
            raise ValueError(
                "Clarification model failed to formulate a question for: " + ", ".join(missing)
            )

        return [
            {
                "question": generated[dimension],
                "target_dimensions": [dimension],
                "target_parameters": [DIMENSION_LABELS[language][dimension]],
                "reason": None,
                "blocking": True,
                "alternatives": [],
                "kind": "omission_confirmation",
                "question_source": "llm_omission_question",
            }
            for dimension in dimensions
        ]

    def _ensure_omission_questions(self, state: dict) -> None:
        """Keep each unconfirmed omission connected to its own generated question."""
        for question in state.get("questions", []):
            targets = question.get("target_dimensions", [])
            if (
                question.get("kind") == "omission_confirmation"
                and len(targets) == 1
                and state["dimensions"][targets[0]]["status"] == "UNCONFIRMED_ABSENT"
            ):
                # Readiness requires explicit confirmation for every omitted
                # dimension, so the corresponding question must be selectable.
                question["blocking"] = True
        covered = {
            targets[0]
            for question in state.get("questions", [])
            if question.get("kind") == "omission_confirmation"
            and len(targets := question.get("target_dimensions", [])) == 1
        }
        missing = [
            dimension for dimension in DIMENSIONS
            if state["dimensions"][dimension]["status"] == "UNCONFIRMED_ABSENT"
            and dimension not in covered
        ]
        if missing:
            state.setdefault("questions", []).extend(
                self._generate_omission_questions(
                    state["original_query"],
                    missing,
                    state["language"],
                    context={
                        "confirmed_clarifications": state.get("clarifications", []),
                        "previous_turns": state.get("history", []),
                    },
                )
            )

    def _parse_query(self, query: str, language: str = "en") -> dict:
        normalized_query = _normalize_phrase(query)
        dimension_schema = {
            key: {"value": None, "status": "UNCONFIRMED_ABSENT", "evidence": None,
                  "alternatives": [], "reason": None}
            for key in DIMENSIONS
        }
        output_schema = {
            "dimensions": dimension_schema,
            "questions": [{
                "question": "...", "target_dimensions": ["L"],
                "target_parameters": ["city"], "reason": "...",
                "blocking": True, "alternatives": [], "kind": "location_disambiguation",
            }],
        }
        prompt = render_prompt(
            "query_parser",
            OUTPUT_SCHEMA=json.dumps(output_schema, ensure_ascii=False),
            LANGUAGE="Italian" if language == "it" else "English",
            QUERY=json.dumps(query, ensure_ascii=False),
        )
        result = self._model().invoke(prompt)
        data = _parse_llm_json(result)
        if not isinstance(data, dict):
            raise ValueError("Clarification model returned invalid structured output")
        dims = data.get("dimensions") if isinstance(data.get("dimensions"), dict) else {}
        clean_dims = {}
        for key in DIMENSIONS:
            raw = dims.get(key) if isinstance(dims.get(key), dict) else {}
            status = str(raw.get("status", "UNCONFIRMED_ABSENT")).upper()
            if status not in STATUSES:
                status = "UNCONFIRMED_ABSENT"
            value = raw.get("value")
            evidence = raw.get("evidence")
            alternatives = raw.get("alternatives", [])
            if not isinstance(alternatives, list):
                alternatives = []
            clean_dims[key] = {
                "value": value if isinstance(value, (str, int, float, list, dict)) else None,
                "status": status,
                "evidence": evidence if isinstance(evidence, str) else None,
                "alternatives": [str(item) for item in alternatives if item is not None],
                "reason": raw.get("reason") if isinstance(raw.get("reason"), str) else None,
            }
            if key == "L":
                if (
                    status == "SPECIFIED"
                    and (not isinstance(value, str)
                         or _normalize_phrase(value) not in normalized_query)
                ):
                    clean_dims[key].update({
                        "value": None,
                        "status": "MISSING_CRITICAL",
                        "reason": "The geographic value is not explicit in the query or available context.",
                    })
            evidence = clean_dims[key]["evidence"]
            if status == "NOT_REQUESTED" and (
                not evidence or _normalize_phrase(evidence) not in normalized_query
            ):
                # A model label alone cannot establish that an omission was intentional.
                clean_dims[key]["status"] = "UNCONFIRMED_ABSENT"
            if clean_dims[key]["status"] == "NOT_REQUESTED":
                clean_dims[key]["value"] = None
            if status == "SPECIFIED" and value is None:
                clean_dims[key]["status"] = "MISSING_CRITICAL"
            if status == "MISSING_CRITICAL":
                clean_dims[key]["value"] = None

        questions = []
        for raw in data.get("questions", []) if isinstance(data.get("questions"), list) else []:
            if not isinstance(raw, dict):
                continue
            raw_targets = raw.get("target_dimensions", [])
            if not isinstance(raw_targets, list):
                raw_targets = []
            targets = [d for d in raw_targets if d in DIMENSIONS]
            if not targets or not isinstance(raw.get("question"), str):
                continue
            kind = raw.get("kind")
            if kind == "location_disambiguation":
                if clean_dims["L"]["status"] not in {"AMBIGUOUS", "MISSING_CRITICAL"}:
                    continue
                targets = ["L"]
            elif kind == "omission_confirmation":
                targets = [
                    dimension for dimension in targets
                    if clean_dims[dimension]["status"] == "UNCONFIRMED_ABSENT"
                ]
                if len(targets) != 1:
                    continue
            else:
                targets = [
                    dimension for dimension in targets
                    if clean_dims[dimension]["status"] in {"AMBIGUOUS", "MISSING_CRITICAL"}
                ]
                if not targets:
                    continue
            has_ambiguity = any(
                clean_dims[d]["status"] in {"AMBIGUOUS", "MISSING_CRITICAL"}
                for d in targets
            )
            is_omission_question = (
                kind == "omission_confirmation"
                and len(targets) == 1
                and all(clean_dims[d]["status"] == "UNCONFIRMED_ABSENT" for d in targets)
            )
            if not has_ambiguity and not is_omission_question:
                continue
            alternatives = raw.get("alternatives", [])
            if not isinstance(alternatives, list):
                alternatives = []
            alternatives = [str(v) for v in alternatives if v is not None]
            target_parameters = [
                str(p) for p in raw.get("target_parameters", [])
            ] if isinstance(raw.get("target_parameters", []), list) else []
            question_text = raw["question"].strip()
            questions.append({
                "question": question_text,
                "target_dimensions": targets,
                "target_parameters": target_parameters,
                "reason": str(raw.get("reason") or "This detail changes the interpretation."),
                "blocking": (
                    True if kind == "omission_confirmation"
                    else bool(raw.get("blocking", True))
                ),
                "alternatives": alternatives,
                "kind": kind,
                "question_source": "llm_query_parser",
            })
        already_targeted = {
            dimension for question in questions
            for dimension in question["target_dimensions"]
        }
        missing_dimensions = [
            dimension for dimension in DIMENSIONS
            if dimension not in already_targeted
            and clean_dims[dimension]["status"] == "UNCONFIRMED_ABSENT"
        ]
        if missing_dimensions:
            questions.extend(
                self._generate_omission_questions(query, missing_dimensions, language)
            )
        return {"dimensions": clean_dims, "questions": questions}

    def _extract_omission_updates(self, state: dict, question: dict, answer: str) -> dict:
        """Let the model classify intent and extract explicit per-dimension updates."""
        targets = question.get("target_dimensions", [])
        schema = {
            dimension: {"status": "SPECIFIED|NOT_REQUESTED|UNCONFIRMED_ABSENT",
                        "value": None, "evidence": "exact supporting words from the answer"}
            for dimension in targets
        }
        prompt = render_prompt(
            "omission_answer",
            UPDATE_SCHEMA=json.dumps(schema, ensure_ascii=False),
            DIMENSION_LABELS=json.dumps(
                {d: DIMENSION_LABELS[state["language"]][d] for d in targets},
                ensure_ascii=False,
            ),
            QUESTION=json.dumps(question["question"], ensure_ascii=False),
            ANSWER=json.dumps(answer, ensure_ascii=False),
        )
        result = self._model().invoke(prompt)
        data = _parse_llm_json(result)
        intent = data.get("intent") if isinstance(data, dict) else None
        if intent not in ANSWER_INTENTS:
            intent = "UNCLEAR"
        intent_evidence = data.get("evidence") if isinstance(data, dict) else None
        if intent in {"NO_PREFERENCE", "UNKNOWN", "REJECTED"} and (
            not isinstance(intent_evidence, str) or not intent_evidence.strip()
            or _normalize_phrase(intent_evidence) not in _normalize_phrase(answer)
        ):
            intent = "UNCLEAR"
        raw_updates = data.get("updates", {}) if isinstance(data, dict) else {}
        updates = {}
        for dimension in targets:
            if intent == "NO_PREFERENCE":
                updates[dimension] = {
                    "status": "NOT_REQUESTED", "value": None, "evidence": intent_evidence,
                }
                continue
            if intent != "REQUIREMENT":
                updates[dimension] = {
                    "status": "UNCONFIRMED_ABSENT", "value": None, "evidence": None,
                }
                continue
            raw = raw_updates.get(dimension, {}) if isinstance(raw_updates, dict) else {}
            status = str(raw.get("status", "UNCONFIRMED_ABSENT")).upper()
            if status not in {"SPECIFIED", "NOT_REQUESTED", "UNCONFIRMED_ABSENT"}:
                status = "UNCONFIRMED_ABSENT"
            value = raw.get("value")
            evidence = raw.get("evidence")
            evidence_is_grounded = (
                isinstance(evidence, str) and bool(evidence.strip())
                and _normalize_phrase(evidence) in _normalize_phrase(answer)
            )
            if status in {"SPECIFIED", "NOT_REQUESTED"} and not evidence_is_grounded:
                status, value = "UNCONFIRMED_ABSENT", None
            if status == "SPECIFIED" and not isinstance(value, (str, int, float, list, dict)):
                status, value = "UNCONFIRMED_ABSENT", None
            if status == "SPECIFIED" and not str(value).strip():
                status, value = "UNCONFIRMED_ABSENT", None
            updates[dimension] = {
                "status": status,
                "value": value if status == "SPECIFIED" else None,
                "evidence": evidence if status in {"SPECIFIED", "NOT_REQUESTED"} else None,
            }
        return {"intent": intent, "updates": updates, "evidence": intent_evidence}

    def _interpret_location_answer(self, state: dict, question: dict, answer: str) -> dict:
        """Use the model to interpret a response to a geographic clarification."""
        prompt = render_prompt(
            "location_answer",
            PLACE=json.dumps(state["dimensions"]["L"].get("value"), ensure_ascii=False),
            ALTERNATIVES=json.dumps(question.get("alternatives", []), ensure_ascii=False),
            ORIGINAL_QUERY=json.dumps(state["original_query"], ensure_ascii=False),
            QUESTION=json.dumps(question["question"], ensure_ascii=False),
            ANSWER=json.dumps(answer, ensure_ascii=False),
        )
        result = self._model().invoke(prompt)
        try:
            data = _parse_llm_json(result)
        except ValueError:
            return {"intent": "UNCLEAR"}
        if not isinstance(data, dict):
            return {"intent": "UNCLEAR"}
        intent = data.get("intent")
        if intent not in ANSWER_INTENTS:
            intent = "UNCLEAR"
        evidence = data.get("evidence")
        if intent in {"NO_PREFERENCE", "UNKNOWN", "REJECTED"}:
            if (
                not isinstance(evidence, str) or not evidence.strip()
                or _normalize_phrase(evidence) not in _normalize_phrase(answer)
            ):
                intent = "UNCLEAR"
            return {"intent": intent, "evidence": evidence}
        if intent != "REQUIREMENT":
            return {"intent": intent, "evidence": evidence}
        city = data.get("city")
        selected_alternative = data.get("selected_alternative")
        if not isinstance(city, str) or not city.strip():
            return {"intent": "UNCLEAR"}
        if not isinstance(evidence, str) or not evidence.strip():
            return {"intent": "UNCLEAR"}
        if _normalize_phrase(evidence) not in _normalize_phrase(answer):
            return {"intent": "UNCLEAR"}
        if selected_alternative is not None:
            offered = {
                _normalize_phrase(option)
                for option in question.get("alternatives", [])
            }
            if (
                not isinstance(selected_alternative, str)
                or _normalize_phrase(selected_alternative) not in offered
                or _normalize_phrase(city) != _normalize_phrase(selected_alternative)
            ):
                return {"intent": "UNCLEAR"}
        return {
            "intent": "REQUIREMENT", "city": city.strip(), "evidence": evidence,
            "selected_alternative": selected_alternative,
        }

    def _classify_answer(self, state: dict, question: dict, answer: str) -> dict:
        """Ask the model to classify response intent and check consistency."""
        prompt = render_prompt(
            "answer_consistency",
            ORIGINAL_QUERY=json.dumps(state["original_query"], ensure_ascii=False),
            CONFIRMED_CLARIFICATIONS=json.dumps(
                state.get("clarifications", []), ensure_ascii=False
            ),
            TARGET_DIMENSIONS=json.dumps(question.get("target_dimensions", [])),
            DIMENSION_LABELS=json.dumps(
                {dimension: DIMENSION_LABELS[state["language"]][dimension]
                 for dimension in question.get("target_dimensions", [])},
                ensure_ascii=False,
            ),
            QUESTION=json.dumps(question["question"], ensure_ascii=False),
            ANSWER=json.dumps(answer, ensure_ascii=False),
        )
        try:
            result = self._model().invoke(prompt)
            data = _parse_llm_json(result)
            relation = data.get("relation") if isinstance(data, dict) else None
            intent = data.get("intent") if isinstance(data, dict) else None
            evidence = data.get("evidence") if isinstance(data, dict) else None
            if intent in {"NO_PREFERENCE", "UNKNOWN", "REJECTED"} and (
                not isinstance(evidence, str) or not evidence.strip()
                or _normalize_phrase(evidence) not in _normalize_phrase(answer)
            ):
                intent = "UNCLEAR"
            return {
                "relation": relation if relation in {"consistent", "contradictory", "unclear"} else "unclear",
                "intent": intent if intent in ANSWER_INTENTS else "UNCLEAR",
                "evidence": evidence,
            }
        except Exception:
            logger.warning("Could not validate clarification answer", exc_info=True)
            return {"relation": "unclear", "intent": "UNCLEAR", "evidence": None}

    @staticmethod
    def _question_belief(question: dict) -> tuple[dict[str, float], dict[str, Optional[str]]]:
        options = question.get("alternatives") or []
        if not options:
            # This records the SAGE epsilon viability only; it is not a
            # normalized probability over unknown values.
            return {"<UNK>": EPSILON}, {"<UNK>": None}
        possible_values: list[Optional[str]] = [str(option) for option in options]
        if question.get("kind") == "location_disambiguation":
            # The question always includes an open "another city" answer, so
            # represent that outcome instead of treating suggestions as exhaustive.
            possible_values.append(None)
        viability = parameter_specificity(specified=False, domain_size=len(possible_values))
        weights = {f"candidate_{i}": viability for i, _ in enumerate(possible_values)}
        outcomes = {f"candidate_{i}": option for i, option in enumerate(possible_values)}
        return weights, outcomes

    @classmethod
    def _refresh_beliefs(cls, state: dict) -> None:
        beliefs = {}
        candidates = []
        for question_index, question in enumerate(state.get("questions", [])):
            targets = question.get("target_dimensions", [])
            if targets and all(state["dimensions"][d]["status"] in {"SPECIFIED", "NOT_REQUESTED"} for d in targets):
                beliefs[f"question_{question_index}"] = {"resolved": 1.0}
                continue
            weights, _ = cls._question_belief(question)
            if weights and question.get("alternatives"):
                total = sum(weights.values())
                weights = {candidate: value / total for candidate, value in weights.items()}
            indexed_weights = {
                (f"q{question_index}_unknown" if candidate == "<UNK>"
                 else f"q{question_index}_c{candidate.removeprefix('candidate_')}"): value
                for candidate, value in weights.items()
            }
            beliefs[f"question_{question_index}"] = indexed_weights
            for candidate_index, alternative in enumerate(question.get("alternatives", [])):
                candidates.append({
                    "id": f"q{question_index}_c{candidate_index}",
                    "target_dimensions": targets,
                    "interpretation": str(alternative),
                    "belief": indexed_weights.get(f"q{question_index}_c{candidate_index}"),
                    "other_requirements": "unchanged",
                })
            if not question.get("alternatives"):
                candidates.append({
                    "id": f"q{question_index}_unknown",
                    "target_dimensions": targets,
                    "interpretation": "<UNK>",
                    "domain_unknown": True,
                    "viability": EPSILON,
                    "other_requirements": "unchanged",
                })
        state["candidate_beliefs"] = beliefs
        state["candidate_interpretations"] = candidates
        necessary_dimensions = {
            dimension
            for question in state.get("questions", [])
            if question.get("blocking", True)
            for dimension in question.get("target_dimensions", [])
        }
        for dimension in DIMENSIONS:
            status = state["dimensions"][dimension]["status"]
            state["dimensions"][dimension]["clarification_necessary"] = (
                status == "UNCONFIRMED_ABSENT"
                or (dimension in necessary_dimensions and status in {"AMBIGUOUS", "MISSING_CRITICAL"})
            )

    def _select_question(self, state: dict) -> Optional[dict]:
        scored = []
        for index, question in enumerate(state.get("questions", [])):
            targets = question.get("target_dimensions", [])
            if not question.get("blocking", True):
                continue
            if all(state["dimensions"][d]["status"] in {"SPECIFIED", "NOT_REQUESTED"} for d in targets):
                continue
            weights, outcomes = self._question_belief(question)
            count = sum(state.get("asked_aspects", {}).get(dimension, 0) for dimension in targets)
            if any(dimension in state.get("unanswerable_aspects", []) for dimension in targets):
                continue
            evpi, score = question_score(
                weights, outcomes, redundancy_count=count,
                redundancy_lambda=self.redundancy_lambda,
            )
            current_best = max(normalized_beliefs(weights).values(), default=0.0)
            # Apply the SAGE stopping test only when the response domain is
            # enumerable. An unknown domain has no defensible answer prior,
            # so it remains eligible for a targeted question.
            if question.get("alternatives") and score < self.stop_alpha * current_best:
                continue
            scored.append((score, evpi, -index, question))
        if not scored:
            return None
        return max(scored, key=lambda item: item[:3])[3]

    def _ready(self, state: dict) -> bool:
        if any(dim["status"] in {"MISSING_CRITICAL", "UNCONFIRMED_ABSENT"}
               for dim in state["dimensions"].values()):
            return False
        nonblocking_dimensions = {
            dimension
            for question in state.get("questions", [])
            if not question.get("blocking", True)
            for dimension in question.get("target_dimensions", [])
            if not any(
                other.get("blocking", True) and dimension in other.get("target_dimensions", [])
                for other in state.get("questions", [])
            )
        }
        return not any(
            dimension["status"] == "AMBIGUOUS"
            for key, dimension in state["dimensions"].items()
            if key not in nonblocking_dimensions
        )

    def _save(self, db: Session, row: ClarificationSession, state: dict, status: str) -> None:
        row.state = state
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
        db.refresh(row)

    def _result(self, state: dict, session_id: str, db: Session,
                row: ClarificationSession) -> ClarificationResponse:
        self._ensure_omission_questions(state)
        unresolved = self._select_question(state)
        if self._ready(state):
            state["refined_query"] = self._refine(state)
            self._save(db, row, state, "ready")
            return ClarificationResponse(
                status="READY", session_id=session_id,
                refined_query=state["refined_query"], turn=state["turn"],
            )
        question_targets = {
            dimension
            for question in state.get("questions", [])
            if question.get("blocking", True)
            for dimension in question.get("target_dimensions", [])
        }
        if any(
            dimension["status"] == "MISSING_CRITICAL"
            and key not in question_targets
            for key, dimension in state["dimensions"].items()
        ):
            self._save(db, row, state, "blocked")
            return ClarificationResponse(
                status="BLOCKED", session_id=session_id,
                message="A critical query detail has no safe clarification path; analysis was not started.",
                turn=state["turn"],
            )
        if state["turn"] >= self.max_turns or unresolved is None:
            self._save(db, row, state, "blocked")
            return ClarificationResponse(
                status="BLOCKED", session_id=session_id,
                message="A necessary query detail remains unresolved; analysis was not started.",
                turn=state["turn"],
            )
        self._save(db, row, state, "active")
        return ClarificationResponse(
            status="ASK", session_id=session_id, question=unresolved["question"],
            turn=state["turn"],
        )

    def _refine(self, state: dict) -> str:
        """Ask the LLM to synthesize the original query and confirmed answers naturally."""
        language = state.get("language", "en")
        clarifications = []
        for item in state.get("clarifications", []):
            answer = item.get("text", "").strip()
            if not answer:
                continue
            targets = item.get("target_dimensions") or []
            clarifications.append({
                "question": item.get("question"),
                "answer": answer,
                "dimensions": {
                    dimension: DIMENSION_LABELS[language].get(dimension, dimension)
                    for dimension in targets
                },
                "confirmed_requirements": item.get("values", {}),
            })
        prompt = render_prompt(
            "query_rewriter",
            ORIGINAL_QUERY=json.dumps(state["original_query"].strip(), ensure_ascii=False),
            CLARIFICATIONS=json.dumps(clarifications, ensure_ascii=False),
        )
        result = self._model().invoke(prompt)
        rewritten_query = _llm_text(result).strip()
        if not rewritten_query:
            raise ValueError("Clarification model returned an empty rewritten query")
        return rewritten_query

    def process(self, *, db: Session, user_input: str,
                session_id: Optional[str] = None, user_id: Optional[int] = None,
                clarification_response: Optional[str] = None,
                language: str = "en") -> ClarificationResponse:
        """Start a clarification session or apply one answer to an existing session."""
        if not session_id:
            language = language if language in {"en", "it"} else "en"
            state = self._parse_query(user_input, language)
            state.update({
                "original_query": user_input,
                "language": language,
                "turn": 0,
                "clarifications": [],
                "asked_aspects": {},
                "unanswerable_aspects": [],
                "excluded_interpretations": {},
                "candidate_beliefs": {},
                "history": [],
            })
            self._refresh_beliefs(state)
            session_id = str(uuid.uuid4())
            row = ClarificationSession(session_id=session_id, user_id=user_id,
                                      state=state, status="active")
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._result(state, session_id, db, row)

        row = db.query(ClarificationSession).filter(
            ClarificationSession.session_id == session_id
        ).first()
        if not row or (row.user_id is not None and row.user_id != user_id):
            return ClarificationResponse(status="BLOCKED", session_id=session_id,
                                         message="Clarification session was not found.")
        if row.status != "active":
            return ClarificationResponse(status="BLOCKED", session_id=session_id,
                                         message="Clarification session is no longer active.")
        state = dict(row.state or {})
        pending = self._select_question(state)
        answer = (clarification_response or "").strip()
        if pending is None:
            return self._result(state, session_id, db, row)

        state["turn"] = int(state.get("turn", 0)) + 1
        aspect_keys = pending.get("target_dimensions", [])
        for aspect_key in aspect_keys:
            state.setdefault("asked_aspects", {})[aspect_key] = (
                state.setdefault("asked_aspects", {}).get(aspect_key, 0) + 1
            )
        state.setdefault("history", []).append({
            "question": pending["question"], "answer": answer,
            "target_dimensions": pending.get("target_dimensions", []),
        })
        if not answer:
            state.setdefault("unanswerable_aspects", []).extend(aspect_keys)
        elif pending.get("kind") == "omission_confirmation":
            result = self._extract_omission_updates(state, pending, answer)
            intent = result["intent"]
            if intent in {"UNKNOWN", "REJECTED"}:
                state.setdefault("unanswerable_aspects", []).extend(aspect_keys)
                if intent == "REJECTED":
                    for dimension in aspect_keys:
                        state.setdefault("excluded_interpretations", {}).setdefault(dimension, []).extend(
                            pending.get("alternatives", [])
                        )
            elif intent == "UNCLEAR":
                replacements = self._generate_omission_questions(
                    state["original_query"],
                    aspect_keys,
                    state["language"],
                    context={
                        "previous_question": pending["question"],
                        "previous_user_answer": answer,
                        "answer_was_unclear": True,
                        "confirmed_clarifications": state.get("clarifications", []),
                    },
                )
                replacement_by_dimension = {
                    question["target_dimensions"][0]: question
                    for question in replacements
                }
                for question in state.get("questions", []):
                    targets = question.get("target_dimensions", [])
                    if question.get("kind") == "omission_confirmation" and len(targets) == 1:
                        replacement = replacement_by_dimension.pop(targets[0], None)
                        if replacement:
                            question.clear()
                            question.update(replacement)
                if replacement_by_dimension:
                    state.setdefault("questions", []).extend(replacement_by_dimension.values())
            else:
                specified = {}
                not_requested = []
                unresolved = []
                for dimension, update in result["updates"].items():
                    state["dimensions"][dimension].update({
                        "value": update["value"], "status": update["status"],
                        "evidence": update["evidence"], "reason": None,
                        "alternatives": [],
                    })
                    if update["status"] == "SPECIFIED":
                        specified[dimension] = str(update["value"])
                    elif update["status"] == "NOT_REQUESTED":
                        not_requested.append(dimension)
                    else:
                        unresolved.append(dimension)
                if specified or not_requested:
                    state.setdefault("clarifications", []).append({
                        "text": answer, "question": pending["question"],
                        "target_dimensions": list(specified) + not_requested,
                        "values": specified,
                        "not_requested_dimensions": not_requested,
                    })
                if unresolved:
                    replacements = self._generate_omission_questions(
                        state["original_query"],
                        unresolved,
                        state["language"],
                        context={
                            "previous_question": pending["question"],
                            "previous_user_answer": answer,
                            "confirmed_clarifications": state.get("clarifications", []),
                        },
                    )
                    replacement_by_dimension = {
                        question["target_dimensions"][0]: question
                        for question in replacements
                    }
                    for question in state.get("questions", []):
                        targets = question.get("target_dimensions", [])
                        if question.get("kind") == "omission_confirmation" and len(targets) == 1:
                            replacement = replacement_by_dimension.pop(targets[0], None)
                            if replacement:
                                question.clear()
                                question.update(replacement)
                    if replacement_by_dimension:
                        state.setdefault("questions", []).extend(replacement_by_dimension.values())
        elif pending.get("kind") == "location_disambiguation":
            result = self._interpret_location_answer(state, pending, answer)
            if result["intent"] == "REQUIREMENT":
                place = state["dimensions"]["L"].get("value")
                city = result["city"]
                combined_location = f"{place}, {city}" if place else city
                state.setdefault("clarifications", []).append({
                    "text": answer, "question": pending["question"],
                    "target_dimensions": ["L"],
                    "values": {"L": combined_location},
                })
                state["dimensions"]["L"].update({
                    "value": combined_location, "status": "SPECIFIED",
                    "evidence": result["evidence"], "alternatives": [], "reason": None,
                })
            elif result["intent"] == "NO_PREFERENCE":
                state["dimensions"]["L"].update({
                    "value": None, "status": "NOT_REQUESTED", "evidence": result["evidence"],
                    "alternatives": [], "reason": None,
                })
                state.setdefault("clarifications", []).append({
                    "text": answer, "question": pending["question"],
                    "target_dimensions": ["L"], "not_requested_dimensions": ["L"],
                })
            else:
                # Keep unresolved location questions eligible even if the model
                # classifies an answer as unknown, rejected, or unclear. Those
                # labels alone must not permanently discard a critical location.
                if result["intent"] == "REJECTED":
                    state.setdefault("excluded_interpretations", {}).setdefault("L", []).extend(
                        pending.get("alternatives", [])
                    )
        else:
            result = self._classify_answer(state, pending, answer)
            intent = result["intent"]
            if intent == "NO_PREFERENCE":
                for dimension in aspect_keys:
                    state["dimensions"][dimension].update({
                        "value": None, "status": "NOT_REQUESTED", "evidence": result["evidence"],
                        "alternatives": [], "reason": None,
                    })
                state.setdefault("clarifications", []).append({
                    "text": answer, "question": pending["question"],
                    "target_dimensions": aspect_keys,
                    "not_requested_dimensions": aspect_keys,
                })
            elif intent in {"UNKNOWN", "REJECTED", "UNCLEAR"}:
                state.setdefault("unanswerable_aspects", []).extend(aspect_keys)
                if intent == "REJECTED":
                    for dimension in aspect_keys:
                        state.setdefault("excluded_interpretations", {}).setdefault(dimension, []).extend(
                            pending.get("alternatives", [])
                        )
            elif result["relation"] != "consistent":
                reason = (
                    "The clarification conflicts with existing requirements."
                    if result["relation"] == "contradictory"
                    else "The clarification could not be reconciled safely."
                )
                for dimension in aspect_keys:
                    state["dimensions"][dimension].update({
                        "value": None, "status": "MISSING_CRITICAL", "evidence": answer,
                        "reason": reason,
                    })
                state.setdefault("unanswerable_aspects", []).extend(aspect_keys)
                self._refresh_beliefs(state)
                self._save(db, row, state, "blocked")
                return ClarificationResponse(
                    status="BLOCKED", session_id=session_id,
                    message=reason + " Analysis was not started.", turn=state["turn"],
                )
            else:
                state.setdefault("clarifications", []).append({
                    "text": answer, "question": pending["question"],
                    "target_dimensions": aspect_keys,
                })
                for dimension in aspect_keys:
                    state["dimensions"][dimension].update({
                        "value": answer, "status": "SPECIFIED", "evidence": answer,
                        "alternatives": [], "reason": None,
                    })
        self._refresh_beliefs(state)
        # Non-requirement answers leave uncertainty intact and suppress repeats.
        return self._result(state, session_id, db, row)
