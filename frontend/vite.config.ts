import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

function assertApiBaseUrl(raw: string | undefined): void {
  if (!raw) {
    throw new Error("VITE_API_BASE_URL is required");
  }
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error("VITE_API_BASE_URL must be a valid URL");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("VITE_API_BASE_URL must be http or https");
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  if (mode === "production") {
    assertApiBaseUrl(env.VITE_API_BASE_URL);
  }
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
  };
});
