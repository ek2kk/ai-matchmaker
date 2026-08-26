import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type PrivacyView } from "@/lib/api";
import { ApiError } from "@/lib/http";
import { getAccountId, setSession } from "@/lib/session";

export function PrivacyPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<PrivacyView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const accountId = getAccountId();

  useEffect(() => {
    api
      .getPrivacy()
      .then(setView)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setSession(null);
          navigate("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load privacy.");
      });
  }, [navigate]);

  function logout() {
    api.logout().finally(() => navigate("/login"));
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Your privacy</h1>
      <p className="text-sm text-slate-600">Account {accountId ?? "unknown"}</p>
      {error ? (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      {view ? (
        <ul className="rounded-lg bg-white p-4 text-sm shadow-sm">
          <li>Discoverable: {String(view.discoverable)}</li>
          <li>AI matching: {String(view.allow_ai_matching)}</li>
          <li>Product analytics: {String(view.allow_product_analytics)}</li>
        </ul>
      ) : null}
      <div className="flex gap-3">
        <button
          type="button"
          onClick={logout}
          className="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          Log out
        </button>
        <Link to="/" className="self-center text-sm">
          API status
        </Link>
        <Link to="/onboarding" className="self-center text-sm">
          Onboarding
        </Link>
      </div>
    </main>
  );
}
