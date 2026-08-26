from __future__ import annotations

from ai_dating.ai.schema import metadata_fact_keys

FLOW_VERSION = "v2"

GENDER_CODES = ("man", "woman")
ORIENTATION_CODES = ("heterosexual",)
SEARCH_MODES = ("dating", "friendship")
RELATIONSHIP_GOAL_CODES = (
    "serious_relationship",
    "friends_with_benefits",
    "unsure",
)
RELATIONSHIP_STATUS_CODES = ("single",)
CITY_CODES = ("moscow",)
PUBLIC_AREA_CODES = (
    "moscow_central",
    "moscow_north",
    "moscow_south",
    "moscow_east",
    "moscow_west",
)
SELF_PROMPT_CODES = ("self_about", "self_weekend", "self_people")
DESIRED_PROMPT_CODES = (
    "partner_who",
    "partner_together",
    "partner_relationship",
)
PROMPT_CODES = SELF_PROMPT_CODES + DESIRED_PROMPT_CODES
UI_SELF_PROMPT_CODES = ("self_about", "self_weekend")
UI_DESIRED_PROMPT_CODES = ("partner_who", "partner_together")
STEP_CODES = (
    "account",
    "profile",
    "preferences",
    "photos",
    "facts_review",
    "calibration",
)
TASK_STEP_CODES = ("account", "profile", "preferences")
CALIBRATION_VERSION = "v1"
REASON_CODES = (
    "shared_interests",
    "communication_style",
    "activity_style",
    "schedule_fit",
    "other",
)

ANSWER_VISIBILITY = ("private", "matching_only", "eligible_only")
PROFILE_VISIBILITY = ("hidden", "eligible", "paused")
MODERATION_STATES = ("pending", "approved", "rejected", "suspended")

SELF_MIN_AGE = 21
PREF_AGE_MIN = 18
PREF_AGE_MAX = 120
DISTANCE_MIN_KM = 1
DISTANCE_MAX_KM = 500
DISPLAY_NAME_MAX = 80
BIO_MAX = 2000
ANSWER_MAX = 1000
DEFAULT_CITY_CODE = "moscow"
DEFAULT_PUBLIC_AREA = "moscow_central"
DEFAULT_SEARCH_MODE = "dating"
DEFAULT_RELATIONSHIP_STATUS = "single"
MOSCOW_LATITUDE = 55.75
MOSCOW_LONGITUDE = 37.62

PROMPT_LABELS = {
    "self_about": "Tell me a bit about yourself and what you like doing.",
    "self_weekend": "What does your ideal weekend usually look like?",
    "self_people": "What do you especially like in people and conversation?",
    "partner_who": "What kind of person would you like to meet?",
    "partner_together": "How would you typically spend time together?",
    "partner_relationship": "What matters to you in a relationship?",
}


def prompt_side(code: str) -> str:
    if code in SELF_PROMPT_CODES:
        return "self"
    return "desired_partner"


def _codes(values: tuple[str, ...], labels: dict[str, str]) -> list[dict[str, str]]:
    return [{"code": code, "label": labels[code]} for code in values]


def metadata_payload(policy_version: str) -> dict:
    return {
        "flow_version": FLOW_VERSION,
        "policy_version": policy_version,
        "genders": _codes(GENDER_CODES, {"man": "Man", "woman": "Woman"}),
        "orientations": _codes(ORIENTATION_CODES, {"heterosexual": "Heterosexual"}),
        "search_modes": _codes(
            SEARCH_MODES, {"dating": "Dating", "friendship": "Friendship"}
        ),
        "relationship_goals": _codes(
            RELATIONSHIP_GOAL_CODES,
            {
                "serious_relationship": "Serious relationship",
                "friends_with_benefits": "Friends with benefits",
                "unsure": "Not sure yet",
            },
        ),
        "cities": _codes(CITY_CODES, {"moscow": "Moscow"}),
        "public_areas": _codes(
            PUBLIC_AREA_CODES,
            {
                "moscow_central": "Moscow · Centre",
                "moscow_north": "Moscow · North",
                "moscow_south": "Moscow · South",
                "moscow_east": "Moscow · East",
                "moscow_west": "Moscow · West",
            },
        ),
        "prompts": [
            {
                "code": code,
                "label": PROMPT_LABELS[code],
                "side": prompt_side(code),
            }
            for code in PROMPT_CODES
        ],
        "ui_prompts": {
            "self": list(UI_SELF_PROMPT_CODES),
            "desired_partner": list(UI_DESIRED_PROMPT_CODES),
        },
        "fact_keys": metadata_fact_keys(),
        "calibration_version": CALIBRATION_VERSION,
        "calibration_reason_codes": _codes(
            REASON_CODES,
            {
                "shared_interests": "Shared interests",
                "communication_style": "Communication style",
                "activity_style": "Activity style",
                "schedule_fit": "Schedule fit",
                "other": "Other",
            },
        ),
        "age": {"min": PREF_AGE_MIN, "max": PREF_AGE_MAX, "self_min": SELF_MIN_AGE},
        "distance_km": {"min": DISTANCE_MIN_KM, "max": DISTANCE_MAX_KM},
    }
