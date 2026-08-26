# Graph Report - frontend  (2026-08-26)

## Corpus Check
- 29 files · ~7,138 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 181 nodes · 315 edges · 14 communities (13 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- api.ts
- devDependencies
- compilerOptions
- package.json
- Frontend — agent notes
- CalibrationStep.tsx
- PartnerPreferencesStep.tsx
- OnboardingPage.tsx
- FactsReviewStep.tsx
- PromptStep.tsx
- DiscoverabilityStep.tsx
- vite-env.d.ts

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 19 edges
2. `api` - 14 edges
3. `OnboardingState` - 10 edges
4. `Frontend — agent notes` - 10 edges
5. `ApiError` - 9 edges
6. `setSession()` - 9 edges
7. `FormErrorSummary()` - 8 edges
8. `StepNav()` - 8 edges
9. `OnboardingMetadata` - 8 edges
10. `scripts` - 5 edges

## Surprising Connections (you probably didn't know these)
- `remember()` --calls--> `setSession()`  [EXTRACTED]
  src/lib/api.ts → src/lib/session.ts
- `OnboardingPage()` --calls--> `setSession()`  [EXTRACTED]
  src/pages/OnboardingPage.tsx → src/lib/session.ts
- `CalibrationStep()` --calls--> `granted()`  [EXTRACTED]
  src/components/onboarding/CalibrationStep.tsx → src/lib/onboarding.ts
- `EligibilityStep()` --calls--> `granted()`  [EXTRACTED]
  src/components/onboarding/EligibilityStep.tsx → src/lib/onboarding.ts
- `request()` --calls--> `getSessionToken()`  [EXTRACTED]
  src/lib/http.ts → src/lib/session.ts

## Import Cycles
- None detected.

## Communities (14 total, 1 thin omitted)

### Community 0 - "api.ts"
Cohesion: 0.09
Nodes (32): App(), api, CodeLabel, DemoCard, ExtractionStatus, FactsListResponse, HealthStatus, OnboardingCompleteResult (+24 more)

### Community 1 - "devDependencies"
Cohesion: 0.07
Nodes (29): eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, devDependencies, eslint, @eslint/js (+21 more)

### Community 2 - "compilerOptions"
Cohesion: 0.08
Nodes (24): DOM, DOM.Iterable, ES2022, src, compilerOptions, allowImportingTsExtensions, baseUrl, isolatedModules (+16 more)

### Community 3 - "package.json"
Cohesion: 0.12
Nodes (16): dependencies, react, react-dom, react-router-dom, name, private, scripts, build (+8 more)

### Community 4 - "Frontend — agent notes"
Cohesion: 0.18
Nodes (10): Anti-patterns (rejected), Backend integration, Code style (frontend-specific), Configuration, Dependency policy, Frontend — agent notes, Layout, Package manager (+2 more)

### Community 5 - "CalibrationStep.tsx"
Cohesion: 0.27
Nodes (8): CalibrationStep(), Props, EligibilityStep(), Props, FormErrorSummary(), Props, CalibrationSession, granted()

### Community 6 - "PartnerPreferencesStep.tsx"
Cohesion: 0.25
Nodes (8): PartnerPreferencesStep(), Props, toggle(), Props, SelfProfileStep(), Props, StepNav(), OnboardingMetadata

### Community 7 - "OnboardingPage.tsx"
Cohesion: 0.35
Nodes (8): Props, VersionConflictDialog(), errorSummary(), fieldMessages(), firstIncompleteStep(), StepId, STEPS, OnboardingPage()

### Community 8 - "FactsReviewStep.tsx"
Cohesion: 0.40
Nodes (5): claim(), FactsReviewStep(), Props, FactKeyMeta, ProfileFact

### Community 9 - "PromptStep.tsx"
Cohesion: 0.50
Nodes (4): byCode(), PromptStep(), Props, PromptMeta

### Community 10 - "DiscoverabilityStep.tsx"
Cohesion: 0.50
Nodes (3): DiscoverabilityStep(), Props, OnboardingState

## Knowledge Gaps
- **80 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `devDependencies` connect `devDependencies` to `package.json`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _80 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `api.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.08787878787878788 - nodes in this community are weakly interconnected._
- **Should `devDependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.06896551724137931 - nodes in this community are weakly interconnected._
- **Should `compilerOptions` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `package.json` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._