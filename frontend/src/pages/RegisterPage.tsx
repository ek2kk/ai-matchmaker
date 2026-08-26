import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/lib/api";
import { ApiError } from "@/lib/http";

export function RegisterPage() {
  const navigate = useNavigate();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    api
      .register(login, password)
      .then(() => navigate("/onboarding"))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError(err.message);
          return;
        }
        setError("Registration failed.");
      });
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Create local account</h1>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm">
          Login
          <input
            name="login"
            autoComplete="username"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            name="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
            required
          />
        </label>
        {error ? (
          <p className="text-sm text-red-700" role="alert">
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          className="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          Register
        </button>
      </form>
      <p className="text-sm text-slate-600">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </main>
  );
}
