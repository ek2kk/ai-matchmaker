from ai_dating.ai.eval import dataset_hash, evaluate, manifest_for, synthetic_pools


def test_synthetic_eval_is_deterministic_and_not_promoted():
    pools = synthetic_pools(100)
    assert len(pools) == 100
    assert dataset_hash(pools) == dataset_hash(synthetic_pools(100))
    report = evaluate(pools)
    assert report["metrics"]["hard_filter_violations"] == 0
    manifest = manifest_for(pools, report, human=False)
    assert manifest["decision"] == "fail"
    assert manifest["quality_gate"] == "rerank-human-pairwise-v1"
    assert "account" not in json_blob(manifest)


def json_blob(payload: dict) -> str:
    import json

    return json.dumps(payload).lower()
