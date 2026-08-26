import { FormEvent, useEffect, useState } from "react";

import type { CalibrationSession, OnboardingMetadata, OnboardingState } from "@/lib/api";
import { api } from "@/lib/api";
import { granted } from "@/lib/onboarding";

import { FormErrorSummary } from "./FormErrorSummary";
import { StepNav } from "./StepNav";

type Props = {
  state: OnboardingState;
  metadata: OnboardingMetadata;
  errors: string[];
  busy: boolean;
  onBack?: () => void;
  onSaved: () => Promise<void>;
  onError: (error: unknown) => void;
};

export function CalibrationStep({
  state,
  metadata,
  errors,
  busy,
  onBack,
  onSaved,
  onError,
}: Props) {
  const [session, setSession] = useState<CalibrationSession | null>(null);
  const [consent, setConsent] = useState(granted(state, "calibration"));

  useEffect(() => {
    api.createCalibrationSession().then(setSession).catch(onError);
    // Parent onError is not memoized.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function choose(demoPairId: string, selection: "left" | "right" | "neither") {
    if (!session) {
      return;
    }
    const next = await api.postCalibrationChoice(session.calibration_session_id, {
      demo_pair_id: demoPairId,
      selection,
    });
    setSession(next);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) {
      return;
    }
    try {
      if (consent && !granted(state, "calibration")) {
        await api.postConsent({
          purpose: "calibration",
          policy_version: metadata.policy_version,
          decision: "granted",
        });
      }
      await api.completeCalibrationSession(session.calibration_session_id, "complete");
      await onSaved();
    } catch (error) {
      onError(error);
    }
  }

  async function skip() {
    if (!session) {
      return;
    }
    try {
      await api.completeCalibrationSession(session.calibration_session_id, "skip");
      await onSaved();
    } catch (error) {
      onError(error);
    }
  }

  async function clearData() {
    try {
      await api.postConsent({
        purpose: "calibration",
        policy_version: metadata.policy_version,
        decision: "withdrawn",
      });
      setConsent(false);
      const next = await api.createCalibrationSession();
      setSession(next);
    } catch (error) {
      onError(error);
    }
  }

  if (!session) {
    return <p className="text-sm text-slate-600">Loading demo comparisons…</p>;
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      <h2 className="text-lg font-medium">Preference calibration</h2>
      <p className="text-sm text-slate-600">
        These cards are labelled “{session.label}”. Choices never create likes, passes, or matches.
      </p>
      <FormErrorSummary messages={errors} />
      {(session.pairs ?? []).map((pair) => {
        const current = (session.choices ?? []).find((item) => item.demo_pair_id === pair.demo_pair_id);
        return (
          <fieldset key={pair.demo_pair_id} className="rounded-lg border border-slate-200 p-4">
            <legend className="text-xs uppercase tracking-wide text-slate-500">{pair.label}</legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {(["left", "right"] as const).map((side) => (
                <button
                  key={side}
                  type="button"
                  onClick={() => choose(pair.demo_pair_id, side).catch(onError)}
                  className={`rounded-md border p-3 text-left text-sm ${
                    current?.selection === side ? "border-slate-900" : "border-slate-200"
                  }`}
                >
                  <p className="font-medium">{pair[side].display_name}</p>
                  <p className="mt-1 text-slate-600">{pair[side].summary}</p>
                </button>
              ))}
            </div>
            <button
              type="button"
              className="mt-2 text-sm underline"
              onClick={() => choose(pair.demo_pair_id, "neither").catch(onError)}
            >
              Neither
            </button>
          </fieldset>
        );
      })}
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        I consent to using these demo comparisons as a soft preference signal.
      </label>
      <div className="flex flex-wrap gap-3">
        <button type="button" className="rounded-md border border-slate-300 px-4 py-2 text-sm" onClick={skip}>
          Skip calibration
        </button>
        <button type="button" className="rounded-md border border-slate-300 px-4 py-2 text-sm" onClick={clearData}>
          Clear calibration data
        </button>
      </div>
      <StepNav onBack={onBack} continueLabel="Save comparisons" busy={busy} />
    </form>
  );
}
