CREATE DATABASE IF NOT EXISTS ai_dating;

CREATE TABLE IF NOT EXISTS ai_dating.raw_events
(
    event_id UUID,
    event_name LowCardinality(String),
    schema_version UInt16,
    occurred_at DateTime64(3, 'UTC'),
    occurred_date Date MATERIALIZED toDate(occurred_at),
    producer LowCardinality(String),
    owner LowCardinality(String),
    actor_account_id Nullable(UUID),
    subject_account_id Nullable(UUID),
    recommendation_batch_id Nullable(UUID),
    recommendation_item_id Nullable(UUID),
    match_id Nullable(UUID),
    conversation_id Nullable(UUID),
    request_id String,
    experiment_assignments String,
    privacy_classification LowCardinality(String),
    properties String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (event_name, occurred_date, event_id);
