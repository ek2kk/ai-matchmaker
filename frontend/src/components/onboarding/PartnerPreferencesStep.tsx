import { FormEvent, useState } from "react";

import type { OnboardingMetadata, OnboardingState } from "@/lib/api";
import { api } from "@/lib/api";

import { FormErrorSummary } from "./FormErrorSummary";
import { StepNav } from "./StepNav";

type Props = {
  state: OnboardingState;
  metadata: OnboardingMetadata;
  errors: string[];
  fieldErrors: Record<string, string>;
  busy: boolean;
  onBack?: () => void;
  onSaved: () => Promise<void>;
  onError: (error: unknown) => void;
};

function toggle(list: string[], code: string, on: boolean): string[] {
  if (on) {
    return list.includes(code) ? list : [...list, code];
  }
  return list.filter((item) => item !== code);
}

export function PartnerPreferencesStep({
  state,
  metadata,
  errors,
  fieldErrors,
  busy,
  onBack,
  onSaved,
  onError,
}: Props) {
  const prefs = state.preferences;
  const mode = state.profile.search_mode ?? "dating";
  const [genders, setGenders] = useState(prefs.accepted_gender_codes);
  const [goals, setGoals] = useState(prefs.relationship_goal_codes);
  const [ageMin, setAgeMin] = useState(String(prefs.age_min ?? 21));
  const [ageMax, setAgeMax] = useState(String(prefs.age_max ?? 35));
  const [distance, setDistance] = useState(String(prefs.max_distance_km ?? 25));

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await api.patchOnboardingPreferences({
        expected_version: prefs.version,
        search_mode: mode,
        accepted_gender_codes: genders,
        relationship_goal_codes: mode === "dating" ? goals : [],
        city_codes: ["moscow"],
        age_min: Number(ageMin),
        age_max: Number(ageMax),
        max_distance_km: Number(distance),
      });
      await onSaved();
    } catch (error) {
      onError(error);
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      <h2 className="text-lg font-medium">Desired partner</h2>
      <p className="text-sm text-slate-600">
        Matching is reciprocal: both of you must accept each other&apos;s gender, age, city and
        {mode === "dating" ? " goals" : " search mode"}. Choose genders explicitly — orientation is
        not converted into a preference.
      </p>
      <FormErrorSummary messages={errors} />
      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">Accepted genders</legend>
        {metadata.genders.map((item) => (
          <label key={item.code} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={genders.includes(item.code)}
              onChange={(e) => setGenders(toggle(genders, item.code, e.target.checked))}
            />
            {item.label}
          </label>
        ))}
      </fieldset>
      {fieldErrors.accepted_gender_codes ? (
        <p className="text-sm text-red-800">{fieldErrors.accepted_gender_codes}</p>
      ) : null}
      <label className="flex flex-col gap-1 text-sm">
        Minimum age
        <input
          name="age_min"
          type="number"
          min={metadata.age.min}
          max={metadata.age.max}
          value={ageMin}
          onChange={(e) => setAgeMin(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2"
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Maximum age
        <input
          name="age_max"
          type="number"
          min={metadata.age.min}
          max={metadata.age.max}
          value={ageMax}
          onChange={(e) => setAgeMax(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2"
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Maximum distance ({distance} km)
        <input
          name="max_distance_km"
          type="range"
          min={metadata.distance_km.min}
          max={metadata.distance_km.max}
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
        />
      </label>
      {mode === "dating" ? (
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium">Accepted goals</legend>
          {metadata.relationship_goals.map((item) => (
            <label key={item.code} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={goals.includes(item.code)}
                onChange={(e) => setGoals(toggle(goals, item.code, e.target.checked))}
              />
              {item.label}
            </label>
          ))}
        </fieldset>
      ) : (
        <p className="text-sm text-slate-600">Friendship matching does not use relationship goals.</p>
      )}
      {fieldErrors.relationship_goal_codes ? (
        <p className="text-sm text-red-800">{fieldErrors.relationship_goal_codes}</p>
      ) : null}
      <StepNav onBack={onBack} busy={busy} />
    </form>
  );
}
