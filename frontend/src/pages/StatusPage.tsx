import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, type HealthStatus } from "@/lib/api";
import { ApiError } from "@/lib/http";

type Status =
  | { kind: "loading" }
  | { kind: "ok"; health: HealthStatus }
  | { kind: "error"; message: string };

function messageFor(error: unknown): string {
  if (error instanceof ApiError && error.isNetworkError) {
    return "Can't reach the API.";
  }
  return "The API returned an error.";
}

export function StatusPage() {
  const [status, setStatus] = useState<Status>({ kind: "loading" });

  const load = useCallback(() => {
    setStatus({ kind: "loading" });
    api
      .getHealth()
      .then((health) => setStatus({ kind: "ok", health }))
      .catch((error: unknown) => setStatus({ kind: "error", message: messageFor(error) }));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">API status</h1>
      {status.kind === "loading" ? <p className="text-slate-600">Checking backend…</p> : null}
      {status.kind === "ok" ? (
        <p className="rounded-lg bg-white p-4 shadow-sm">
          Backend is {status.health.status}, version {status.health.version}.
        </p>
      ) : null}
      {status.kind === "error" ? (
        <p className="rounded-lg bg-white p-4 text-red-700 shadow-sm">{status.message}</p>
      ) : null}
      <button
        type="button"
        onClick={load}
        className="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        Retry
      </button>
      <p className="text-sm text-slate-600">
        <Link to="/register">Register</Link> · <Link to="/login">Sign in</Link> ·{" "}
        <Link to="/recommendations">Recommendations</Link> · <Link to="/matches">Matches</Link> ·{" "}
        <Link to="/people">Profiles</Link>
      </p>
    </main>
  );
}
