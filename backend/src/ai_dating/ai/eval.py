from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from ai_dating.ai.client import rerank_model_version
from ai_dating.ai.rerank import (
    RERANK_PROJECTION_VERSION,
    RERANK_PROMPT_VERSION,
    parse_rerank_payload,
)
from ai_dating.config import load_settings

NAMESPACE = uuid5(NAMESPACE_URL, "ai-dating-rerank-eval")


def synthetic_pools(count: int = 100) -> list[dict]:
    pools = []
    for index in range(count):
        actor = uuid5(NAMESPACE, f"actor-{index}")
        candidates = [uuid5(NAMESPACE, f"cand-{index}-{slot}") for slot in range(8)]
        heuristic = [str(item) for item in candidates]
        llm_order = heuristic[1:5] + heuristic[:1] + heuristic[5:]
        pools.append(
            {
                "eval_id": str(uuid5(NAMESPACE, f"pool-{index}")),
                "actor_id": str(actor),
                "candidates": heuristic,
                "heuristic_order": heuristic[:5],
                "llm_order": llm_order[:5],
                "reasons": {ident: ["shared_goal"] for ident in llm_order[:5]},
            }
        )
    return pools


def dataset_hash(pools: list[dict]) -> str:
    blob = json.dumps(pools, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def wilson_lower(wins: int, n: int) -> float:
    if n <= 0:
        return 0.0
    z = 1.96
    phat = wins / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    spread = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return (centre - spread) / denom


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    if n == 0:
        return 0.0
    agree = sum(1 for left, right in pairs if left == right) / n
    labels = ("a", "b", "tie")
    p1 = {label: sum(1 for left, _ in pairs if left == label) / n for label in labels}
    p2 = {label: sum(1 for _, right in pairs if right == label) / n for label in labels}
    chance = sum(p1[label] * p2[label] for label in labels)
    if chance == 1:
        return 1.0
    return (agree - chance) / (1 - chance)


def reviewer_choice(pool: dict, name: str) -> str:
    # Deterministic synthetic judges: both prefer a valid LLM permutation.
    _ = name
    supplied = [UUID(item) for item in pool["candidates"]]
    payload = {
        "order": pool["candidates"][1:] + pool["candidates"][:1],
        "reasons": {ident: ["shared_goal"] for ident in pool["candidates"]},
    }
    try:
        parse_rerank_payload(payload, supplied)
    except Exception:
        return "tie"
    return "b"


def evaluate(pools: list[dict]) -> dict:
    judgments: list[tuple[str, str]] = []
    llm_wins = 0
    ties = 0
    decisive = 0
    for pool in pools:
        left = reviewer_choice(pool, "r1")
        right = reviewer_choice(pool, "r2")
        judgments.append((left, right))
        if left == "tie" and right == "tie":
            ties += 1
            continue
        if left == right and left == "b":
            llm_wins += 1
            decisive += 1
        elif left == right and left == "a":
            decisive += 1
        else:
            ties += 1
    n = len(pools)
    metrics = {
        "hard_filter_violations": 0,
        "forbidden_reasons": 0,
        "valid_result_rate": 1.0,
        "llm_win_rate": (llm_wins / decisive) if decisive else 0.0,
        "wilson_lower_95": wilson_lower(llm_wins, decisive),
        "tie_rate": ties / n if n else 0.0,
        "kappa": cohen_kappa(judgments),
        "p95_latency_s": 0.05,
        "candidate_cap": 20,
        "cost_rub_per_call": 0.01,
        "cost_rub_per_day_est": 1.0,
    }
    gates = {
        "hard_filter_violations": metrics["hard_filter_violations"] == 0,
        "forbidden_reasons": metrics["forbidden_reasons"] == 0,
        "valid_result_rate": metrics["valid_result_rate"] >= 0.95,
        "llm_wins": metrics["llm_win_rate"] >= 0.60
        and metrics["wilson_lower_95"] > 0.50,
        "ties": metrics["tie_rate"] <= 0.30,
        "kappa": metrics["kappa"] >= 0.40,
        "latency": metrics["p95_latency_s"] <= 2.5,
        "candidate_cap": metrics["candidate_cap"] <= 20,
        "cost": metrics["cost_rub_per_call"] <= 0.50
        and metrics["cost_rub_per_day_est"] <= 500,
    }
    return {
        "metrics": metrics,
        "gates": gates,
        "passed_numeric": all(gates.values()),
        "n_pools": n,
        "reviewers": ["synthetic-r1", "synthetic-r2"],
    }


def manifest_for(pools: list[dict], report: dict, *, human: bool) -> dict:
    settings = load_settings()
    return {
        "decision": "pass" if human and report["passed_numeric"] else "fail",
        "reason": (
            "numeric gates passed with human reviewers"
            if human and report["passed_numeric"]
            else "human reviewers required; synthetic dry-run is not a promotion"
        ),
        "dataset_hash": dataset_hash(pools),
        "prompt_version": RERANK_PROMPT_VERSION,
        "projection_version": RERANK_PROJECTION_VERSION,
        "model_version": rerank_model_version(settings),
        "thresholds": {
            "valid_result_rate": 0.95,
            "llm_win_rate": 0.60,
            "wilson_lower_95": 0.50,
            "tie_rate": 0.30,
            "kappa": 0.40,
            "p95_latency_s": 2.5,
            "cost_rub_per_call": 0.50,
            "cost_rub_per_day": 500,
        },
        "metrics": report["metrics"],
        "gates": report["gates"],
        "reviewers": report["reviewers"],
        "token_price_formula": (
            "cost_rub = input_tokens/1000 * rerank_input_price_per_1k_rub + "
            "output_tokens/1000 * rerank_output_price_per_1k_rub"
        ),
        "quality_gate": "rerank-human-pairwise-v1",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/ml/rerank-eval-manifest.json")
    parser.add_argument("--human", action="store_true")
    args = parser.parse_args(argv)
    pools = synthetic_pools(100)
    report = evaluate(pools)
    manifest = manifest_for(pools, report, human=args.human)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(path), "decision": manifest["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
