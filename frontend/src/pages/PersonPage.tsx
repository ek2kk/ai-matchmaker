import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, type OnboardingMetadata, type PublicProfile } from "@/lib/api";
import { env } from "@/lib/env";
import { ApiError } from "@/lib/http";
import { setSession } from "@/lib/session";

function labelOf(items: { code: string; label: string }[] | undefined, code: string | null) {
  if (!code) {
    return "—";
  }
  return items?.find((item) => item.code === code)?.label ?? code.replaceAll("_", " ");
}

export function PersonPage() {
  const { profileId } = useParams<{ profileId: string }>();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [metadata, setMetadata] = useState<OnboardingMetadata | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profileId) {
      return;
    }
    Promise.all([api.getPublicProfile(profileId), api.getOnboardingMetadata()])
      .then(([next, meta]) => {
        setProfile(next);
        setMetadata(meta);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setSession(null);
          navigate("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load this profile.");
      });
  }, [navigate, profileId]);

  if (error) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-4 p-6">
        <p className="text-sm text-red-800" role="alert">
          {error}
        </p>
        <Link to="/people" className="text-sm">
          Back to profiles
        </Link>
      </main>
    );
  }
  if (!profile || !metadata) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center p-6">
        <p className="text-slate-600">Loading profile…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col gap-6 p-6 py-10">
      <Link to="/people" className="text-sm text-slate-600">
        Back to profiles
      </Link>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {profile.display_name}, {profile.age}
        </h1>
        <p className="text-sm text-slate-600">
          {labelOf(metadata.genders, profile.gender_code)}
          {" · "}
          {labelOf(metadata.public_areas, profile.public_area_code)}
          {" · "}
          {labelOf(metadata.relationship_goals, profile.relationship_goal_code)}
        </p>
      </div>
      {profile.photo_urls?.length ? (
        <div className="flex gap-2 overflow-x-auto">
          {profile.photo_urls.map((url) => (
            <img
              key={url}
              src={url.startsWith("http") ? url : `${env.apiBaseUrl}${url}`}
              alt=""
              className="h-40 w-32 shrink-0 rounded-md object-cover"
            />
          ))}
        </div>
      ) : null}
      {profile.bio ? (
        <p className="rounded-lg bg-white p-4 text-sm shadow-sm whitespace-pre-wrap">{profile.bio}</p>
      ) : null}
      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="text-lg font-medium">About</h2>
        {profile.answers.length ? (
          <ul className="mt-4 flex flex-col gap-3 text-sm">
            {profile.answers.map((row) => (
              <li key={row.answer_id}>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {metadata.prompts.find((item) => item.code === row.prompt_code)?.label ??
                    row.prompt_code}
                </p>
                <p className="mt-0.5 whitespace-pre-wrap">{row.answer_text}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-600">No public answers yet.</p>
        )}
      </section>
    </main>
  );
}
