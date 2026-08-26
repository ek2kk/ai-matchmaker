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

export function SelfProfileStep({
  state,
  metadata,
  errors,
  fieldErrors,
  busy,
  onBack,
  onSaved,
  onError,
}: Props) {
  const profile = state.profile;
  const [displayName, setDisplayName] = useState(profile.display_name ?? "");
  const [gender, setGender] = useState(profile.gender_code ?? "");
  const [orientation, setOrientation] = useState(profile.orientation_code ?? "heterosexual");
  const [mode, setMode] = useState(profile.search_mode ?? "dating");
  const [goal, setGoal] = useState(profile.relationship_goal_code ?? "");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await api.patchOnboardingProfile({
        expected_version: profile.version,
        display_name: displayName,
        gender_code: gender,
        orientation_code: orientation,
        search_mode: mode,
        relationship_goal_code: mode === "dating" ? goal : null,
        city_code: "moscow",
      });
      await onSaved();
    } catch (error) {
      onError(error);
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      <h2 className="text-lg font-medium">About you</h2>
      <FormErrorSummary messages={errors} />
      <label className="flex flex-col gap-1 text-sm">
        Display name
        <input
          name="display_name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          aria-describedby={fieldErrors.display_name ? "display-name-error" : undefined}
          className="rounded-md border border-slate-300 px-3 py-2"
          required
          minLength={1}
          maxLength={80}
        />
      </label>
      {fieldErrors.display_name ? (
        <p id="display-name-error" className="text-sm text-red-800">
          {fieldErrors.display_name}
        </p>
      ) : null}
      <label className="flex flex-col gap-1 text-sm">
        Gender
        <select
          name="gender_code"
          value={gender}
          onChange={(e) => setGender(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2"
          required
        >
          <option value="">Select…</option>
          {metadata.genders.map((item) => (
            <option key={item.code} value={item.code}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Orientation
        <select
          name="orientation_code"
          value={orientation}
          onChange={(e) => setOrientation(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2"
          required
        >
          {metadata.orientations.map((item) => (
            <option key={item.code} value={item.code}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <p className="text-sm text-slate-600">
        Orientation is about you. It is not used to fill partner gender preferences.
      </p>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">I am here for</legend>
        {metadata.search_modes.map((item) => (
          <label key={item.code} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="search_mode"
              checked={mode === item.code}
              onChange={() => setMode(item.code)}
            />
            {item.label}
          </label>
        ))}
      </fieldset>
      {mode === "dating" ? (
        <label className="flex flex-col gap-1 text-sm">
          Relationship goal
          <select
            name="relationship_goal_code"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
            required
          >
            <option value="">Select…</option>
            {metadata.relationship_goals.map((item) => (
              <option key={item.code} value={item.code}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <p className="text-sm text-slate-600">City: Moscow. Matching is limited to this city for now.</p>
      <StepNav onBack={onBack} busy={busy} />
    </form>
  );
}
