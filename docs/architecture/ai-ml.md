# AI and ML boundary

> **Principle:** models propose derived data or ordering; deterministic application policy owns eligibility, consent, authorization and enforcement.

## 1. MVP model uses

| Capability | Input | Output | Authority | Fallback |
|---|---|---|---|---|
| Fact extraction | One user-authored answer, allowlisted schema | Pending normalized facts + confidence | User confirms/edits/rejects | Manual structured input |
| Embeddings | Deterministic minimized self/desired projection | `EmbeddingsGigaR` 2560-dimensional versioned vector | Retrieval hint only | Exact eligible SQL + heuristic |
| LLM reranking | Actor preference summary + ≤20 eligible candidate summaries | Ordered supplied IDs + reason codes | Server validates; cannot add IDs | Heuristic order |
| Text/photo moderation | Submitted content/media derivative | Allow/hold/reject signal | Policy + human escalation for material cases | Hold non-public, fail closed |

No autonomous agent, external social lookup, tool use on behalf of a user, model-authored message sending or end-to-end learned ranker in MVP.

## 2. Data minimization

Allowed only when required by the named purpose: reviewed prompt text, confirmed `matching_only` facts, coarse public area, explicit desired preferences, candidate public/matching projection. Before provider call, server builds a purpose-specific projection, records its schema/version and strips unsupported fields.

Never send unless a separately approved feature proves necessity and consent:

- email, phone, auth token, IP/device identifiers;
- exact DOB or exact location/GPS;
- account, block, report, moderation-case or staff identifiers;
- raw report details, security evidence, private messages for matching;
- private/rejected/pending facts;
- inferred sensitive traits, third-party data, contact lists or social profiles;
- original photo when a minimized derivative suffices for moderation.

Model prompts and responses must not enter general application logs. Yandex AI Studio is the generation provider; GigaChat `EmbeddingsGigaR` is the retrieval provider. Local prototype may call DS Lab via `DSLAB_API_KEY` (`gemini-2.5-flash-lite` for extraction, `gte-base` 768-d for embeddings) or OpenRouter as an OpenAI-compatible stand-in; neither is a production provider. Their retention/data-region contracts require a recorded production review; use the most restrictive available settings and only the OpenAI-compatible API subset covered by contract tests.

## 3. Extraction contract and guardrails

- JSON schema has an allowlist of `fact_code` and a closed value vocabulary per code. Repeatable codes (`interest`, `date_preference`, `values`) may appear multiple times; ordinal codes appear at most once per `profile_side`.
- Input is one account's current answer version; `prompt_code` selects `profile_side` (`self_*` → `self`, `partner_*` → `desired_partner`). Cross-user context is forbidden.
- Output is untrusted: validate schema, closed values, confidence, prohibited trait rules and source version.
- Store as `pending`; no matching use before explicit confirmation. Accept sets `visibility=matching_only`.
- Show source excerpt and purpose; user edit supersedes the model proposal.
- Prompt injection in profile text has no effect because extraction has no tools, instructions from user text are delimited as data and output is schema-constrained.
- Unknown `fact_code`, unknown value, and hard-filter keys (`gender`, `age`/`birth_date`, `orientation`, `city`, `search_mode`, `relationship_goal`, `relationship_status`, safety/block) are dropped. Prohibited sensitive inference fail-closes the whole provider result: no facts are stored, the job is `failed`, and the user continues with manual structured input.

### Extraction schema v2

Prompt version `extract-facts-v4`. Only explicitly stated claims; never inferred sensitive traits or hard filters. Codes and values are a closed product vocabulary.

| `fact_code` | Kind | Values | Category |
|---|---|---|---|
| `interest` | repeatable ≤8 | `travel`, `fitness`, `gaming`, `cinema`, `books`, `technology`, `art`, `music`, `cooking`, `photography` | `lifestyle` |
| `date_preference` | repeatable ≤8 | `walking`, `restaurants`, `cinema`, `travel`, `home_evening`, `short_trip` | `lifestyle` |
| `values` | repeatable ≤8 | `family`, `career`, `personal_growth`, `freedom`, `stability` | `intent` |
| `fitness_level`, `nightlife_preference`, `energy_level`, `spontaneity` | ordinal | `low`, `medium`, `high` | `lifestyle` |
| `travel_frequency` | ordinal | `rare`, `occasional`, `frequent` | `lifestyle` |
| `social_style` | ordinal | `introvert`, `ambivert`, `extrovert` | `lifestyle` |
| `communication_style` | ordinal | `direct`, `warm`, `reserved` | `intent` |
| `occupation_domain` | ordinal | `software_engineering`, `design`, `healthcare`, `education`, `business`, `science`, `arts`, `other` | `lifestyle` |

Provider JSON is `{facts:[{fact_code,value,confidence,excerpt?,preference_strength?}]}`. `value` is a single slug. `preference_strength` (`dont_care`/`prefer`/`strong_preference`) is stored only on `desired_partner` rows and defaults to `prefer`. `excerpt` is ≤120 characters from the source answer. `strong_preference` is a ranking hint, never a hard filter.

### Extraction job

`job_type = extract_profile_facts`. Payload is only `answer_id`, `answer_version`, `prompt_version`, `model_version`. `dedup_key` is `extract_profile_facts:{answer_id}:{answer_version}:{prompt_version}:{model_version}`. Default `max_attempts = 3` with bounded backoff. Provider calls run after claim commit. Stale answer versions are discarded without writing facts. Schema/safety failures do not retry.

Canonical event `source_type`: DB `free_text` → `extracted`; DB `form` or `user_edit` → `user_entered`. `extractor_version` on events and rows is the prompt version.

## 4. Embedding contract

Projection builder is deterministic and covered by golden fixtures. It emits `projection_schema_version`, ordered field labels and normalized confirmed text. Production retrieval is `EmbeddingsGigaR` with 2560 dimensions. Local prototype uses DS Lab `gte-base` (`vector(768)`) with the same `DSLAB_API_KEY` as extraction; cache key includes source version, projection version and exact model configuration. A vector dimension change requires a new migration/index and parallel backfill; never mix dimensions/models in similarity comparison.

HNSW recall is evaluated against exact cosine on sampled eligible pools. Embedding similarity is a soft feature, not proof of compatibility or a source for sensitive inference.

## 5. Reranking contract

System prompt says: choose only supplied IDs; prioritize mutual compatibility and conversation potential; never infer sensitive facts; return typed JSON. Temperature/config is fixed in `model_version`. Provider deadline is 3 seconds and candidates/tokens are bounded. Unknown/duplicate IDs, reasons referencing forbidden fields, or invalid JSON discard the entire model result and use heuristic order.

Generated reasons use only allowlisted public evidence references, for example `shared_goal` and `prompt_theme`, never exact scores, private facts, inferred traits, location or distance-derived claims. LLM prose is accepted only after a validator confirms its evidence and content policy; a rejected or unavailable reason is omitted rather than replaced with unsafe text.

## 6. Versioning and observability

Restricted `ai_operations` rows record extraction metadata. Do not store raw prompts or responses.

Each AI observation records, with restricted access:

| Field | Purpose |
|---|---|
| `ai_operation_id` | Trace/cost correlation, not public |
| `operation_type` | extraction, embedding, rerank, moderation |
| `prompt_version` / `projection_schema_version` | Exact input contract |
| `model_version` | Provider model + relevant parameters |
| `feature_schema_version` / `ranker_version` | Replay of ordering inputs |
| Source entity IDs + versions | Detect stale output |
| Latency, token counts, estimated cost, result status | Budgets and incidents |
| Safety validation result | Audit fallback/rejection |

Runtime does not store raw payloads. Restricted sampled payload retention for evaluation requires separate consent/purpose, access log and expiry.

## 7. Evaluation and launch gates

### Extraction

Curated consented/redacted set; per-key precision/recall, unsupported-fact rate, user correction/rejection rate and sensitive-trait violation count. Launch gate: zero prohibited-trait outputs in adversarial suite and product-approved per-key precision target (`TBD-ML01`). `TBD-ML01` remains the extraction quality gate only.

### Retrieval/ranking

Hard-filter violation rate must be zero. Measure eligible recall@100 against exact search, diversity, reply/conversation outcomes and block/report/unmatch guardrails.

The rerank quality gate is `rerank-human-pairwise-v1` (separate from `TBD-ML01`). Runtime promotion requires a PII-free passing manifest whose prompt/model/projection versions match config: zero hard-filter/ID-set violations; zero forbidden reasons; valid-result rate ≥95%; LLM wins ≥60% of decisive judgments with 95% Wilson lower bound >50%; ties ≤30%; reviewer κ ≥0.40; p95 latency ≤2.5 s; ≤20 candidates.

`TBD-ML02` cost formula (prototype, YandexGPT Lite): `cost_rub = input_tokens/1000 * rerank_input_price_per_1k_rub + output_tokens/1000 * rerank_output_price_per_1k_rub` with reviewed caps ₽0.50/call and ₽500/day. Default prices in config are ₽0.40/1K input and ₽0.80/1K output. Failed or missing evaluation leaves rerank wired but disabled; production stays heuristic-only.

### Moderation

Measure false negative/positive samples by policy category, appeal overturn rate and time-to-human-review for severe reports. Automated reject is limited to high-confidence policy cases; ambiguous material is held from public view. Approved content may be re-held after a credible report; model decisions are never the final appeal decision.

## 8. Human review and recovery

Trust & Safety reviews held photos/text and reports through restricted tools. Reviewer sees minimum necessary evidence; every access/decision is audited. Provider outage holds new media non-public but does not remove already approved content unless policy requires. Model rollback pins previous `model_version`/prompt; in-flight jobs finish against captured version or are discarded on source drift.

## 9. Later gates

Learned ranking begins only after canonical events are stable, consent/legal basis is confirmed, minimum sample size is set, leakage/bias review passes, shadow evaluation succeeds and rollback is tested. Feature store, model registry service or realtime training are added only when a learned model needs online/offline feature consistency that versioned Postgres snapshots cannot provide.

Social enrichment or agents require a separate design: explicit opt-in per data source/purpose, proof of data subject consent, revocation/deletion propagation, no scraping, no exposure of non-users, scoped tools and confirmation before any external side effect.
