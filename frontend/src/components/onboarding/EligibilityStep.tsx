import { FormEvent, useState } from "react";

import type { OnboardingMetadata, OnboardingState } from "@/lib/api";
import { api } from "@/lib/api";
import { granted } from "@/lib/onboarding";

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

export function EligibilityStep({
  state,
  metadata,
  errors,
  fieldErrors,
  busy,
  onBack,
  onSaved,
  onError,
}: Props) {
  const [dob, setDob] = useState(state.profile.date_of_birth ?? "");
  const [terms, setTerms] = useState(granted(state, "terms_privacy"));
  const [aiMatching, setAiMatching] = useState(granted(state, "ai_matching"));

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await api.patchOnboardingProfile({
        expected_version: state.profile.version,
        date_of_birth: dob,
      });
      if (terms && !granted(state, "terms_privacy")) {
        await api.postConsent({
          purpose: "terms_privacy",
          policy_version: metadata.policy_version,
          decision: "granted",
        });
      }
      if (aiMatching && !granted(state, "ai_matching")) {
        await api.postConsent({
          purpose: "ai_matching",
          policy_version: metadata.policy_version,
          decision: "granted",
        });
      }
      await onSaved();
    } catch (error) {
      onError(error);
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      <h2 className="text-lg font-medium">Eligibility</h2>
      <FormErrorSummary messages={errors} />
      <label className="flex flex-col gap-1 text-sm">
        Date of birth
        <input
          id="date_of_birth"
          name="date_of_birth"
          type="date"
          value={dob}
          onChange={(e) => setDob(e.target.value)}
          aria-describedby={fieldErrors.date_of_birth ? "dob-error" : undefined}
          className="rounded-md border border-slate-300 px-3 py-2"
          required
        />
      </label>
      {fieldErrors.date_of_birth ? (
        <p id="dob-error" className="text-sm text-red-800">
          {fieldErrors.date_of_birth}
        </p>
      ) : (
        <p className="text-sm text-slate-600">You must be {metadata.age.self_min} or older.</p>
      )}
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={terms}
          onChange={(e) => setTerms(e.target.checked)}
          required
        />
        I agree to the terms and privacy policy.
      </label>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={aiMatching}
          onChange={(e) => setAiMatching(e.target.checked)}
          required
        />
        I consent to AI matching on my profile.
      </label>
      <StepNav onBack={onBack} busy={busy} />
    </form>
  );
}
