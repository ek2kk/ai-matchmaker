import { env } from "./env";
import { getSessionToken } from "./session";

// Canonical analytics (event_id, occurred_at, actor, properties) are server-owned.
// Do not send them from the SPA. Idempotency-Key is added on mutating requests.

const TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  readonly isNetworkError: boolean;
  readonly status: number | null;
  readonly code: string | null;
  readonly details: Record<string, unknown> | null;

  constructor(
    message: string,
    isNetworkError: boolean,
    status: number | null = null,
    code: string | null = null,
    details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.isNetworkError = isNetworkError;
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isVersionConflict(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 409 && error.code === "version_conflict";
}

type ErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);
  const headers = new Headers(init?.headers);
  const token = getSessionToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const method = (init?.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD" && !headers.has("Idempotency-Key")) {
    headers.set("Idempotency-Key", crypto.randomUUID());
  }
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  try {
    const response = await fetch(`${env.apiBaseUrl}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    });
    if (response.status === 204) {
      return undefined as T;
    }
    const text = await response.text();
    const data = text ? (JSON.parse(text) as unknown) : null;
    if (!response.ok) {
      const err = data as ErrorBody | null;
      throw new ApiError(
        err?.error?.message ?? "Request failed",
        false,
        response.status,
        err?.error?.code ?? null,
        err?.error?.details ?? null,
      );
    }
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("Network error", true);
  } finally {
    window.clearTimeout(timer);
  }
}
