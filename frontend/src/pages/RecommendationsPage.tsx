import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  api,
  type OnboardingMetadata,
  type RecommendationBatchView,
  type RecommendationItemView,
} from "@/lib/api";
import { ApiError } from "@/lib/http";
import { setSession } from "@/lib/session";

const SURFACE = "daily_batch";
const PASS_REASONS = [
  { code: "not_my_type", label: "Not my type" },
  { code: "photos", label: "Photos" },
  { code: "location", label: "Location" },
  { code: "other", label: "Other" },
];
const REPORT_REASONS = [
  { code: "harassment", label: "Harassment" },
  { code: "spam", label: "Spam" },
  { code: "fake_profile", label: "Fake profile" },
  { code: "underage", label: "Underage" },
  { code: "other", label: "Other" },
];

function labelOf(items: { code: string; label: string }[] | undefined, code: string | null) {
  if (!code) {
    return "—";
  }
  return items?.find((item) => item.code === code)?.label ?? code.replaceAll("_", " ");
}

export function RecommendationsPage() {
  const navigate = useNavigate();
  const [batch, setBatch] = useState<RecommendationBatchView | null>(null);
  const [metadata, setMetadata] = useState<OnboardingMetadata | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gone, setGone] = useState<Set<string>>(new Set());
  const [matchNotice, setMatchNotice] = useState<{ name: string; href: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshNote, setRefreshNote] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api.getCurrentRecommendations(), api.getOnboardingMetadata()])
      .then(([next, meta]) => {
        setBatch(next);
        setMetadata(meta);
        setGone(new Set());
        setError(null);
        setRefreshNote(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setSession(null);
          navigate("/login");
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          setError("Publish your profile first to get recommendations.");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load recommendations.");
      });
  }, [navigate]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (batch?.status !== "pending") {
      return;
    }
    const timer = window.setTimeout(() => load(), 2000);
    return () => window.clearTimeout(timer);
  }, [batch?.status, load]);

  if (error) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-4 p-6">
        <p className="text-sm text-red-800" role="alert">
          {error}
        </p>
        <Link to="/onboarding" className="text-sm">
          Your profile
        </Link>
      </main>
    );
  }
  if (!batch || !metadata) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center p-6">
        <p className="text-slate-600">Loading recommendations…</p>
      </main>
    );
  }

  const visible = batch.items.filter(
    (item) => item.decision == null && !gone.has(item.recommendation_item_id),
  );
  const consumed =
    batch.status === "ready" &&
    batch.items.length > 0 &&
    visible.length === 0;

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col gap-6 p-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Recommendations</h1>
        <p className="text-sm text-slate-600">
          Up to five people who passed reciprocal filters. This is not an infinite feed.
        </p>
      </div>
      {matchNotice ? (
        <p className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-950" role="status" aria-live="polite">
          You matched with {matchNotice.name}.{" "}
          <Link to={matchNotice.href} className="underline">
            Open conversation
          </Link>
        </p>
      ) : null}
      {batch.status === "pending" ? (
        <p className="rounded-lg bg-white p-4 text-sm shadow-sm">Building your batch…</p>
      ) : null}
      {batch.status === "insufficient_supply" ? (
        <p className="rounded-lg bg-white p-4 text-sm shadow-sm">
          Not enough matching people right now.
        </p>
      ) : null}
      {consumed ? (
        <p className="rounded-lg bg-white p-4 text-sm shadow-sm">
          You have reviewed everyone in this batch.
        </p>
      ) : null}
      {refreshNote ? (
        <p className="rounded-lg bg-white p-4 text-sm shadow-sm" role="status">
          {refreshNote}
        </p>
      ) : null}
      <ul className="flex flex-col gap-3">
        {visible.map((item) => (
          <Card
            key={item.recommendation_item_id}
            item={item}
            metadata={metadata}
            onGone={() =>
              setGone((current) => new Set(current).add(item.recommendation_item_id))
            }
            onMatch={(name, conversationId) =>
              setMatchNotice({ name, href: `/conversations/${conversationId}` })
            }
            onAuthLost={() => {
              setSession(null);
              navigate("/login");
            }}
            onOpen={(profileId) => navigate(`/people/${profileId}`)}
          />
        ))}
      </ul>
      {refreshNote ? null : consumed || batch.status === "insufficient_supply" ? (
        <button
          type="button"
          disabled={busy || batch.status === "pending"}
          onClick={() => {
            setBusy(true);
            api
              .refreshRecommendations()
              .then((next) => {
                setBatch(next);
                setGone(new Set());
                setRefreshNote(null);
              })
              .catch((err: unknown) => {
                if (err instanceof ApiError && err.status === 409) {
                  setRefreshNote("No more batches today.");
                  return;
                }
                setError(err instanceof ApiError ? err.message : "Could not refresh.");
              })
              .finally(() => setBusy(false));
          }}
          className="rounded-md bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50"
        >
          Get another batch
        </button>
      ) : null}
      <p className="text-sm text-slate-600">
        <Link to="/people">All profiles</Link>
        {" · "}
        <Link to="/matches">Matches</Link>
        {" · "}
        <Link to="/onboarding">Your profile</Link>
      </p>
    </main>
  );
}

function Card({
  item,
  metadata,
  onGone,
  onMatch,
  onAuthLost,
  onOpen,
}: {
  item: RecommendationItemView;
  metadata: OnboardingMetadata;
  onGone: () => void;
  onMatch: (name: string, conversationId: string) => void;
  onAuthLost: () => void;
  onOpen: (profileId: string) => void;
}) {
  const profile = item.profile;
  const preview = profile.answers?.[0]?.answer_text;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passReason, setPassReason] = useState("");
  const [confirm, setConfirm] = useState<"block" | "report" | null>(null);
  const [reportReason, setReportReason] = useState("other");
  const onGoneRef = useRef(onGone);
  const onAuthLostRef = useRef(onAuthLost);
  onGoneRef.current = onGone;
  onAuthLostRef.current = onAuthLost;

  useEffect(() => {
    api
      .postRecommendationImpression(item.recommendation_item_id, { surface: SURFACE })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          onAuthLostRef.current();
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          onGoneRef.current();
        }
      });
  }, [item.recommendation_item_id]);

  function fail(err: unknown) {
    if (err instanceof ApiError && err.status === 401) {
      onAuthLost();
      return;
    }
    if (err instanceof ApiError && err.status === 404) {
      onGone();
      return;
    }
    if (err instanceof ApiError && err.status === 409 && err.code === "decision_conflict") {
      onGone();
      return;
    }
    setError(err instanceof ApiError ? err.message : "That action could not be saved.");
    setBusy(false);
  }

  function run(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    work()
      .then(() => setBusy(false))
      .catch(fail);
  }

  return (
    <li className="rounded-lg bg-white p-4 shadow-sm">
      <p className="font-medium">
        {profile.display_name}, {profile.age}
      </p>
      <p className="mt-1 text-sm text-slate-600">
        {labelOf(metadata.genders, profile.gender_code)}
        {" · "}
        {labelOf(metadata.public_areas, profile.public_area_code)}
        {" · "}
        {labelOf(metadata.relationship_goals, profile.relationship_goal_code)}
      </p>
      {item.reason?.text ? (
        <p className="mt-2 text-sm text-slate-700">{item.reason.text}</p>
      ) : null}
      {preview ? <p className="mt-2 line-clamp-3 text-sm text-slate-600">{preview}</p> : null}
      {error ? (
        <p className="mt-2 text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          aria-label={`Open ${profile.display_name}`}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          onClick={() =>
            run(async () => {
              await api.postRecommendationOpen(item.recommendation_item_id, {
                surface: SURFACE,
              });
              onOpen(profile.profile_id);
            })
          }
        >
          Open
        </button>
        <button
          type="button"
          disabled={busy}
          aria-label={`Like ${profile.display_name}`}
          className="rounded-md bg-emerald-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          onClick={() =>
            run(async () => {
              const result = await api.postRecommendationFeedback(item.recommendation_item_id, {
                action: "like",
              });
              if (result.match) {
                onMatch(profile.display_name, result.match.conversation_id);
              }
              onGone();
            })
          }
        >
          Like
        </button>
        <button
          type="button"
          disabled={busy}
          aria-label={`Pass on ${profile.display_name}`}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
          onClick={() =>
            run(async () => {
              await api.postRecommendationFeedback(item.recommendation_item_id, {
                action: "pass",
                ...(passReason ? { reason_code: passReason } : {}),
              });
              onGone();
            })
          }
        >
          Pass
        </button>
        <label className="sr-only" htmlFor={`pass-reason-${item.recommendation_item_id}`}>
          Optional pass reason for {profile.display_name}
        </label>
        <select
          id={`pass-reason-${item.recommendation_item_id}`}
          value={passReason}
          disabled={busy}
          onChange={(event) => setPassReason(event.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">Pass reason (optional)</option>
          {PASS_REASONS.map((row) => (
            <option key={row.code} value={row.code}>
              {row.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={busy}
          aria-label={`Block ${profile.display_name}`}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
          onClick={() => setConfirm("block")}
        >
          Block
        </button>
        <button
          type="button"
          disabled={busy}
          aria-label={`Report ${profile.display_name}`}
          className="rounded-md border border-red-300 px-3 py-1.5 text-sm text-red-800 disabled:opacity-50"
          onClick={() => setConfirm("report")}
        >
          Report
        </button>
      </div>
      {confirm === "block" ? (
        <div
          role="alertdialog"
          aria-labelledby={`block-title-${item.recommendation_item_id}`}
          className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm"
        >
          <p id={`block-title-${item.recommendation_item_id}`} className="font-medium">
            Block {profile.display_name}?
          </p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="rounded-md bg-slate-900 px-3 py-1.5 text-white"
              onClick={() =>
                run(async () => {
                  await api.postBlock({ profile_id: profile.profile_id });
                  setConfirm(null);
                  onGone();
                })
              }
            >
              Block
            </button>
            <button type="button" className="rounded-md px-3 py-1.5" onClick={() => setConfirm(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
      {confirm === "report" ? (
        <div
          role="alertdialog"
          aria-labelledby={`report-title-${item.recommendation_item_id}`}
          className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm"
        >
          <p id={`report-title-${item.recommendation_item_id}`} className="font-medium">
            Report {profile.display_name}?
          </p>
          <label className="mt-2 block text-xs uppercase tracking-wide text-slate-600" htmlFor={`report-reason-${item.recommendation_item_id}`}>
            Reason
          </label>
          <select
            id={`report-reason-${item.recommendation_item_id}`}
            value={reportReason}
            onChange={(event) => setReportReason(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5"
          >
            {REPORT_REASONS.map((row) => (
              <option key={row.code} value={row.code}>
                {row.label}
              </option>
            ))}
          </select>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="rounded-md bg-red-800 px-3 py-1.5 text-white"
              onClick={() =>
                run(async () => {
                  await api.postReport({
                    profile_id: profile.profile_id,
                    reason_code: reportReason,
                  });
                  setConfirm(null);
                  onGone();
                })
              }
            >
              Report
            </button>
            <button type="button" className="rounded-md px-3 py-1.5" onClick={() => setConfirm(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </li>
  );
}
