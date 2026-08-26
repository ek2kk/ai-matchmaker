import { FormEvent, useState } from "react";

import type { OnboardingState } from "@/lib/api";
import { api } from "@/lib/api";

import { FormErrorSummary } from "./FormErrorSummary";
import { StepNav } from "./StepNav";

type Props = {
  state: OnboardingState;
  errors: string[];
  busy: boolean;
  onBack?: () => void;
  onSaved: () => Promise<void>;
  onError: (error: unknown) => void;
};

export function DiscoverabilityStep({
  state,
  errors,
  busy,
  onBack,
  onSaved,
  onError,
}: Props) {
  const [discoverable, setDiscoverable] = useState(state.privacy.discoverable);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      if (discoverable !== state.privacy.discoverable) {
        await api.patchPrivacy({
          expected_version: state.privacy.version,
          discoverable,
        });
      }
      const latest = await api.getOnboarding();
      await api.completeOnboarding({
        expected_profile_version: latest.profile.version,
        expected_preferences_version: latest.preferences.version,
      });
      await onSaved();
    } catch (error) {
      onError(error);
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      <h2 className="text-lg font-medium">Discoverability</h2>
      <FormErrorSummary messages={errors} />
      <ul className="rounded-lg bg-white p-4 text-sm shadow-sm">
        <li>Name: {state.profile.display_name}</li>
        <li>City: {state.profile.city_code}</li>
        <li>Looking for: {state.preferences.accepted_gender_codes.join(", ")}</li>
        <li>
          Ages {state.preferences.age_min}–{state.preferences.age_max}, up to{" "}
          {state.preferences.max_distance_km} km
        </li>
      </ul>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={discoverable}
          onChange={(e) => setDiscoverable(e.target.checked)}
          required
        />
        Make my profile discoverable.
      </label>
      <StepNav onBack={onBack} continueLabel="Finish onboarding" busy={busy} />
    </form>
  );
}
