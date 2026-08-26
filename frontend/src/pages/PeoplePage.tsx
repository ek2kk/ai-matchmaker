import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type OnboardingMetadata, type PublicProfileCard } from "@/lib/api";
import { ApiError } from "@/lib/http";
import { setSession } from "@/lib/session";

function labelOf(items: { code: string; label: string }[] | undefined, code: string | null) {
  if (!code) {
    return "—";
  }
  return items?.find((item) => item.code === code)?.label ?? code.replaceAll("_", " ");
}

export function PeoplePage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<PublicProfileCard[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<(string | null)[]>([null]);
  const [page, setPage] = useState(0);
  const [metadata, setMetadata] = useState<OnboardingMetadata | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    (after: string | null) => {
      setLoading(true);
      setError(null);
      Promise.all([api.listProfiles(after), api.getOnboardingMetadata()])
        .then(([listed, meta]) => {
          setItems(listed.items);
          setCursor(listed.next_cursor);
          setMetadata(meta);
        })
        .catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 401) {
            setSession(null);
            navigate("/login");
            return;
          }
          setError(err instanceof ApiError ? err.message : "Could not load profiles.");
        })
        .finally(() => setLoading(false));
    },
    [navigate],
  );

  useEffect(() => {
    load(null);
  }, [load]);

  function nextPage() {
    if (!cursor) {
      return;
    }
    setHistory((prev) => [...prev, cursor]);
    setPage((prev) => prev + 1);
    load(cursor);
  }

  function prevPage() {
    if (page === 0) {
      return;
    }
    const prevCursor = history[page - 1] ?? null;
    setHistory((prev) => prev.slice(0, page));
    setPage((prev) => prev - 1);
    load(prevCursor);
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-3xl flex-col gap-6 p-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Profiles</h1>
        <p className="text-sm text-slate-600">
          Discoverable profiles, 50 per page. Open a card to read the public answers.
        </p>
      </div>
      {error ? (
        <p className="text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <p className="text-slate-600">Loading profiles…</p> : null}
      {!loading && !items.length ? (
        <p className="rounded-lg bg-white p-4 text-sm text-slate-600 shadow-sm">
          No discoverable profiles yet.
        </p>
      ) : null}
      <ul className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item.profile_id}>
            <Link
              to={`/people/${item.profile_id}`}
              className="block rounded-lg bg-white p-4 shadow-sm hover:bg-slate-50"
            >
              <p className="font-medium">
                {item.display_name}, {item.age}
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {labelOf(metadata?.genders, item.gender_code)}
                {" · "}
                {labelOf(metadata?.public_areas, item.public_area_code)}
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {labelOf(metadata?.relationship_goals, item.relationship_goal_code)}
              </p>
            </Link>
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40"
          disabled={page === 0 || loading}
          onClick={prevPage}
        >
          Previous
        </button>
        <button
          type="button"
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40"
          disabled={!cursor || loading}
          onClick={nextPage}
        >
          Next
        </button>
        <span className="text-sm text-slate-600">Page {page + 1}</span>
      </div>
      <p className="text-sm text-slate-600">
        <Link to="/recommendations">Recommendations</Link>
        {" · "}
        <Link to="/matches">Matches</Link>
        {" · "}
        <Link to="/onboarding">Your profile</Link>
      </p>
    </main>
  );
}
