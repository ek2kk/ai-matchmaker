import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { CalibrationStep } from "@/components/onboarding/CalibrationStep";
import { DiscoverabilityStep } from "@/components/onboarding/DiscoverabilityStep";
import { EligibilityStep } from "@/components/onboarding/EligibilityStep";
import { FactsReviewStep } from "@/components/onboarding/FactsReviewStep";
import { PartnerPreferencesStep } from "@/components/onboarding/PartnerPreferencesStep";
import { PromptStep } from "@/components/onboarding/PromptStep";
import { SelfProfileStep } from "@/components/onboarding/SelfProfileStep";
import { VersionConflictDialog } from "@/components/onboarding/VersionConflictDialog";
import { api, type OnboardingMetadata, type OnboardingState } from "@/lib/api";
import { ApiError, isVersionConflict } from "@/lib/http";
import { errorSummary, fieldMessages, firstIncompleteStep, STEPS, type StepId } from "@/lib/onboarding";
import { setSession } from "@/lib/session";

export function OnboardingPage() {
  const navigate = useNavigate();
  const [state, setState] = useState<OnboardingState | null>(null);
  const [metadata, setMetadata] = useState<OnboardingMetadata | null>(null);
  const [step, setStep] = useState<StepId>("eligibility");
  const [errors, setErrors] = useState<string[]>([]);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(
    async (selectStep = false) => {
      const [nextState, nextMeta] = await Promise.all([
        api.getOnboarding(),
        api.getOnboardingMetadata(),
      ]);
      setState(nextState);
      setMetadata(nextMeta);
      if (nextState.onboarding_completed) {
        navigate("/onboarding/pending");
        return nextState;
      }
      if (selectStep) {
        setStep(firstIncompleteStep(nextState.gates));
      }
      return nextState;
    },
    [navigate],
  );

  useEffect(() => {
    load(true).catch((err: unknown) => {
      if (err instanceof ApiError && err.status === 401) {
        setSession(null);
        navigate("/login");
        return;
      }
      setLoadError(err instanceof ApiError ? err.message : "Could not load onboarding.");
    });
  }, [load, navigate]);

  function handleError(error: unknown) {
    setBusy(false);
    if (isVersionConflict(error)) {
      setConflict(true);
      setErrors([]);
      setFieldErrors({});
      return;
    }
    setConflict(false);
    setFieldErrors(fieldMessages(error));
    setErrors(errorSummary(error));
  }

  async function saved() {
    setBusy(false);
    setErrors([]);
    setFieldErrors({});
    setConflict(false);
    const next = await load(false);
    if (!next || next.onboarding_completed) {
      return;
    }
    const index = STEPS.indexOf(step);
    const following = STEPS[index + 1];
    setStep(following ?? firstIncompleteStep(next.gates));
  }

  function back() {
    const index = STEPS.indexOf(step);
    if (index > 0) {
      setStep(STEPS[index - 1]);
      setErrors([]);
      setFieldErrors({});
    }
  }

  if (loadError) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-4 p-6">
        <p className="text-sm text-red-800" role="alert">
          {loadError}
        </p>
      </main>
    );
  }
  if (!state || !metadata) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center p-6">
        <p className="text-slate-600">Loading onboarding…</p>
      </main>
    );
  }

  const shared = {
    state,
    metadata,
    errors,
    fieldErrors,
    busy,
    onBack: step === "eligibility" ? undefined : back,
    onSaved: async () => {
      setBusy(true);
      await saved();
    },
    onError: handleError,
  };

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Set up your profile</h1>
        <p className="text-sm text-slate-600">
          Step {STEPS.indexOf(step) + 1} of {STEPS.length}. Completion {state.completion_percent}%.
        </p>
      </div>
      {conflict ? (
        <VersionConflictDialog
          onReload={() => {
            setConflict(false);
            load(true).catch(handleError);
          }}
        />
      ) : null}
      {step === "eligibility" ? <EligibilityStep {...shared} /> : null}
      {step === "self" ? <SelfProfileStep {...shared} /> : null}
      {step === "partner" ? <PartnerPreferencesStep {...shared} /> : null}
      {step === "prompt" ? <PromptStep {...shared} /> : null}
      {step === "facts" ? <FactsReviewStep {...shared} /> : null}
      {step === "calibration" ? <CalibrationStep {...shared} /> : null}
      {step === "discoverability" ? (
        <DiscoverabilityStep
          state={state}
          errors={errors}
          busy={busy}
          onBack={back}
          onSaved={async () => navigate("/onboarding/pending")}
          onError={handleError}
        />
      ) : null}
    </main>
  );
}
