from __future__ import annotations

JOB_TYPE_GENERATE = "generate_recommendation_batch"
POLICY_VERSION = "eligibility-v2"
ELIGIBILITY_VERSION = "eligibility-v2"
RANKER_VERSION = "prototype-heuristic-v1"
FEATURE_SCHEMA_VERSION = "heuristic-v1"
BATCH_SCHEMA_VERSION = 1
ITEM_SCHEMA_VERSION = 1
DAILY_BATCH_QUOTA = 2
MAX_ELIGIBLE = 5000
RETRIEVE_LIMIT = 100
SCORE_LIMIT = 50
BATCH_SIZE = 5
RERANK_POOL = 20
EXPLORATION_SLOTS = 1
ACTIVITY_DAYS = 30
BATCH_TTL_HOURS = 24
CLUSTER_COSINE = 0.92
DIVERSITY_PENALTY = 0.10
TRIGGER_CODES = frozenset({"onboarding_complete", "profile_updated", "refill"})
SURFACES = frozenset({"daily_batch"})
PASS_REASON_CODES = frozenset({"not_my_type", "photos", "location", "other"})
WEIGHTS = {
    "semantic_actor": 0.30,
    "semantic_candidate": 0.20,
    "goal": 0.15,
    "facts": 0.10,
    "distance": 0.10,
    "activity": 0.10,
    "quality": 0.05,
}
