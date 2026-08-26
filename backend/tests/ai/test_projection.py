from types import SimpleNamespace

from ai_dating.ai.projection import build_projection
from ai_dating.ai.schema import PROJECTION_SCHEMA_VERSION


def test_self_projection_is_ordered_and_omits_private_fields():
    profile = SimpleNamespace(
        search_mode="dating",
        gender_code="woman",
        orientation_code="heterosexual",
        city_code="moscow",
        relationship_goal_code="serious_relationship",
        display_name="Alex",
        date_of_birth="2000-01-15",
    )
    answers = [
        SimpleNamespace(prompt_code="self_weekend", answer_text=" Quiet films. "),
        SimpleNamespace(prompt_code="self_about", answer_text="I cook."),
        SimpleNamespace(prompt_code="partner_who", answer_text="Kind."),
    ]
    facts = [
        SimpleNamespace(
            profile_side="self",
            fact_code="interest",
            value="music",
            preference_strength=None,
        ),
        SimpleNamespace(
            profile_side="self",
            fact_code="interest",
            value="cooking",
            preference_strength=None,
        ),
        SimpleNamespace(
            profile_side="desired_partner",
            fact_code="interest",
            value="travel",
            preference_strength="prefer",
        ),
    ]
    built = build_projection(
        "self", profile=profile, prefs=None, answers=answers, facts=facts
    )
    assert built["projection_schema_version"] == PROJECTION_SCHEMA_VERSION
    text = built["text"]
    assert "search_mode: dating" in text
    assert "answer self_about: I cook." in text
    assert "fact interest: cooking" in text
    assert "Kind." not in text
    assert "2000-01-15" not in text
    assert "Alex" not in text
    fields = built["fields"]
    assert fields.index("fact interest: cooking") < fields.index("fact interest: music")


def test_desired_projection_uses_preferences_and_partner_side():
    prefs = SimpleNamespace(
        search_mode="dating",
        accepted_gender_codes=["man"],
        age_min=21,
        age_max=35,
        max_distance_km=25,
        city_codes=["moscow"],
        relationship_goal_codes=["serious_relationship"],
    )
    answers = [
        SimpleNamespace(prompt_code="partner_who", answer_text="Curious."),
        SimpleNamespace(prompt_code="self_about", answer_text="I cook."),
    ]
    facts = [
        SimpleNamespace(
            profile_side="desired_partner",
            fact_code="interest",
            value="travel",
            preference_strength="prefer",
        )
    ]
    built = build_projection(
        "desired_partner",
        profile=SimpleNamespace(),
        prefs=prefs,
        answers=answers,
        facts=facts,
    )
    text = built["text"]
    assert "accepted_genders: man" in text
    assert "answer partner_who: Curious." in text
    assert "fact interest: travel (prefer)" in text
    assert "I cook." not in text
