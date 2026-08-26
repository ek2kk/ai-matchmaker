from __future__ import annotations

from datetime import UTC, date, datetime

from ai_dating.errors import AppError
from ai_dating.onboarding.vocab import (
    ANSWER_MAX,
    BIO_MAX,
    CITY_CODES,
    DISPLAY_NAME_MAX,
    DISTANCE_MAX_KM,
    DISTANCE_MIN_KM,
    GENDER_CODES,
    ORIENTATION_CODES,
    PREF_AGE_MAX,
    PREF_AGE_MIN,
    PROMPT_CODES,
    PUBLIC_AREA_CODES,
    RELATIONSHIP_GOAL_CODES,
    SEARCH_MODES,
    SELF_MIN_AGE,
)


def years_old(dob: date, today: date | None = None) -> int:
    today = today or datetime.now(UTC).date()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def require_21_plus(dob: date) -> None:
    if years_old(dob) < SELF_MIN_AGE:
        raise AppError(
            422,
            "validation_error",
            "You must be 21 or older.",
            details={"fields": {"date_of_birth": "You must be 21 or older."}},
        )


def validate_display_name(value: str) -> str:
    name = value.strip()
    if not (1 <= len(name) <= DISPLAY_NAME_MAX):
        raise AppError(
            422,
            "validation_error",
            "Display name must be 1 to 80 characters.",
            details={"fields": {"display_name": "Must be 1 to 80 characters."}},
        )
    return name


def validate_bio(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > BIO_MAX:
        raise AppError(
            422,
            "validation_error",
            "Bio is too long.",
            details={"fields": {"bio": "Must be at most 2000 characters."}},
        )
    return value


def validate_code(field: str, value: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise AppError(
            422,
            "validation_error",
            "Invalid request.",
            details={"fields": {field: "Choose a listed option."}},
        )
    return value


def validate_codes(
    field: str,
    values: list[str],
    allowed: tuple[str, ...],
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not values:
        if allow_empty:
            return []
        raise AppError(
            422,
            "validation_error",
            "Select at least one option.",
            details={"fields": {field: "Select at least one option."}},
        )
    seen: list[str] = []
    for item in values:
        if item not in allowed:
            raise AppError(
                422,
                "validation_error",
                "Invalid request.",
                details={"fields": {field: "Choose listed options only."}},
            )
        if item not in seen:
            seen.append(item)
    return seen


def validate_location(latitude: float, longitude: float) -> tuple[float, float]:
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise AppError(
            422,
            "validation_error",
            "Location is invalid.",
            details={
                "fields": {"location": "Latitude and longitude are out of range."}
            },
        )
    return latitude, longitude


def validate_age_range(age_min: int, age_max: int) -> tuple[int, int]:
    if not (PREF_AGE_MIN <= age_min <= age_max <= PREF_AGE_MAX):
        raise AppError(
            422,
            "validation_error",
            "Age range is invalid.",
            details={
                "fields": {
                    "age_min": (
                        f"Must be {PREF_AGE_MIN}–{PREF_AGE_MAX} "
                        "and not greater than max."
                    ),
                    "age_max": (
                        f"Must be {PREF_AGE_MIN}–{PREF_AGE_MAX} and not less than min."
                    ),
                }
            },
        )
    return age_min, age_max


def validate_distance(km: int) -> int:
    if not (DISTANCE_MIN_KM <= km <= DISTANCE_MAX_KM):
        raise AppError(
            422,
            "validation_error",
            "Distance is invalid.",
            details={
                "fields": {
                    "max_distance_km": (
                        f"Must be {DISTANCE_MIN_KM} to {DISTANCE_MAX_KM} km."
                    )
                }
            },
        )
    return km


def validate_answer_text(value: str) -> str:
    text = value.strip()
    if not (1 <= len(text) <= ANSWER_MAX):
        raise AppError(
            422,
            "validation_error",
            "Answer must be 1 to 1000 characters.",
            details={"fields": {"answer_text": "Must be 1 to 1000 characters."}},
        )
    return text


def gender_code(value: str) -> str:
    return validate_code("gender_code", value, GENDER_CODES)


def orientation_code(value: str) -> str:
    return validate_code("orientation_code", value, ORIENTATION_CODES)


def relationship_goal_code(value: str) -> str:
    return validate_code("relationship_goal_code", value, RELATIONSHIP_GOAL_CODES)


def search_mode(value: str) -> str:
    return validate_code("search_mode", value, SEARCH_MODES)


def city_code(value: str) -> str:
    return validate_code("city_code", value, CITY_CODES)


def public_area_code(value: str) -> str:
    return validate_code("public_area_code", value, PUBLIC_AREA_CODES)


def prompt_code(value: str) -> str:
    return validate_code("prompt_code", value, PROMPT_CODES)


def accepted_genders(values: list[str]) -> list[str]:
    return validate_codes("accepted_gender_codes", values, GENDER_CODES)


def relationship_goals(values: list[str], *, allow_empty: bool = False) -> list[str]:
    return validate_codes(
        "relationship_goal_codes",
        values,
        RELATIONSHIP_GOAL_CODES,
        allow_empty=allow_empty,
    )


def city_codes(values: list[str]) -> list[str]:
    return validate_codes("city_codes", values, CITY_CODES)
