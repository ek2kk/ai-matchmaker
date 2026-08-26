import type { OnboardingGates, OnboardingState } from "./api";
import { ApiError } from "./http";

export const STEPS = [
  "eligibility",
  "self",
  "partner",
  "prompt",
  "facts",
  "calibration",
  "discoverability",
] as const;
export type StepId = (typeof STEPS)[number];

export function firstIncompleteStep(gates: OnboardingGates): StepId {
  if (!gates.dob_21_plus || !gates.terms_privacy || !gates.ai_matching) {
    return "eligibility";
  }
  if (!gates.self_profile) {
    return "self";
  }
  if (!gates.preferences) {
    return "partner";
  }
  if (!gates.prompt_answer) {
    return "prompt";
  }
  if (!gates.facts_reviewed) {
    return "facts";
  }
  if (!gates.calibration_done) {
    return "calibration";
  }
  return "discoverability";
}

export function fieldMessages(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !error.details) {
    return {};
  }
  const fields = error.details.fields;
  if (!fields || typeof fields !== "object") {
    return {};
  }
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(fields)) {
    if (typeof value === "string") {
      out[key] = value;
    }
  }
  return out;
}

export function errorSummary(error: unknown): string[] {
  if (!(error instanceof ApiError)) {
    return ["Something went wrong."];
  }
  const messages = [error.message];
  const fields = fieldMessages(error);
  for (const value of Object.values(fields)) {
    if (!messages.includes(value)) {
      messages.push(value);
    }
  }
  const gates = error.details?.gates;
  if (gates && typeof gates === "object") {
    for (const value of Object.values(gates)) {
      if (typeof value === "string" && !messages.includes(value)) {
        messages.push(value);
      }
    }
  }
  return messages;
}

export function granted(state: OnboardingState, purpose: string): boolean {
  const row = state.privacy?.consents?.find((item) => item.purpose === purpose);
  return row?.decision === "granted";
}
