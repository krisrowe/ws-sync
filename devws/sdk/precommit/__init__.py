"""Precommit scanning SDK - regex patterns + entropy detection."""
import re
import random
from devws.sdk.precommit.scanner import run_scan, load_regex_patterns
from devws.sdk.precommit.entropy import (
    check_secret, test_patterns, shannon_entropy,
    load_patterns, generate_from_pattern
)


def run_full_pattern_test(seed: int = 42) -> dict:
    """
    Run all test patterns through full detection (regex + entropy).

    Returns dict with results and summary - CLI handles formatting.
    """
    data = load_patterns()
    regex_patterns = load_regex_patterns()
    rng = random.Random(seed)

    results = []
    for p in data.get("patterns", []):
        example = generate_from_pattern(p["pattern"], rng)
        expect_flag = p.get("expect") == "flag"

        # Check regex
        regex_match = False
        for pattern in regex_patterns:
            try:
                if re.search(pattern, example):
                    regex_match = True
                    break
            except re.error:
                pass

        # Check entropy
        entropy_result = check_secret(example)
        entropy_flag = entropy_result["flagged"]

        # Final: flagged if EITHER catches it
        final_flag = regex_match or entropy_flag
        correct = expect_flag == final_flag

        results.append({
            "id": p.get("id", ""),
            "expect": p.get("expect", "pass"),
            "regex_match": regex_match,
            "entropy_flag": entropy_flag,
            "entropy_val": entropy_result["entropy"],
            "exception": entropy_result.get("exception"),
            "final_flag": final_flag,
            "correct": correct
        })

    # Summary
    tp = sum(1 for r in results if r["final_flag"] and r["expect"] == "flag")
    fp = sum(1 for r in results if r["final_flag"] and r["expect"] == "pass")
    tn = sum(1 for r in results if not r["final_flag"] and r["expect"] == "pass")
    fn = sum(1 for r in results if not r["final_flag"] and r["expect"] == "flag")

    return {
        "results": results,
        "summary": {
            "total": len(results),
            "correct": sum(1 for r in results if r["correct"]),
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "accuracy": sum(1 for r in results if r["correct"]) / len(results) if results else 0
        }
    }


def list_test_patterns() -> dict:
    """
    List all test patterns from YAML.

    Returns dict with patterns - CLI handles formatting.
    """
    data = load_patterns()
    return {
        "seed": data.get("seed", 42),
        "patterns": data.get("patterns", [])
    }


__all__ = [
    "run_scan", "check_secret", "test_patterns", "shannon_entropy",
    "run_full_pattern_test", "list_test_patterns"
]
