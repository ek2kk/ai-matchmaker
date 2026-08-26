import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type ConversationSummary } from "@/lib/api";
import { ApiError } from "@/lib/http";
import { setSession } from "@/lib/session";

export function MatchesPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listConversations()
      .then((listed) => {
        setItems(listed.items);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setSession(null);
          navigate("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load matches.");
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col gap-6 p-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Matches</h1>
        <p className="text-sm text-slate-600">Active conversations from reciprocal likes.</p>
      </div>
      {error ? (
        <p className="text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <p className="text-slate-600">Loading matches…</p> : null}
      {!loading && !items.length ? (
        <p className="rounded-lg bg-white p-4 text-sm text-slate-600 shadow-sm">
          No active matches yet.
        </p>
      ) : null}
      <ul className="flex flex-col gap-3">
        {items.map((item) => (
          <li key={item.conversation_id}>
            <Link
              to={`/conversations/${item.conversation_id}`}
              className="block rounded-lg bg-white p-4 shadow-sm hover:bg-slate-50"
            >
              <p className="font-medium">
                {item.counterpart.display_name}, {item.counterpart.age}
              </p>
              <p className="mt-1 text-sm text-slate-600">{item.counterpart.public_area_code}</p>
            </Link>
          </li>
        ))}
      </ul>
      <p className="text-sm text-slate-600">
        <Link to="/recommendations">Recommendations</Link>
        {" · "}
        <Link to="/people">Profiles</Link>
      </p>
    </main>
  );
}
