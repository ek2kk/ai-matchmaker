from __future__ import annotations

from ai_dating.ai.schema import PROJECTION_SCHEMA_VERSION
from ai_dating.onboarding.vocab import DESIRED_PROMPT_CODES, SELF_PROMPT_CODES
from ai_dating.profiles.models import (
    DatingPreferences,
    Profile,
    ProfileAnswer,
    ProfileFact,
)


def build_projection(
    kind: str,
    *,
    profile: Profile,
    prefs: DatingPreferences | None,
    answers: list[ProfileAnswer],
    facts: list[ProfileFact],
) -> dict[str, str | list[str]]:
    if kind == "self":
        lines = _self_lines(profile, answers, facts)
    elif kind == "desired_partner":
        lines = _desired_lines(prefs, answers, facts)
    else:
        raise ValueError(kind)
    return {
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "kind": kind,
        "text": "\n".join(lines),
        "fields": lines,
    }


def _self_lines(
    profile: Profile, answers: list[ProfileAnswer], facts: list[ProfileFact]
) -> list[str]:
    lines = [
        f"search_mode: {profile.search_mode}",
        f"gender: {profile.gender_code}",
        f"orientation: {profile.orientation_code}",
        f"city: {profile.city_code}",
    ]
    if profile.relationship_goal_code:
        lines.append(f"relationship_goal: {profile.relationship_goal_code}")
    lines.extend(_answer_lines(answers, SELF_PROMPT_CODES))
    lines.extend(_fact_lines(facts, "self"))
    return lines


def _desired_lines(
    prefs: DatingPreferences | None,
    answers: list[ProfileAnswer],
    facts: list[ProfileFact],
) -> list[str]:
    lines: list[str] = []
    if prefs is not None:
        lines.append(f"search_mode: {prefs.search_mode}")
        lines.append(
            "accepted_genders: " + ",".join(sorted(prefs.accepted_gender_codes))
        )
        lines.append(f"age_min: {prefs.age_min}")
        lines.append(f"age_max: {prefs.age_max}")
        lines.append(f"max_distance_km: {prefs.max_distance_km}")
        lines.append("cities: " + ",".join(sorted(prefs.city_codes)))
        if prefs.relationship_goal_codes:
            lines.append(
                "relationship_goals: " + ",".join(sorted(prefs.relationship_goal_codes))
            )
    lines.extend(_answer_lines(answers, DESIRED_PROMPT_CODES))
    lines.extend(_fact_lines(facts, "desired_partner"))
    return lines


def _answer_lines(answers: list[ProfileAnswer], codes: tuple[str, ...]) -> list[str]:
    wanted = set(codes)
    rows = [row for row in answers if row.prompt_code in wanted]
    rows.sort(key=lambda row: row.prompt_code)
    return [f"answer {row.prompt_code}: {row.answer_text.strip()}" for row in rows]


def _fact_lines(facts: list[ProfileFact], side: str) -> list[str]:
    rows = [row for row in facts if row.profile_side == side]
    rows.sort(key=lambda row: (row.fact_code, row.value))
    out: list[str] = []
    for row in rows:
        line = f"fact {row.fact_code}: {row.value}"
        if row.preference_strength:
            line += f" ({row.preference_strength})"
        out.append(line)
    return out
