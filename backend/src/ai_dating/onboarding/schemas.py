from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class LocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float
    longitude: float


class OnboardingProfilePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    display_name: str | None = None
    gender_code: str | None = None
    orientation_code: str | None = None
    search_mode: str | None = None
    relationship_goal_code: str | None = None
    city_code: str | None = None
    location: LocationIn | None = None
    public_area_code: str | None = None
    date_of_birth: date | None = None


class OnboardingPreferencesPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    search_mode: str | None = None
    accepted_gender_codes: list[str] | None = None
    age_min: int | None = None
    age_max: int | None = None
    max_distance_km: int | None = None
    city_codes: list[str] | None = None
    relationship_goal_codes: list[str] | None = None


class OnboardingCompleteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_profile_version: int
    expected_preferences_version: int


class CalibrationSessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CalibrationChoiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    demo_pair_id: str
    selection: str
    reason_code: str | None = None


class CalibrationCompleteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
