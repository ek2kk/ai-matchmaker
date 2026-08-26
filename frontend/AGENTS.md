# Frontend — agent notes

This is the React SPA for AI Dating. Read [../AGENTS.md](../AGENTS.md) first — universal building rules live there. This file adds frontend-specific conventions.

The SPA is bootstrapped. Commands: `pnpm install --frozen-lockfile`, `pnpm dev`, `pnpm lint`, `pnpm tsc --noEmit`, `pnpm build`. Lockfile: `pnpm-lock.yaml`. `.npmrc` sets `minimum-release-age=10080`; `pnpm-workspace.yaml` repeats that as `minimumReleaseAge` (pnpm 11) and allowlists the `esbuild` build script.

## Stack

- **Plain React SPA** (Vite + TypeScript, strict). **Not Next.js** — do not suggest Next, SSR, server components, or file-based routing.
- **Tailwind CSS** for styling. No CSS modules, styled-components, Emotion, or `.module.css` files for component styles. Global theme tokens live in `src/index.css`.
- **shadcn/ui** for UI primitives. Add components with `pnpm dlx shadcn@latest add <name>` — don't hand-roll what shadcn already ships.
- **React Router** for routing.
- Local prototype auth uses backend login/password/session endpoints. Phone OTP/call-code and Yandex ID are Later; no Supabase client is used.

## Package manager

**`pnpm` only once the frontend is bootstrapped.** Do not use `npm install` or `yarn add`. The lockfile should be `pnpm-lock.yaml`. If you see `package-lock.json` or `yarn.lock` appear, that's a bug — delete it.

**Minimum release age: 7 days.** When the frontend is bootstrapped, enforce it via `.npmrc` with `minimum-release-age=10080` minutes. pnpm will then refuse to install any package version published less than 7 days ago. This defends against typosquat / compromised-release attacks where a malicious version of a popular package goes live and gets pulled within hours.

If a fresh package is genuinely required (e.g. urgent security fix in a dep we already use), override per-install and justify in the commit message — don't lower the global threshold.

## Dependency policy

See universal policy in [../AGENTS.md](../AGENTS.md). Frontend-specific:

- **HTTP:** use the native `fetch` API through a thin client in `src/lib/http.ts` and the `api` singleton in `src/lib/api.ts`. **No axios, ky, got, superagent, redaxios.**
- **Dates:** use native `Date` and `Intl.DateTimeFormat`. No moment, dayjs, date-fns unless genuinely needed.
- **Utilities:** use native `Array` / `Object` / `Map` methods. No lodash, ramda.
- **State:** `useState` / `useReducer` / `useContext` first. Only reach for external state libraries when the pain is real.
- **Forms:** native `<form>` + `FormData` first.
- **Validation:** only add a schema library when we actually need runtime validation at boundaries.
- **UI components:** shadcn primitives via `pnpm dlx shadcn@latest add <name>`. Don't hand-roll what shadcn already ships.

Before adding a package, check:

1. Is there a native browser or TS/JS API that does this?
2. Does shadcn/ui already cover it?
3. Is it small, well-maintained, and worth the maintenance cost?

If yes to (3), add it — but flag the decision in the commit message.

## Layout

```text
frontend/
├── src/
│   ├── components/        # App components. shadcn primitives under components/ui/
│   ├── lib/               # Framework-agnostic helpers (http, api, auth, env)
│   ├── pages/             # Route-level components
│   ├── App.tsx            # Router
│   ├── main.tsx
│   └── index.css          # Tailwind directives + global theme tokens
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

Keep imports consistent with the `@/*` alias (e.g. `@/lib/api`, `@/components/ui/button`).

## Code style (frontend-specific)

- **TypeScript strict.** No `any` unless there's no alternative; prefer `unknown` and narrow.
- **Small, composable functions and components** over clever abstractions. Three similar lines > a premature generic.
- **One component = one file.** Components stay small enough to fit on one screen.
- **Tailwind classes inline.** No CSS modules, styled-components, Emotion, or `.module.css` for component styles. Global tokens live in `src/index.css`.

## Configuration

- All env reads go through a single `src/lib/env.ts` module that validates required vars at boot. Never read `import.meta.env.X` directly in components.
- Env vars are prefixed `VITE_` (Vite convention). Anything not prefixed is not exposed to the client.

## Backend integration

- Talks to a separate Python backend over JSON. URL comes from `VITE_API_BASE_URL`.
- Always use `api.get/post/put/patch/delete` from `@/lib/api` — it handles base URL, JSON, application session credentials, timeouts, and typed `ApiError`s (including the `isNetworkError` flag that distinguishes CORS/network from HTTP errors).
- Local prototype auth is login/password with opaque backend sessions. Session credentials are injected automatically via the API client; never thread tokens through component props.
- The SPA never builds canonical analytics payloads and never sends `event_id`, `occurred_at`, actor/subject, or event `properties`. Those fields are server-owned. `Idempotency-Key` is added with the first state-changing endpoint.

## Testing

**No frontend tests.** Do not write `*.test.ts` / `*.test.tsx` files or introduce a test runner. We verify the frontend manually in the browser plus `pnpm tsc --noEmit` and `pnpm lint`. If you find yourself reaching for vitest, Playwright, or Cypress — stop. That's not what this project does. Correctness for shared logic comes from keeping it simple and well-typed, not from a test suite.

## Anti-patterns (rejected)

- Reading `import.meta.env.X` directly outside `lib/env.ts`.
- Importing an HTTP library when `fetch` would do.
- Mixing client state libraries (Zustand + Jotai + Redux) for one project.
- `any` annotations to silence the type-checker.
- Custom CSS files / styled-components alongside Tailwind.
- Re-implementing a shadcn primitive by hand.
- Reaching for Next.js, SSR, or any framework that requires a Node server in front of the SPA.
