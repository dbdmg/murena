"""Persistent orchestration for the pre-analysis clarification wrapper."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import ClarificationSession
from app.models.responses import ClarificationResponse
from app.services.llm.langchain_client import get_llm
from app.utils.json_parser import safe_extract_json
from app.services.sage_clarification.prompt_loader import render_prompt
from app.services.sage_clarification.uncertainty import (
    EPSILON,
    parameter_specificity,
    question_score,
    normalized_beliefs,
)

logger = logging.getLogger(__name__)

DIMENSIONS = ("I", "D", "L", "Cb", "Ce", "Cp")
STATUSES = {
    "SPECIFIED", "NOT_REQUESTED", "UNCONFIRMED_ABSENT", "AMBIGUOUS",
    "MISSING_CRITICAL",
}
UNKNOWN_ANSWERS = {"i don't know", "i don t know", "i do not know", "not sure", "unsure", "non lo so"}
NO_PREFERENCE_ANSWERS = {
    "any", "anything", "anywhere", "no preference", "no preference either way", "none",
    "doesn't matter", "doesnt matter", "doesn t matter", "does not matter to me",
    "not relevant", "don't care", "don t care", "non ho preferenze", "non mi interessa",
    "non e rilevante", "non e importante", "nessun interesse",
}
REJECTION_ANSWERS = {"no", "neither", "none of those", "not any of those", "nessuna", "nessuno"}


def _is_unknown(text: str) -> bool:
    normalized = re.sub(r"[^a-zà-ÿ ]", " ", text.lower())
    return " ".join(normalized.split()) in UNKNOWN_ANSWERS


def _normalized_answer(text: str) -> str:
    return " ".join(re.sub(r"[^a-zà-ÿ ]", " ", text.lower()).split())


def _normalize_phrase(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9à-ÿ ]", " ", text.lower()).split())


PROPERTY_TYPE_PATTERNS = (
    re.compile(r"\b(?:uffici(?:o)?|office(?:s)?)\b", re.IGNORECASE),
    re.compile(r"\b(?:residenzial[ei]|residential)\b", re.IGNORECASE),
    re.compile(r"\b(?:commercial[ei]|commercial|negozi?|shops?)\b", re.IGNORECASE),
    re.compile(r"\b(?:appartament[oi]|apartments?)\b", re.IGNORECASE),
    re.compile(r"\b(?:magazzin[oi]|warehouses?|industrial[ei])\b", re.IGNORECASE),
)


def _explicit_property_type(query: str) -> Optional[str]:
    """Return a clearly named physical typology without deriving one from use."""
    for pattern in PROPERTY_TYPE_PATTERNS:
        match = pattern.search(query)
        if match:
            return match.group(0)
    return None


_PROPER_PLACE = r"[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’\-]*(?:\s+[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’\-]*)*"
_LOCATION_CUE = re.compile(
    rf"(?i:\b(?:near|close to|by|vicino\s+(?:a|al|alla|allo|ai|alle)|nei\s+pressi\s+di|presso|accanto\s+a)\s+(?:the\s+)?)(?P<place>{_PROPER_PLACE})",
)


def _explicit_location_reference(query: str) -> Optional[dict[str, Any]]:
    """Find a named place following a proximity cue and any explicit city suffix."""
    match = _LOCATION_CUE.search(query)
    if not match:
        return None
    place = match.group("place")
    suffix = query[match.end():]
    city_match = re.match(
        rf"(?i:\s*,?\s*(?:(?:in|a)\s+(?:the\s+city\s+of\s+)?)?)(?P<city>{_PROPER_PLACE})",
        suffix,
    )
    if city_match:
        end = match.end() + city_match.end()
        value = query[match.start("place"):end].strip()
        return {"place": place, "value": value, "city_supplied": True}
    return {"place": place, "value": place, "city_supplied": False}


def _location_disambiguation_question(place: str, language: str) -> dict:
    if language == "it":
        question = (
            f"Hai indicato «{place}»: in quale città si trova? "
            "Basta aggiungere il nome della città."
        )
    else:
        question = (
            f"You mentioned “{place}”. Which city is it in? "
            "Just add the city name."
        )
    return {
        "question": question,
        "target_dimensions": ["L"],
        "target_parameters": ["city", f"place: {place}"],
        "reason": "The query names a place but does not identify its city.",
        "blocking": True,
        "alternatives": [],
        "kind": "location_disambiguation",
    }


def _looks_like_place_answer(text: str) -> bool:
    """Conservative fallback for a direct answer to a city-name question."""
    normalized = _normalize_phrase(text)
    tokens = normalized.split()
    invalid_tokens = {
        "no", "not", "non", "neither", "voglio", "vorrei", "farci", "cerco",
        "preferisco", "studentato", "student", "housing", "office", "offices",
        "ufficio", "uffici", "energy", "energetica", "classe", "building", "edificio",
    }
    return (
        bool(tokens)
        and len(tokens) <= 8
        and normalized not in NO_PREFERENCE_ANSWERS
        and normalized not in UNKNOWN_ANSWERS
        and not any(token in invalid_tokens for token in tokens)
        and not any(token in {"o", "oppure", "or", "and", "e"} for token in tokens)
    )


def _generic_location_question(parameters: list[str], language: str = "en") -> str:
    parameter_text = " ".join(parameters).lower()
    if language == "it":
        if "univers" in parameter_text:
            return "A quale università ti riferisci? Puoi indicarne il nome o la sede."
        if "city" in parameter_text or "town" in parameter_text or "citt" in parameter_text:
            return "A quale città ti riferisci? Puoi indicare anche un quartiere o un comune vicino."
        if "landmark" in parameter_text or "place" in parameter_text or "luogo" in parameter_text:
            return "A quale luogo o punto di riferimento ti riferisci? Puoi indicarne il nome o la zona."
        return "A quale località ti riferisci? Puoi indicare una città, un quartiere o un punto di riferimento."
    if "univers" in parameter_text:
        return "Which university do you mean? You can give its name or campus."
    if "city" in parameter_text or "town" in parameter_text:
        return "Which city do you mean? A neighborhood or nearby town works too."
    if "landmark" in parameter_text or "place" in parameter_text:
        return "Which landmark or place do you mean? You can give its name or area."
    return "Which location are you referring to? You can name a city, neighborhood, or landmark."


DIMENSION_LABELS = {
    "it": {
        "I": "tipologia dell'immobile / intento di ricerca",
        "D": "destinazione d'uso e requisiti normativi",
        "L": "località",
        "Cb": "vincoli edilizi o strutturali",
        "Ce": "prestazioni energetiche",
        "Cp": "servizi e infrastrutture di prossimità",
    },
    "en": {
        "I": "property type / search intent",
        "D": "intended use and regulatory requirements",
        "L": "location",
        "Cb": "building or structural constraints",
        "Ce": "energy performance",
        "Cp": "nearby services and infrastructure",
    },
}

DIMENSION_GUIDANCE = {
    "it": {
        "I": "Per esempio: uffici, residenziale, commerciale oppure qualsiasi tipologia.",
        "D": "Per esempio: residenza universitaria, social housing o servizi pubblici.",
        "L": "Puoi indicare una città, un quartiere o un punto di riferimento.",
        "Cb": "Per esempio: superficie minima, capienza o una caratteristica strutturale; va bene anche una descrizione qualitativa.",
        "Ce": "Per esempio: una classe energetica target, oppure un obiettivo qualitativo come alta o bassa efficienza.",
        "Cp": "Per esempio: trasporti, aree verdi, sanità, istruzione, sport o negozi nelle vicinanze.",
    },
    "en": {
        "I": "For example: offices, residential, commercial, or any property type.",
        "D": "For example: student housing, social housing, or public services.",
        "L": "You can name a city, neighborhood, or landmark.",
        "Cb": "For example: minimum floor area, capacity, or a structural feature; a qualitative description is fine too.",
        "Ce": "For example: a target energy class, or a qualitative goal such as high or low efficiency.",
        "Cp": "For example: nearby transit, green areas, healthcare, education, sports, or shops.",
    },
}


def _omission_confirmation_question(dimensions: list[str], language: str) -> dict:
    labels = DIMENSION_LABELS[language]
    guidance = DIMENSION_GUIDANCE[language]
    details = ", ".join(labels[key] for key in dimensions)
    if language == "it":
        if len(dimensions) == 1:
            question = (
                f"Non hai specificato {details}. {guidance[dimensions[0]]} "
                "È una dimensione che non ti interessa, oppure vuoi aggiungere un requisito? "
                "Gli esempi sono solo spunti: userò soltanto ciò che confermi."
            )
        else:
            question = (
                f"Non hai specificato: {details}. Li hai omessi perché non ti interessano, "
                "oppure vuoi aggiungere requisiti? Indica quello che ti interessa e conferma "
                "che gli altri non sono rilevanti."
            )
        reason = "The user has not confirmed whether these omitted dimensions are intentional."
    else:
        if len(dimensions) == 1:
            question = (
                f"Your query does not specify {details}. {guidance[dimensions[0]]} "
                "Is this dimension unimportant to you, or would you like to add a requirement? "
                "These are only examples; I will use only what you confirm."
            )
        else:
            question = (
                f"Your query does not specify: {details}. Did you omit these because they do not "
                "matter to you, or would you like to add requirements? List what matters and "
                "confirm that the others are not relevant."
            )
        reason = "The user has not confirmed whether these omitted dimensions are intentional."
    return {
        "question": question,
        "target_dimensions": dimensions,
        "target_parameters": [labels[key] for key in dimensions],
        "reason": reason,
        "blocking": True,
        "alternatives": [],
        "kind": "omission_confirmation",
    }


def _explicitly_rejected(options: list[str], answer: str) -> list[str]:
    rejected = []
    for option in options:
        escaped = re.escape(option.lower())
        if re.search(rf"(?:\bnot\b|\bno\b|\bneither\b|\bnon\b)\s+(?:the\s+)?{escaped}\b", answer.lower()):
            rejected.append(option)
    return rejected


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
                "blocking": True, "alternatives": [],
            }],
        }
        prompt = render_prompt(
            "query_parser",
            OUTPUT_SCHEMA=json.dumps(output_schema, ensure_ascii=False),
            LANGUAGE="Italian" if language == "it" else "English",
            QUERY=json.dumps(query, ensure_ascii=False),
        )
        result = self._model().invoke(prompt)
        data = safe_extract_json(getattr(result, "content", result))
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
                location_alternatives = [
                    alternative for alternative in clean_dims[key]["alternatives"]
                    if _normalize_phrase(alternative) in normalized_query
                ]
                clean_dims[key]["alternatives"] = (
                    location_alternatives
                    if len(location_alternatives) == len(clean_dims[key]["alternatives"])
                    else []
                )
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
            if status in {"AMBIGUOUS", "MISSING_CRITICAL"}:
                clean_dims[key]["value"] = None

        # Guard against a parser miss on an explicit, common physical typology.
        # This only corrects omitted labels; it does not infer a type from the
        # intended use or overwrite an actual ambiguity reported by the model.
        explicit_type = _explicit_property_type(query)
        if explicit_type and clean_dims["I"]["status"] in {
            "UNCONFIRMED_ABSENT", "NOT_REQUESTED"
        }:
            clean_dims["I"].update({
                "value": explicit_type,
                "status": "SPECIFIED",
                "evidence": explicit_type,
                "reason": None,
            })
        location_reference = _explicit_location_reference(query)
        if location_reference and clean_dims["L"]["status"] in {
            "UNCONFIRMED_ABSENT", "NOT_REQUESTED", "MISSING_CRITICAL"
        }:
            if location_reference["city_supplied"]:
                clean_dims["L"].update({
                    "value": location_reference["value"],
                    "status": "SPECIFIED",
                    "evidence": location_reference["value"],
                    "reason": None,
                })
            else:
                clean_dims["L"].update({
                    "value": location_reference["place"],
                    "status": "AMBIGUOUS",
                    "evidence": location_reference["place"],
                    "reason": "A named place is explicit, but its city is not.",
                })

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
            if not any(clean_dims[d]["status"] in {"AMBIGUOUS", "MISSING_CRITICAL"} for d in targets):
                continue
            alternatives = raw.get("alternatives", [])
            if not isinstance(alternatives, list):
                alternatives = []
            alternatives = [str(v) for v in alternatives if v is not None]
            target_parameters = [
                str(p) for p in raw.get("target_parameters", [])
            ] if isinstance(raw.get("target_parameters", []), list) else []
            question_text = raw["question"].strip()
            if "L" in targets:
                # No geographic catalog/context is available at this boundary.
                # Keep only location candidates named in the user's text.
                grounded_alternatives = [
                    alternative for alternative in alternatives
                    if _normalize_phrase(alternative) in normalized_query
                ]
                if len(grounded_alternatives) != len(alternatives):
                    grounded_alternatives = []
                alternatives = grounded_alternatives
                if (
                    location_reference and not location_reference["city_supplied"]
                    and clean_dims["L"]["status"] == "AMBIGUOUS"
                ):
                    question_text = _location_disambiguation_question(
                        location_reference["place"], language
                    )["question"]
                    target_parameters = ["city", f"place: {location_reference['place']}"]
                elif not alternatives:
                    question_text = _generic_location_question(target_parameters, language)
            questions.append({
                "question": question_text,
                "target_dimensions": targets,
                "target_parameters": target_parameters,
                "reason": str(raw.get("reason") or "This detail changes the interpretation."),
                "blocking": bool(raw.get("blocking", True)),
                "alternatives": alternatives,
            })
        already_targeted = {
            dimension for question in questions
            for dimension in question["target_dimensions"]
        }
        for dimension in DIMENSIONS:
            if dimension in already_targeted:
                continue
            if (
                dimension == "L"
                and location_reference
                and not location_reference["city_supplied"]
                and clean_dims["L"]["status"] == "AMBIGUOUS"
            ):
                questions.append(_location_disambiguation_question(
                    location_reference["place"], language
                ))
                already_targeted.add(dimension)
            elif clean_dims[dimension]["status"] == "UNCONFIRMED_ABSENT":
                questions.append(_omission_confirmation_question([dimension], language))
                already_targeted.add(dimension)
        return {"dimensions": clean_dims, "questions": questions}

    def _extract_omission_updates(self, state: dict, question: dict, answer: str) -> dict:
        """Extract only explicit per-dimension confirmations from a grouped answer."""
        targets = question.get("target_dimensions", [])
        if _normalized_answer(answer) in NO_PREFERENCE_ANSWERS:
            return {dimension: {"status": "NOT_REQUESTED", "value": None,
                                "evidence": answer}
                    for dimension in targets}
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
        data = safe_extract_json(getattr(result, "content", result))
        raw_updates = data.get("updates", {}) if isinstance(data, dict) else {}
        updates = {}
        for dimension in targets:
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
        return updates

    def _classify_answer(self, state: dict, question: dict, answer: str) -> str:
        """Check a new answer against original and previously confirmed evidence."""
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
            data = safe_extract_json(getattr(result, "content", result))
            relation = data.get("relation") if isinstance(data, dict) else None
            return relation if relation in {"consistent", "contradictory", "unclear"} else "unclear"
        except Exception:
            logger.warning("Could not validate clarification answer", exc_info=True)
            return "unclear"

    @staticmethod
    def _question_belief(question: dict) -> tuple[dict[str, float], dict[str, Optional[str]]]:
        options = question.get("alternatives") or []
        if not options:
            # This records the SAGE epsilon viability only; it is not a
            # normalized probability over unknown values.
            return {"<UNK>": EPSILON}, {"<UNK>": None}
        viability = parameter_specificity(specified=False, domain_size=len(options))
        weights = {f"candidate_{i}": viability for i, _ in enumerate(options)}
        outcomes = {f"candidate_{i}": str(option) for i, option in enumerate(options)}
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

    @staticmethod
    def _refine(state: dict) -> str:
        original = state["original_query"].strip()
        if state.get("language") == "it":
            additions = [
                (
                    f"Per {DIMENSION_LABELS['it'].get(dimension, dimension)}, "
                    f"l'utente ha specificato: «{item.get('values', {}).get(dimension, item['text']).strip()}»"
                    if dimension in item.get("values", {}) else
                    f"Alla domanda «{item['question']}», l'utente ha precisato: «{item['text'].strip()}»"
                )
                for item in state.get("clarifications", [])
                for dimension in (item.get("target_dimensions") or [None])
                if item.get("text", "").strip()
            ]
            label = "Chiarimento fornito dall'utente: "
        else:
            additions = [
                (
                    f"For {DIMENSION_LABELS['en'].get(dimension, dimension)}, "
                    f"the user specified: \"{item.get('values', {}).get(dimension, item['text']).strip()}\""
                    if dimension in item.get("values", {}) else
                    f"When asked \"{item['question']}\", the user clarified: \"{item['text'].strip()}\""
                )
                for item in state.get("clarifications", [])
                for dimension in (item.get("target_dimensions") or [None])
                if item.get("text", "").strip()
            ]
            label = "Clarification provided by the user: "
        if not additions:
            return original
        separator = " " if original.endswith((".", "!", "?")) else ". "
        return original + separator + label + "; ".join(additions) + "."

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
        if answer and not _is_unknown(answer):
            normalized_answer = _normalized_answer(answer)
            if pending.get("kind") == "omission_confirmation":
                # This asks about a dimension previously marked absent. Extract
                # its explicit answer directly: the generic contradiction
                # classifier can confuse independent dimensions (for example,
                # current typology "offices" and future use "student housing").
                updates = self._extract_omission_updates(state, pending, answer)
                specified = {}
                unresolved = []
                for dimension, update in updates.items():
                    state["dimensions"][dimension].update({
                        "value": update["value"], "status": update["status"],
                        "evidence": update["evidence"], "reason": None,
                        "alternatives": [],
                    })
                    if update["status"] == "SPECIFIED":
                        specified[dimension] = str(update["value"])
                    elif update["status"] == "UNCONFIRMED_ABSENT":
                        unresolved.append(dimension)
                if specified:
                    state.setdefault("clarifications", []).append({
                        "text": answer, "question": pending["question"],
                        "target_dimensions": list(specified), "values": specified,
                    })
                # Keep the grouped question alive only for dimensions the user
                # did not address; this lets a partial answer make progress.
                if unresolved:
                    for question in state.get("questions", []):
                        if question.get("kind") == "omission_confirmation" and any(
                            dimension in unresolved for dimension in question.get("target_dimensions", [])
                        ):
                            replacement = _omission_confirmation_question(unresolved, state["language"])
                            question.update(replacement)
                            break
            elif pending.get("kind") == "location_disambiguation":
                relation = self._classify_answer(state, pending, answer)
                if normalized_answer in NO_PREFERENCE_ANSWERS or not _looks_like_place_answer(answer):
                    relation = "unclear"
                # This question exists only because no city was explicit in the
                # query. A direct place-name answer fills that slot and cannot
                # conflict with a city requirement already in the state.
                elif _looks_like_place_answer(answer):
                    relation = "consistent"
                if relation != "consistent":
                    reason = (
                        "The clarification conflicts with existing requirements."
                        if relation == "contradictory"
                        else "Please provide the city for the named location."
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
                place = state["dimensions"]["L"].get("value")
                combined_location = f"{place}, {answer}" if place else answer
                state.setdefault("clarifications", []).append({
                    "text": answer, "question": pending["question"],
                    "target_dimensions": ["L"],
                    "values": {"L": combined_location},
                })
                state["dimensions"]["L"].update({
                    "value": combined_location, "status": "SPECIFIED", "evidence": answer,
                    "alternatives": [], "reason": None,
                })
            elif normalized_answer in NO_PREFERENCE_ANSWERS:
                for dimension in pending.get("target_dimensions", []):
                    state["dimensions"][dimension].update({
                        "value": None, "status": "NOT_REQUESTED", "evidence": answer,
                        "alternatives": [], "reason": None,
                    })
            elif normalized_answer in REJECTION_ANSWERS:
                for dimension in pending.get("target_dimensions", []):
                    state["dimensions"][dimension].update({
                        "value": None, "status": "MISSING_CRITICAL", "evidence": answer,
                        "reason": "The user rejected the candidate interpretations without supplying a replacement.",
                    })
                    state.setdefault("excluded_interpretations", {}).setdefault(dimension, []).extend(
                        pending.get("alternatives", [])
                    )
                state.setdefault("unanswerable_aspects", []).extend(aspect_keys)
            else:
                relation = self._classify_answer(state, pending, answer)
                if relation != "consistent":
                    reason = (
                        "The clarification conflicts with existing requirements."
                        if relation == "contradictory"
                        else "The clarification could not be reconciled safely."
                    )
                    for dimension in pending.get("target_dimensions", []):
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
                state.setdefault("clarifications", []).append({
                    "text": answer, "question": pending["question"],
                    "target_dimensions": pending.get("target_dimensions", []),
                })
                rejected = _explicitly_rejected(pending.get("alternatives", []), answer)
                if rejected:
                    for dimension in pending.get("target_dimensions", []):
                        state.setdefault("excluded_interpretations", {}).setdefault(dimension, []).extend(rejected)
                for dimension in pending.get("target_dimensions", []):
                    state["dimensions"][dimension].update({
                        "value": answer, "status": "SPECIFIED", "evidence": answer,
                        "alternatives": [], "reason": None,
                    })
        else:
            state.setdefault("unanswerable_aspects", []).extend(aspect_keys)
        self._refresh_beliefs(state)
        # An unknown/empty reply leaves the uncertainty intact. The aspect count
        # penalizes repetition; if no other question remains this returns BLOCKED.
        return self._result(state, session_id, db, row)
