from __future__ import annotations

import json
import re

from ai_dating.ai.schema import ExtractionRejected

_PROHIBITED = re.compile(
    r"\b("
    r"diabetes|cancer|hiv|hepatitis|disability|pregnant|"
    r"jewish|muslim|christian|hindu|buddhist|atheist|"
    r"ethnicity|slavic|caucasian|asian|african|"
    r"democrat|republican|communist|liberal|conservative|"
    r"salary|income|mortgage|debt|"
    r"passport|ssn|street address|gps|"
    r"fingerprint|faceid|biometr"
    r")\b",
    re.IGNORECASE,
)


def scan_sensitive(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ExtractionRejected("schema_invalid")
    facts = payload.get("facts")
    if not isinstance(facts, list):
        raise ExtractionRejected("schema_invalid")
    for item in facts:
        if not isinstance(item, dict):
            raise ExtractionRejected("schema_invalid")
        blob = json.dumps(
            {
                "fact_code": item.get("fact_code", item.get("fact_key")),
                "value": item.get("value"),
            },
            ensure_ascii=True,
        )
        if _PROHIBITED.search(blob):
            raise ExtractionRejected("safety_rejected")
