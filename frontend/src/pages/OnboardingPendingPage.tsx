import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import type {
  CodeLabel,
  FactKeyMeta,
  OnboardingMetadata,
  OnboardingState,
  ProfileFact,
  PromptMeta,
} from "@/lib/api";
import { api } from "@/lib/api";
import { PhotoManager } from "@/components/PhotoManager";
import { ApiError } from "@/lib/http";
import { setSession } from "@/lib/session";

function labelOf(items: CodeLabel[] | undefined, code: string | null): string {
  if (!code) {
    return "—";
  }
  return items?.find((item) => item.code === code)?.label ?? code.replaceAll("_", " ");
}

function labelsOf(items: CodeLabel[] | undefined, codes: string[]): string {
  return codes.length ? codes.map((code) => labelOf(items, code)).join(", ") : "—";
}

function promptLabel(prompts: PromptMeta[] | undefined, code: string): string {
  return prompts?.find((item) => item.code === code)?.label ?? code;
}

function prettyValue(fact: ProfileFact): string {
  const value = fact.value.replaceAll("_", " ");
  const strength = fact.preference_strength
    ? ` (${fact.preference_strength.replaceAll("_", " ")})`
    : "";
  return `${value}${strength}`;
}

function groupedFacts(facts: ProfileFact[], keys: FactKeyMeta[]) {
  const order: string[] = [];
  const byCode = new Map<string, ProfileFact[]>();
  for (const fact of facts) {
    if (!byCode.has(fact.fact_code)) {
      order.push(fact.fact_code);
      byCode.set(fact.fact_code, []);
    }
    byCode.get(fact.fact_code)?.push(fact);
  }
  return order.map((code) => {
    const items = [...(byCode.get(code) ?? [])].sort((a, b) =>
      prettyValue(a).localeCompare(prettyValue(b)),
    );
    return {
      code,
      label: keys.find((item) => item.code === code)?.label ?? code,
      items,
    };
  });
}

export function OnboardingPendingPage() {
  const navigate = useNavigate();
  const [state, setState] = useState<OnboardingState | null>(null);
  const [metadata, setMetadata] = useState<OnboardingMetadata | null>(null);
  const [facts, setFacts] = useState<ProfileFact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);

  const load = useCallback(() => {
    Promise.all([api.getOnboarding(), api.getOnboardingMetadata(), api.getProfileFacts("confirmed")])
      .then(([nextState, nextMeta, listed]) => {
        if (!nextState.onboarding_completed) {
          navigate("/onboarding");
          return;
        }
        setState(nextState);
        setMetadata(nextMeta);
        setFacts(listed.items ?? []);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setSession(null);
          navigate("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load your profile.");
      });
  }, [navigate]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const status = state?.embedding?.status;
    if (status !== "queued" && status !== "running") {
      return;
    }
    const timer = window.setTimeout(() => {
      load();
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [load, state?.embedding?.status]);

  async function removeFact(fact: ProfileFact) {
    setBusyId(fact.fact_id);
    setActionError(null);
    try {
      await api.reviewProfileFact(fact.fact_id, {
        decision: "reject",
        expected_source_version: fact.source_version,
      });
      const listed = await api.getProfileFacts("confirmed");
      setFacts(listed.items ?? []);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setSession(null);
        navigate("/login");
        return;
      }
      setActionError(err instanceof ApiError ? err.message : "Could not remove that fact.");
    } finally {
      setBusyId(null);
    }
  }

  async function publish() {
    setPublishing(true);
    setActionError(null);
    try {
      await api.publishProfile();
      const next = await api.getOnboarding();
      setState(next);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setSession(null);
        navigate("/login");
        return;
      }
      setActionError(err instanceof ApiError ? err.message : "Could not publish your profile.");
    } finally {
      setPublishing(false);
    }
  }

  if (error) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-4 p-6">
        <p className="text-sm text-red-800" role="alert">
          {error}
        </p>
      </main>
    );
  }
  if (!state || !metadata) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center p-6">
        <p className="text-slate-600">Loading your profile…</p>
      </main>
    );
  }

  const factKeys = metadata.fact_keys ?? [];
  const selfFacts = facts.filter((item) => item.profile_side === "self");
  const partnerFacts = facts.filter((item) => item.profile_side === "desired_partner");
  const selfAnswers = state.profile.answers.filter((row) =>
    metadata.prompts.some((item) => item.code === row.prompt_code && item.side === "self"),
  );
  const partnerAnswers = state.profile.answers.filter((row) =>
    metadata.prompts.some((item) => item.code === row.prompt_code && item.side === "desired_partner"),
  );

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col gap-6 p-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Your profile</h1>
        <p className="text-sm text-slate-600">
          This is what we have on you now: the fields you entered, your answers, and the facts you
          confirmed for matching.
        </p>
      </div>
      {state.profile.activated_at ? (
        <p className="rounded-lg bg-white p-4 text-sm shadow-sm">
          {state.embedding?.status === "queued" || state.embedding?.status === "running"
            ? "Published. Building embeddings…"
            : state.embedding?.status === "failed"
              ? "Published, but embeddings failed. Try publish again."
              : "Published. Ready for matching."}
        </p>
      ) : (
        <button
          type="button"
          className="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          disabled={publishing}
          onClick={() => {
            void publish();
          }}
        >
          {publishing ? "Publishing…" : "Publish profile"}
        </button>
      )}
      {actionError ? (
        <p className="text-sm text-red-800" role="alert">
          {actionError}
        </p>
      ) : null}
      <PhotoManager onError={setActionError} />
      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="text-lg font-medium">You</h2>
        <dl className="mt-3 flex flex-col gap-3 text-sm">
          <Row label="Name" value={state.profile.display_name} />
          <Row label="Gender" value={labelOf(metadata.genders, state.profile.gender_code)} />
          <Row
            label="Orientation"
            value={labelOf(metadata.orientations, state.profile.orientation_code)}
          />
          <Row label="Search mode" value={labelOf(metadata.search_modes, state.profile.search_mode)} />
          {state.profile.search_mode === "dating" ? (
            <Row
              label="Relationship"
              value={labelOf(metadata.relationship_goals, state.profile.relationship_goal_code)}
            />
          ) : null}
          <Row label="City" value={labelOf(metadata.cities, state.profile.city_code)} />
        </dl>
        {selfAnswers.length ? (
          <ul className="mt-4 flex flex-col gap-3 text-sm">
            {selfAnswers.map((row) => (
              <li key={row.answer_id}>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {promptLabel(metadata.prompts, row.prompt_code)}
                </p>
                <p className="mt-0.5 whitespace-pre-wrap">{row.answer_text}</p>
              </li>
            ))}
          </ul>
        ) : null}
        <FactList
          facts={selfFacts}
          keys={factKeys}
          empty="No confirmed facts about you yet."
          busyId={busyId}
          onRemove={removeFact}
        />
      </section>
      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="text-lg font-medium">Desired partner</h2>
        <dl className="mt-3 flex flex-col gap-3 text-sm">
          <Row
            label="Genders"
            value={labelsOf(metadata.genders, state.preferences.accepted_gender_codes)}
          />
          <Row
            label="Ages"
            value={
              state.preferences.age_min != null && state.preferences.age_max != null
                ? `${state.preferences.age_min}–${state.preferences.age_max}`
                : "—"
            }
          />
          <Row
            label="Distance"
            value={
              state.preferences.max_distance_km != null
                ? `up to ${state.preferences.max_distance_km} km`
                : "—"
            }
          />
          <Row label="Cities" value={labelsOf(metadata.cities, state.preferences.city_codes)} />
          {state.profile.search_mode === "dating" ? (
            <Row
              label="Goals"
              value={labelsOf(metadata.relationship_goals, state.preferences.relationship_goal_codes)}
            />
          ) : null}
        </dl>
        {partnerAnswers.length ? (
          <ul className="mt-4 flex flex-col gap-3 text-sm">
            {partnerAnswers.map((row) => (
              <li key={row.answer_id}>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {promptLabel(metadata.prompts, row.prompt_code)}
                </p>
                <p className="mt-0.5 whitespace-pre-wrap">{row.answer_text}</p>
              </li>
            ))}
          </ul>
        ) : null}
        <FactList
          facts={partnerFacts}
          keys={factKeys}
          empty="No confirmed facts about a desired partner yet."
          busyId={busyId}
          onRemove={removeFact}
        />
      </section>
      <Link to="/privacy" className="self-start text-sm">
        Privacy
      </Link>
      <Link to="/people" className="self-start text-sm">
        Browse profiles
      </Link>
      <Link to="/recommendations" className="self-start text-sm">
        Recommendations
      </Link>
    </main>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5">{value || "—"}</dd>
    </div>
  );
}

function FactList({
  facts,
  keys,
  empty,
  busyId,
  onRemove,
}: {
  facts: ProfileFact[];
  keys: FactKeyMeta[];
  empty: string;
  busyId: string | null;
  onRemove: (fact: ProfileFact) => void;
}) {
  const groups = groupedFacts(facts, keys);
  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Confirmed facts</p>
      {groups.length ? (
        <dl className="mt-3 flex flex-col gap-4">
          {groups.map((group) => (
            <div key={group.code}>
              <dt className="text-sm font-medium">{group.label}</dt>
              <dd>
                <ul className="mt-1 flex flex-col gap-1">
                  {group.items.map((fact) => (
                    <li
                      key={fact.fact_id}
                      className="flex items-center justify-between gap-3 text-sm"
                    >
                      <span>{prettyValue(fact)}</span>
                      <button
                        type="button"
                        className="shrink-0 rounded-md border border-slate-300 px-2 py-0.5 text-xs"
                        disabled={busyId !== null}
                        aria-label={`Remove ${group.label}: ${prettyValue(fact)}`}
                        onClick={() => onRemove(fact)}
                      >
                        {busyId === fact.fact_id ? "Removing…" : "Remove"}
                      </button>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-2 text-sm text-slate-600">{empty}</p>
      )}
    </div>
  );
}
