import { FormEvent, useEffect, useState } from "react";

import type { FactKeyMeta, OnboardingMetadata, OnboardingState, ProfileFact } from "@/lib/api";
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

function claim(fact: ProfileFact, keys: FactKeyMeta[]): string {
  const meta = keys.find((item) => item.code === fact.fact_code);
  const side = fact.profile_side === "desired_partner" ? "Looking for" : "You";
  const strength = fact.preference_strength ? ` (${fact.preference_strength})` : "";
  return `${side} · ${meta?.label ?? fact.fact_code}: ${fact.value}${strength}`;
}

export function FactsReviewStep({
  state,
  metadata,
  errors,
  busy,
  onBack,
  onSaved,
  onError,
}: Props) {
  const factKeys = metadata.fact_keys ?? [];
  const [facts, setFacts] = useState<ProfileFact[]>([]);
  const [status, setStatus] = useState(state.extraction?.status ?? "idle");
  const [manualKey, setManualKey] = useState(factKeys[0]?.code ?? "");
  const [manualSide, setManualSide] = useState<"self" | "desired_partner">("self");
  const [manualValue, setManualValue] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  async function refresh() {
    const latest = await api.getOnboarding();
    setStatus(latest.extraction?.status ?? "idle");
    const listed = await api.getProfileFacts("pending");
    setFacts(listed.items ?? []);
    return latest;
  }

  useEffect(() => {
    let cancelled = false;
    let ticks = 0;
    async function poll() {
      try {
        const latest = await refresh();
        if (cancelled) {
          return;
        }
        if (
          (latest.extraction?.status === "queued" || latest.extraction?.status === "running") &&
          ticks < 45
        ) {
          ticks += 1;
          window.setTimeout(poll, 2000);
        }
      } catch (error) {
        if (!cancelled) {
          onError(error);
        }
      }
    }
    void poll();
    return () => {
      cancelled = true;
    };
    // Bound poll on mount; parent onError is not memoized.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function decide(fact: ProfileFact, decision: "accept" | "reject" | "edit", value?: string) {
    await api.reviewProfileFact(fact.fact_id, {
      decision,
      value,
      expected_source_version: fact.source_version,
    });
    await refresh();
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const latest = await refresh();
      if (latest.gates.facts_reviewed) {
        await onSaved();
      }
    } catch (error) {
      onError(error);
    }
  }

  const spec = factKeys.find((item) => item.code === manualKey);

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      <h2 className="text-lg font-medium">Review extracted facts</h2>
      <p className="text-sm text-slate-600">
        Confirm only what you said. Accepting a fact uses it for matching. Pending facts stay out of
        matching.
      </p>
      <FormErrorSummary messages={errors} />
      {status === "queued" || status === "running" ? (
        <p className="text-sm text-slate-600">Reading your prompts…</p>
      ) : null}
      {status === "failed" ? (
        <p className="text-sm text-slate-600">
          Automatic extraction is unavailable. Continue without facts or add one below.
        </p>
      ) : null}
      {facts.map((fact) => (
        <article key={fact.fact_id} className="rounded-lg border border-slate-200 p-4 text-sm">
          <p className="font-medium">{claim(fact, factKeys)}</p>
          {fact.provenance_excerpt ? (
            <p className="mt-1 text-slate-600">From: {fact.provenance_excerpt}</p>
          ) : null}
          {editId === fact.fact_id ? (
            spec?.allowed?.length ? (
              <label className="mt-2 flex flex-col gap-1">
                Corrected value
                <select
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2"
                >
                  {(factKeys.find((item) => item.code === fact.fact_code)?.allowed ?? []).map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <label className="mt-2 flex flex-col gap-1">
                Corrected value
                <input
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2"
                />
              </label>
            )
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-md bg-slate-900 px-3 py-1 text-white"
              onClick={() => decide(fact, "accept").catch(onError)}
            >
              Accept
            </button>
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1"
              onClick={() => {
                if (editId === fact.fact_id) {
                  decide(fact, "edit", editValue).catch(onError);
                  setEditId(null);
                  return;
                }
                setEditId(fact.fact_id);
                setEditValue(fact.value);
              }}
            >
              {editId === fact.fact_id ? "Save edit" : "Edit"}
            </button>
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1"
              onClick={() => decide(fact, "reject").catch(onError)}
            >
              Reject
            </button>
          </div>
        </article>
      ))}
      <fieldset className="rounded-lg border border-dashed border-slate-300 p-4">
        <legend className="text-sm font-medium">Add a fact yourself</legend>
        <label className="mt-2 flex flex-col gap-1 text-sm">
          Side
          <select
            value={manualSide}
            onChange={(e) => setManualSide(e.target.value as "self" | "desired_partner")}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            <option value="self">You</option>
            <option value="desired_partner">Looking for</option>
          </select>
        </label>
        <label className="mt-2 flex flex-col gap-1 text-sm">
          Fact
          <select
            value={manualKey}
            onChange={(e) => {
              setManualKey(e.target.value);
              setManualValue("");
            }}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            {factKeys.map((item) => (
              <option key={item.code} value={item.code}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="mt-2 flex flex-col gap-1 text-sm">
          Value
          <select
            value={manualValue}
            onChange={(e) => setManualValue(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            <option value="">Select…</option>
            {(spec?.allowed ?? []).map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="mt-3 rounded-md border border-slate-300 px-3 py-1 text-sm"
          onClick={() => {
            if (!manualValue) {
              return;
            }
            api
              .createProfileFact({
                fact_code: manualKey,
                value: manualValue,
                profile_side: manualSide,
              })
              .then(() => {
                setManualValue("");
                return refresh();
              })
              .catch(onError);
          }}
        >
          Save fact
        </button>
      </fieldset>
      <StepNav onBack={onBack} continueLabel="Continue" busy={busy} />
    </form>
  );
}
