function parseApiBaseUrl(raw: string | undefined): string {
  if (!raw) {
    throw new Error("VITE_API_BASE_URL is not set");
  }
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error("VITE_API_BASE_URL is not a valid URL");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("VITE_API_BASE_URL must be http or https");
  }
  return raw.replace(/\/$/, "");
}

export const env = {
  apiBaseUrl: parseApiBaseUrl(import.meta.env.VITE_API_BASE_URL),
};
