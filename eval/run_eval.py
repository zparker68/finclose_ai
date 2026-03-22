"""
finclose_ai/eval/run_eval.py
─────────────────────────────
RAGAS-style evaluation framework for FinClose AI.

Scores each test query on 4 dimensions:
  - faithfulness:        Did the response cite real data from the DB?
  - accuracy:            Are key numbers/facts correct?
  - sox_recall:          Did it catch expected SOX flag types?
  - verdict_correctness: Is the verdict within the expected range?

Usage:
  cd finclose_ai && python eval/run_eval.py
  python eval/run_eval.py --query-id q_anomaly_01   # run a single query
  python eval/run_eval.py --skip-ollama              # schema/structure checks only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ROOT)

# ── Load eval data ─────────────────────────────────────────────────────────────
_EVAL_DIR = os.path.dirname(__file__)
QUERIES_FILE = os.path.join(_EVAL_DIR, "test_queries.json")
GROUND_TRUTH_FILE = os.path.join(_EVAL_DIR, "ground_truth.json")


def load_queries() -> list[dict]:
    with open(QUERIES_FILE) as f:
        return json.load(f)


def load_ground_truth() -> dict:
    with open(GROUND_TRUTH_FILE) as f:
        return json.load(f)


# ── Scoring functions ─────────────────────────────────────────────────────────

def score_faithfulness(response: str, gt: dict) -> float:
    """
    Check how many faithfulness anchors (real data terms) appear in the response.
    Anchors are keywords that only appear if the model actually used retrieved data.
    """
    anchors = gt.get("faithfulness_anchors", [])
    if not anchors:
        return 1.0
    hits = sum(1 for anchor in anchors if re.search(re.escape(anchor), response, re.IGNORECASE))
    return round(hits / len(anchors), 3)


def score_accuracy(response: str, gt: dict) -> float:
    """
    Check how many accuracy patterns (key facts, numbers) appear in the response.
    """
    checks = gt.get("accuracy_checks", [])
    if not checks:
        return 1.0
    hits = sum(1 for check in checks if re.search(check["pattern"], response, re.IGNORECASE))
    return round(hits / len(checks), 3)


def score_sox_recall(actual_flags: list[str], gt: dict) -> float:
    """
    Check whether the required SOX flag types were raised.
    """
    required = gt.get("required_flag_types", [])
    min_flags = gt.get("min_sox_flags", 0)

    if not required and min_flags == 0:
        return 1.0

    type_hits = sum(1 for flag in required if flag in actual_flags)
    type_score = type_hits / len(required) if required else 1.0

    count_score = 1.0 if len(actual_flags) >= min_flags else len(actual_flags) / max(min_flags, 1)

    return round((type_score + count_score) / 2, 3)


def score_verdict(verdict: str, gt: dict) -> float:
    """Binary: 1.0 if verdict is in expected range, 0.0 otherwise."""
    required_verdicts = gt.get("required_verdicts", [])
    if not required_verdicts:
        return 1.0
    return 1.0 if verdict in required_verdicts else 0.0


def score_keywords(response: str, gt: dict) -> float:
    """Check required keywords appear in response."""
    keywords = gt.get("required_keywords", [])
    if not keywords:
        return 1.0
    hits = sum(1 for kw in keywords if re.search(re.escape(kw), response, re.IGNORECASE))
    return round(hits / len(keywords), 3)


def compute_overall(scores: dict) -> float:
    """Weighted average: faithfulness 35%, accuracy 25%, sox_recall 20%, verdict 10%, keywords 10%"""
    weights = {
        "faithfulness": 0.35,
        "accuracy": 0.25,
        "sox_recall": 0.20,
        "verdict_correctness": 0.10,
        "keyword_coverage": 0.10,
    }
    return round(sum(scores.get(k, 0) * w for k, w in weights.items()), 3)


# ── Run evaluation ─────────────────────────────────────────────────────────────

def evaluate_query(query_id: str, query: str, period: str, gt: dict, skip_ollama: bool) -> dict:
    """Run one query through the pipeline and score the result."""
    from pipeline import run_pipeline

    if skip_ollama:
        # Return a zeroed-out result for schema validation only
        return {
            "query_id": query_id,
            "skipped": True,
            "scores": {"faithfulness": 0, "accuracy": 0, "sox_recall": 0,
                       "verdict_correctness": 0, "keyword_coverage": 0, "overall": 0},
        }

    t0 = time.time()
    try:
        state = run_pipeline(query=query, period=period, requested_by="eval")
        elapsed = round((time.time() - t0) * 1000, 1)

        response = state.final_response or ""
        actual_flags = [f.value for f in state.sox_flags]
        verdict = state.critic_verdict or ""

        scores = {
            "faithfulness":       score_faithfulness(response, gt),
            "accuracy":           score_accuracy(response, gt),
            "sox_recall":         score_sox_recall(actual_flags, gt),
            "verdict_correctness": score_verdict(verdict, gt),
            "keyword_coverage":   score_keywords(response, gt),
        }
        scores["overall"] = compute_overall(scores)

        return {
            "query_id":        query_id,
            "query":           query,
            "period":          period,
            "verdict":         verdict,
            "confidence":      state.confidence_score,
            "sox_flags":       actual_flags,
            "processing_ms":   elapsed,
            "scores":          scores,
            "skipped":         False,
            "error":           None,
        }

    except Exception as exc:
        return {
            "query_id": query_id,
            "query":    query,
            "error":    str(exc),
            "skipped":  False,
            "scores":   {"faithfulness": 0, "accuracy": 0, "sox_recall": 0,
                         "verdict_correctness": 0, "keyword_coverage": 0, "overall": 0},
        }


def run_eval(query_filter: str | None = None, skip_ollama: bool = False) -> dict:
    """Run full evaluation suite and return results."""
    queries = load_queries()
    ground_truth = load_ground_truth()

    if query_filter:
        queries = [q for q in queries if q["query_id"] == query_filter]
        if not queries:
            print(f"[error] No query found with id '{query_filter}'")
            sys.exit(1)

    results = []
    print(f"\nFinClose AI — Evaluation Run")
    print(f"Queries: {len(queries)} | Ollama: {'SKIPPED' if skip_ollama else 'ENABLED'}")
    print("─" * 72)

    for i, q in enumerate(queries, 1):
        qid = q["query_id"]
        gt = ground_truth.get(qid, {})
        print(f"[{i:02d}/{len(queries)}] {qid} ... ", end="", flush=True)

        result = evaluate_query(
            query_id=qid,
            query=q["query"],
            period=q.get("period", "2024-12"),
            gt=gt,
            skip_ollama=skip_ollama,
        )
        results.append(result)

        if result.get("skipped"):
            print("SKIPPED")
        elif result.get("error"):
            print(f"ERROR: {result['error'][:60]}")
        else:
            s = result["scores"]
            print(
                f"overall={s['overall']:.2f} | "
                f"faith={s['faithfulness']:.2f} | "
                f"acc={s['accuracy']:.2f} | "
                f"sox={s['sox_recall']:.2f} | "
                f"verdict={s['verdict_correctness']:.0f}"
            )

    # Aggregate
    scored = [r for r in results if not r.get("skipped") and not r.get("error")]
    summary = {}
    if scored:
        for metric in ["faithfulness", "accuracy", "sox_recall", "verdict_correctness",
                       "keyword_coverage", "overall"]:
            vals = [r["scores"][metric] for r in scored]
            summary[metric] = round(sum(vals) / len(vals), 3)

    print("\n" + "─" * 72)
    print("SUMMARY")
    print("─" * 72)
    if summary:
        print(f"  Queries scored:       {len(scored)} / {len(queries)}")
        print(f"  Overall score:        {summary.get('overall', 0):.1%}")
        print(f"  Faithfulness:         {summary.get('faithfulness', 0):.1%}  (target: ≥85%)")
        print(f"  Accuracy:             {summary.get('accuracy', 0):.1%}")
        print(f"  SOX recall:           {summary.get('sox_recall', 0):.1%}")
        print(f"  Verdict correctness:  {summary.get('verdict_correctness', 0):.1%}")
        print(f"  Keyword coverage:     {summary.get('keyword_coverage', 0):.1%}")

        faith = summary.get("faithfulness", 0)
        if faith >= 0.85:
            print(f"\n  ✅ Faithfulness {faith:.1%} meets the 85% bar — README claim valid")
        else:
            print(f"\n  ⚠️  Faithfulness {faith:.1%} is below 85% — do not claim in README yet")
    else:
        print("  No scored results (all skipped or errored)")

    # Export results
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    out_path = os.path.join(_EVAL_DIR, f"results_{date_str}.json")
    output = {
        "run_date":   datetime.utcnow().isoformat() + "Z",
        "query_count": len(queries),
        "scored":     len(scored),
        "summary":    summary,
        "results":    results,
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved → {out_path}\n")

    return output


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinClose AI — Evaluation Runner")
    parser.add_argument("--query-id", help="Run a single query by ID (e.g. q_anomaly_01)")
    parser.add_argument("--skip-ollama", action="store_true",
                        help="Skip pipeline execution — validate schema only")
    args = parser.parse_args()

    run_eval(query_filter=args.query_id, skip_ollama=args.skip_ollama)
