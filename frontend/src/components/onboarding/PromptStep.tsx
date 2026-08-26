import { FormEvent, useState } from "react";

import type { OnboardingMetadata, OnboardingState, PromptMeta } from "@/lib/api";
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

function byCode(prompts: PromptMeta[], codes: string[]): PromptMeta[] {
  const wanted = new Set(codes);
  return prompts.filter((item) => wanted.has(item.code));
}

export function PromptStep({
  state,
  metadata,
  errors,
  fieldErrors,
  busy,
  onBack,
  onSaved,
  onError,
}: Props) {
  const existing = Object.fromEntries(state.profile.answers.map((row) => [row.prompt_code, row.answer_text]));
  const selfCodes = metadata.ui_prompts?.self ?? metadata.prompts.filter((item) => item.side === "self").slice(0, 2).map((item) => item.code);
  const partnerCodes =
    metadata.ui_prompts?.desired_partner ??
    metadata.prompts.filter((item) => item.side === "desired_partner").slice(0, 2).map((item) => item.code);
  const selfPrompts = byCode(metadata.prompts, selfCodes);
  const partnerPrompts = byCode(metadata.prompts, partnerCodes);
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const next: Record<string, string> = {};
    for (const item of [...selfPrompts, ...partnerPrompts]) {
      next[item.code] = existing[item.code] ?? "";
    }
    return next;
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const payload = [...selfPrompts, ...partnerPrompts]
        .map((item) => ({
          prompt_code: item.code,
          answer_text: (answers[item.code] ?? "").trim(),
        }))
        .filter((item) => item.answer_text.length > 0);
      await api.patchProfile({
        expected_version: state.profile.version,
        answers: payload,
      });
      await onSaved();
    } catch (error) {
      onError(error);
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      <h2 className="text-lg font-medium">Tell us more</h2>
      <p className="text-sm text-slate-600">
        Answer at least one question about you and one about the person you want to meet. 1–1000
        characters each.
      </p>
      <FormErrorSummary messages={errors} />
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">About you</h3>
        {selfPrompts.map((item) => (
          <label key={item.code} className="flex flex-col gap-1 text-sm">
            {item.label}
            <textarea
              name={item.code}
              value={answers[item.code] ?? ""}
              onChange={(e) => setAnswers((current) => ({ ...current, [item.code]: e.target.value }))}
              className="min-h-24 rounded-md border border-slate-300 px-3 py-2"
              maxLength={1000}
            />
          </label>
        ))}
      </section>
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Who you want to meet</h3>
        {partnerPrompts.map((item) => (
          <label key={item.code} className="flex flex-col gap-1 text-sm">
            {item.label}
            <textarea
              name={item.code}
              value={answers[item.code] ?? ""}
              onChange={(e) => setAnswers((current) => ({ ...current, [item.code]: e.target.value }))}
              className="min-h-24 rounded-md border border-slate-300 px-3 py-2"
              maxLength={1000}
            />
          </label>
        ))}
      </section>
      {fieldErrors.answer_text ? (
        <p className="text-sm text-red-800">{fieldErrors.answer_text}</p>
      ) : null}
      <StepNav onBack={onBack} busy={busy} />
    </form>
  );
}
