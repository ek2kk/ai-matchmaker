import { useEffect, useState } from "react";

import { api, type ProfilePhoto } from "@/lib/api";
import { env } from "@/lib/env";
import { ApiError } from "@/lib/http";

async function sha256Hex(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((item) => item.toString(16).padStart(2, "0")).join("");
}

function absoluteUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${env.apiBaseUrl}${path}`;
}

export function PhotoManager({
  onError,
}: {
  onError: (message: string) => void;
}) {
  const [photos, setPhotos] = useState<ProfilePhoto[]>([]);
  const [busy, setBusy] = useState(false);

  async function reload() {
    const listed = await api.listPhotos();
    setPhotos(listed.items);
  }

  useEffect(() => {
    reload().catch((err: unknown) => {
      onError(err instanceof ApiError ? err.message : "Could not load photos.");
    });
    // Initial load only; parent onError identity is not a reload trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!photos.some((item) => item.moderation_state === "pending")) {
      return;
    }
    const timer = window.setTimeout(() => {
      reload().catch(() => undefined);
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [photos]);

  async function onFile(file: File | undefined) {
    if (!file) {
      return;
    }
    setBusy(true);
    onError("");
    try {
      const digest = await sha256Hex(file);
      const intent = await api.createPhotoIntent({
        content_type: file.type || "image/jpeg",
        byte_size: file.size,
        content_sha256: digest,
      });
      const put = await fetch(absoluteUrl(intent.upload_url), {
        method: "PUT",
        headers: intent.headers,
        body: file,
      });
      if (!put.ok) {
        throw new Error("Upload failed.");
      }
      await api.completePhoto(intent.upload_intent_id);
      await reload();
    } catch (err: unknown) {
      onError(err instanceof ApiError ? err.message : "Could not upload that photo.");
    } finally {
      setBusy(false);
    }
  }

  async function move(photo: ProfilePhoto, delta: number) {
    const next = photo.position + delta;
    if (next < 0 || next > 5) {
      return;
    }
    setBusy(true);
    try {
      await api.patchPhoto(photo.photo_id, {
        expected_version: photo.version,
        position: next,
      });
      await reload();
    } catch (err: unknown) {
      onError(err instanceof ApiError ? err.message : "Could not reorder photos.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(photo: ProfilePhoto) {
    setBusy(true);
    try {
      await api.deletePhoto(photo.photo_id);
      await reload();
    } catch (err: unknown) {
      onError(err instanceof ApiError ? err.message : "Could not delete that photo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg bg-white p-4 shadow-sm">
      <h2 className="text-lg font-medium">Photos</h2>
      <p className="mt-1 text-sm text-slate-600">
        At least one approved photo is required before your profile can be shown to others.
      </p>
      {photos.length ? (
        <ul className="mt-4 flex flex-col gap-3">
          {photos.map((photo) => (
            <li key={photo.photo_id} className="flex items-center gap-3">
              <img
                src={absoluteUrl(photo.preview_url)}
                alt={`Photo ${photo.position + 1}`}
                className="h-16 w-16 rounded-md object-cover"
              />
              <div className="min-w-0 flex-1 text-sm">
                <p>Position {photo.position + 1}</p>
                <p className="text-slate-600">{photo.moderation_state}</p>
              </div>
              <button
                type="button"
                className="rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50"
                disabled={busy || photo.position === 0}
                onClick={() => {
                  void move(photo, -1);
                }}
              >
                Up
              </button>
              <button
                type="button"
                className="rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50"
                disabled={busy || photo.position >= photos.length - 1}
                onClick={() => {
                  void move(photo, 1);
                }}
              >
                Down
              </button>
              <button
                type="button"
                className="rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50"
                disabled={busy}
                onClick={() => {
                  void remove(photo);
                }}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-slate-600">No photos yet.</p>
      )}
      <label className="mt-4 inline-flex cursor-pointer rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white">
        {busy ? "Working…" : "Add photo"}
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="sr-only"
          disabled={busy}
          onChange={(event) => {
            void onFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </label>
    </section>
  );
}
