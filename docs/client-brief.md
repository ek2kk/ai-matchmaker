# AI Dating MVP: client brief

> **Status:** Local prototype approved; closed-beta preparation planned
> **Owner:** founder  
> **Updated:** 2026-08-25  
> **Related:** [Architecture overview](architecture/overview.md)

## 1. Product outcome

AI Dating помогает взрослому пользователю получить небольшую подборку взаимно совместимых знакомств вместо бесконечного swipe feed. За 3–5 минут пользователь описывает себя и желаемого партнёра, проверяет извлечённые AI факты и получает до пяти объяснимых intro cards.

Основной риск MVP не технический, а рыночный: без плотного eligible supply даже хороший ranker не создаст ценность. Поэтому запуск ограничен одним сегментом и одной географией.

**Decision P-01:** prototype поддерживает `dating` и `friendship` только на synthetic data. Первая real-user closed beta запускается в Москве в режиме `dating` для 21–35 лет; `friendship` открывается отдельной cohort только после отдельной supply/safety проверки. Для dating используются стабильные goal codes `serious_relationship`, `friends_with_benefits`, `unsure`; beta поддерживает heterosexual matching для `gender_code` `man|woman`.

## 2. Целевые пользователи

| Persona | Потребность | Что даёт MVP |
|---|---|---|
| Новый пользователь | Быстро понять, есть ли релевантные люди | Onboarding 3–5 минут, затем до 5 intro cards |
| Пользователь с ясными критериями | Не видеть заведомо несовместимых людей | Reciprocal hard filters до ranking |
| Пользователь, уставший от swipe | Получать ограниченный, осмысленный выбор | Небольшие batch, причины совместимости, без infinite feed |
| Trust & Safety operator | Разбирать жалобы и исключать опасный контент | Report queue, moderation state, audit trail |

## 3. Critical journeys

1. В local prototype пользователь создаёт `login + password`, затем подтверждает возраст 21+, обязательные consents и Москву как coarse location. Реальный closed beta использует отдельный SMS OTP flow; local credentials описаны в [authentication design](authentication/design.md).
2. Заполняет раздельно `self profile` и `desired partner`, проверяет AI-extracted `profile_facts`.
3. В prototype опционально калибрует soft preferences на явно обозначенных synthetic demo profiles. Эти действия не создают реальные likes или matches и не входят в первую beta cohort.
4. Получает `recommendation_batch` максимум из пяти кандидатов, прошедших взаимные hard filters и safety checks.
5. Открывает card, выбирает `like` или `pass`; при взаимном like создаётся `match`.
6. После match начинает conversation; может в любой момент `unmatch`, `block` или `report`.
7. Может приостановить visibility, экспортировать данные или запросить удаление аккаунта.

## 4. MVP scope

| Must ship | Later / не входит в MVP |
|---|---|
| Local login/password auth, 21+ gate, consent | Social scraping или enrichment без informed consent |
| Self profile, desired partner, photos, prompts | Autonomous dating agents |
| Reciprocal eligibility и safety exclusions | Infinite swipe feed |
| Embedding retrieval + heuristic ranker + bounded LLM reranker | Learned ranking model, feature store, realtime ML platform |
| До 5 recommendations в batch, deterministic audit/reconstruction | Multi-region active-active и отдельные microservices |
| Like/pass, reciprocal match, messages | Voice/video calls, payments, boosts |
| Block/report/moderation и privacy controls | Автоматические действия от имени пользователя |
| Canonical events и продуктовые funnel metrics | Kafka до появления измеримой нагрузки/fan-out |

## 5. Product rules

- Hard filters имеют приоритет над embedding, heuristic и LLM scores. Ни один ranker не может вернуть исключённого кандидата.
- Совместимость должна быть взаимной: оба пользователя принимают возраст, gender intent, geography/distance и relationship goal друг друга.
- `block` действует немедленно в обе стороны для recommendations, matches, conversations и profile access.
- Private facts не попадают в public reason или model prompt без явной purpose-specific необходимости.
- Demo calibration не создаёт `impression`, `like`, `pass` или `match` для реальных пользователей.
- Recommendation reason является snapshot: клиент получает только сохранённую, прошедшую policy check версию.
- Reason генерируется только из allowlisted публичных полей; policy validator отклоняет private, inferred и location-derived claims. При его failure карточка остаётся без reason.
- В beta пользователь получает до двух batch в сутки по пять items; второй генерируется только после terminal actions по всем items первого. No-repeat сохраняется.
- При `insufficient_supply` пользователь может явно запросить помеченный exploratory batch только из полностью reciprocal-eligible pool; hard filters никогда не ослабляются.
- Реальная beta cohort выходит из waitlist только когда reciprocal-eligibility graph даёт ей достаточный reserve active candidates; это не отдельная quota по полу или возрасту.
- Likes не являются единственной optimization target. Reply, sustained conversation, unmatch/report/block и retention имеют больший вес при последующем обучении.

## 6. Success and guardrails

Числовые targets ниже являются launch hypotheses, а не подтверждёнными baseline.

| Metric | Closed-beta target | Guardrail / interpretation |
|---|---:|---|
| Onboarding completion | ≥ 70% начавших | Отдельно измерять шаг с максимальным drop-off |
| Time to first ready batch | p95 ≤ 60 s после `profile_activated` | Completion → activation moderation latency измеряется отдельно; UI показывает pending state |
| Eligible supply | ≥ 20 reciprocal candidates для 80% activated users | При меньшем supply не масштабировать acquisition |
| Candidate coverage | ≥ 80% eligible pool рассмотрено retrieval за 7 дней | Не путать с impression coverage |
| Impression → open | ≥ 35% | Диагностический signal, не objective сам по себе |
| Reciprocal like → match | Измерить baseline | Не задавать target до достаточной выборки |
| Match → first message | ≥ 50% | Контролировать spam/rate limits |
| First message → reply in 48 h | ≥ 35% | Более качественный proxy, чем like rate |
| Block + report per 100 matches | Не ухудшается от baseline; любой severe incident разбирается | Запуск останавливается при непроработанном severe incident |
| Week-4 retained activated users | Измерить baseline | Не оптимизировать до плотного supply |

## 7. Acceptance criteria

- `AC-P01`: после user-controlled onboarding новый пользователь получает `profile_activation_pending`, затем ready batch, `generation_pending` или `insufficient_supply`; пустой экран не считается успехом.
- `AC-P02`: тестовая матрица доказывает reciprocal hard filters, block и moderation exclusions до ranking и повторно до delivery.
- `AC-P03`: каждое реальное exposure связано с сохранёнными `recommendation_batch_id` и `recommendation_item_id`.
- `AC-P04`: одну и ту же пару нельзя повторно показать после зарегистрированного impression в рамках MVP policy.
- `AC-P05`: пользователь видит и может исправить AI-extracted facts до их применения в recommendation.
- `AC-P06`: `block` немедленно скрывает обе стороны и создаёт security audit record без раскрытия причины заблокированному пользователю.
- `AC-P07`: продуктовые метрики можно пересчитать из versioned canonical events с дедупликацией по `event_id`.

## 8. Decision register

| ID | Priority | Decision | Recommended default |
|---|---|---|---|
| `P01` | Decided | Первый регион, age band и relationship segment | Москва, 21–35, `dating` в первой beta; `friendship` prototype-only |
| `P02` | Decided | Политика age/location verification и допустимая точность location | DOB declaration + 21–35 beta policy; выбранная coarse area в Москве, без continuous GPS и client-visible distance |
| `TBD-SEC01` | Closed-beta gate | Retention/deletion по launch jurisdiction | Legal review до real-user closed beta; conservative defaults из [privacy-safety](architecture/privacy-safety.md) |
| `OPS01` | Decided with risk | Кто владеет moderation queue и incident response | Founder; invite-only beta, best effort staffed hours, public launch требует backup owner |
| `TBD-P03` | Important | Можно ли повторно показывать кандидата после существенного profile change | Нет в MVP; вернуться при исчерпании supply |
| `P04` | Decided | Taxonomy и semantics для gender/orientation/relationship goal | `man|woman`, `heterosexual`, три dating goals; `friendship` prototype-only до отдельного beta decision |
