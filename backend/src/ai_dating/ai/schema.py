from __future__ import annotations

import re
from typing import Any

from ai_dating.errors import AppError

EXTRACTION_PROMPT_VERSION = "extract-facts-v4"
EXTRACTION_MODEL_VERSION = "gemini-2.5-flash-lite"
JOB_TYPE_EXTRACT = "extract_profile_facts"
JOB_TYPE_EMBED = "embed_profile"
PROJECTION_SCHEMA_VERSION = "embed-proj-v1"
EMBED_DIM = 768
EMBED_KINDS = ("self", "desired_partner")
EXCERPT_MAX = 120
TOKEN_MAX = 32
REPEATABLE_MAX = 8

LEVELS = ("low", "medium", "high")
INTERESTS = (
    "travel",
    "fitness",
    "gaming",
    "cinema",
    "books",
    "technology",
    "art",
    "music",
    "cooking",
    "photography",
)
DATE_PREFERENCES = (
    "walking",
    "restaurants",
    "cinema",
    "travel",
    "home_evening",
    "short_trip",
)
VALUES = ("family", "career", "personal_growth", "freedom", "stability")
OCCUPATIONS = (
    "software_engineering",
    "design",
    "healthcare",
    "education",
    "business",
    "science",
    "arts",
    "other",
)
SOCIAL_STYLES = ("introvert", "ambivert", "extrovert")
COMMUNICATION_STYLES = ("direct", "warm", "reserved")
TRAVEL_FREQUENCIES = ("rare", "occasional", "frequent")
PREFERENCE_STRENGTHS = ("dont_care", "prefer", "strong_preference")
PROFILE_SIDES = ("self", "desired_partner")

HARD_FACT_CODES = frozenset(
    {
        "gender",
        "gender_code",
        "age",
        "birth_date",
        "orientation",
        "orientation_code",
        "city",
        "city_code",
        "search_mode",
        "relationship_goal",
        "relationship_goal_code",
        "relationship_status",
        "block",
        "safety",
    }
)

VALUE_ALIASES = {
    "restaurant": "restaurants",
    "walk": "walking",
    "walks": "walking",
    "gym": "fitness",
    "workout": "fitness",
}

FACT_CODES: dict[str, dict[str, Any]] = {
    "interest": {
        "kind": "repeatable",
        "values": INTERESTS,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Interest",
    },
    "date_preference": {
        "kind": "repeatable",
        "values": DATE_PREFERENCES,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Date preference",
    },
    "values": {
        "kind": "repeatable",
        "values": VALUES,
        "purpose": "matching_only",
        "category": "intent",
        "label": "Values",
    },
    "fitness_level": {
        "kind": "ordinal",
        "values": LEVELS,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Fitness",
    },
    "nightlife_preference": {
        "kind": "ordinal",
        "values": LEVELS,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Nightlife",
    },
    "travel_frequency": {
        "kind": "ordinal",
        "values": TRAVEL_FREQUENCIES,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Travel",
    },
    "social_style": {
        "kind": "ordinal",
        "values": SOCIAL_STYLES,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Social style",
    },
    "energy_level": {
        "kind": "ordinal",
        "values": LEVELS,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Energy",
    },
    "spontaneity": {
        "kind": "ordinal",
        "values": LEVELS,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Spontaneity",
    },
    "communication_style": {
        "kind": "ordinal",
        "values": COMMUNICATION_STYLES,
        "purpose": "matching_only",
        "category": "intent",
        "label": "Communication",
    },
    "occupation_domain": {
        "kind": "ordinal",
        "values": OCCUPATIONS,
        "purpose": "matching_only",
        "category": "lifestyle",
        "label": "Occupation",
    },
}

VISIBILITIES = ("private", "matching_only", "eligible_only")


class ExtractionRejected(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def event_source_type(db_source: str) -> str:
    return "extracted" if db_source == "free_text" else "user_entered"


def fact_category(fact_code: str) -> str:
    spec = FACT_CODES.get(fact_code)
    return spec["category"] if spec else "other"


def fact_purpose(fact_code: str) -> str:
    return FACT_CODES[fact_code]["purpose"]


def metadata_fact_keys() -> list[dict[str, Any]]:
    return [
        {
            "code": key,
            "label": spec["label"],
            "purpose": spec["purpose"],
            "kind": spec["kind"],
            "allowed": list(spec["values"]),
        }
        for key, spec in FACT_CODES.items()
    ]


def vocab_prompt() -> str:
    return "; ".join(
        f"{code} ({spec['kind']}): {', '.join(spec['values'])}"
        for code, spec in FACT_CODES.items()
    )


def normalize_excerpt(text: str | None) -> str | None:
    if text is None:
        return None
    clipped = " ".join(text.split())[:EXCERPT_MAX]
    return clipped or None


def normalize_token(raw: str) -> str | None:
    token = re.sub(r"[^\w]+", "_", raw.lower()).strip("_")
    token = re.sub(r"_+", "_", token)
    if 2 <= len(token) <= TOKEN_MAX:
        return token
    return None


def validate_visibility(value: str | None) -> str:
    vis = value or "private"
    if vis not in VISIBILITIES:
        raise AppError(422, "validation_error", "Invalid request.")
    return vis


def validate_profile_side(value: str | None) -> str:
    side = value or "self"
    if side not in PROFILE_SIDES:
        raise AppError(422, "validation_error", "Invalid request.")
    return side


def validate_preference_strength(value: str | None, *, side: str) -> str | None:
    if side != "desired_partner":
        return None
    strength = value or "prefer"
    if strength not in PREFERENCE_STRENGTHS:
        raise AppError(422, "validation_error", "Invalid request.")
    return strength


def canonical_value(fact_code: str, raw: str) -> str | None:
    spec = FACT_CODES.get(fact_code)
    if spec is None:
        return None
    token = normalize_token(raw)
    if token is None:
        return None
    token = VALUE_ALIASES.get(token, token)
    if token in spec["values"]:
        return token
    return None


def validate_fact_value(fact_code: str, value: object) -> str:
    if fact_code not in FACT_CODES:
        raise AppError(422, "validation_error", "Invalid request.")
    if not isinstance(value, str):
        raise AppError(422, "validation_error", "Invalid request.")
    token = canonical_value(fact_code, value)
    if token is None:
        raise AppError(422, "validation_error", "Invalid request.")
    return token


def _item_code(item: dict) -> str | None:
    raw = item.get("fact_code", item.get("fact_key"))
    return raw if isinstance(raw, str) else None


def _item_value(item: dict) -> str | None:
    raw = item.get("value")
    if isinstance(raw, str):
        return raw
    return None


def _confidence(raw: object) -> float | None:
    value = raw if raw is not None else 0
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if not isinstance(value, int | float) or not (0 <= float(value) <= 1):
        return None
    return round(float(value), 3)


def parse_extraction_output(payload: object) -> list[dict]:
    if not isinstance(payload, dict) or "facts" not in payload:
        raise ExtractionRejected("schema_invalid")
    facts = payload.get("facts")
    if not isinstance(facts, list):
        raise ExtractionRejected("schema_invalid")
    parsed: list[dict] = []
    seen: set[tuple[str, str]] = set()
    ordinal_seen: set[str] = set()
    counts: dict[str, int] = {}
    for item in facts:
        if not isinstance(item, dict):
            raise ExtractionRejected("schema_invalid")
        code = _item_code(item)
        if code is None or code in HARD_FACT_CODES or code not in FACT_CODES:
            continue
        raw_value = _item_value(item)
        if raw_value is None:
            continue
        value = canonical_value(code, raw_value)
        if value is None:
            continue
        spec = FACT_CODES[code]
        if spec["kind"] == "ordinal":
            if code in ordinal_seen:
                continue
            ordinal_seen.add(code)
        else:
            if counts.get(code, 0) >= REPEATABLE_MAX:
                continue
            counts[code] = counts.get(code, 0) + 1
        key = (code, value)
        if key in seen:
            continue
        seen.add(key)
        confidence = _confidence(item.get("confidence", 0))
        if confidence is None:
            continue
        excerpt = item.get("excerpt")
        if excerpt is not None and not isinstance(excerpt, str):
            continue
        strength = item.get("preference_strength")
        if strength is not None and strength not in PREFERENCE_STRENGTHS:
            strength = None
        parsed.append(
            {
                "fact_code": code,
                "value": value,
                "confidence": confidence,
                "excerpt": normalize_excerpt(excerpt),
                "preference_strength": strength,
            }
        )
    return parsed
