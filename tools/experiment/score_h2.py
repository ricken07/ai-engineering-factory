#!/usr/bin/env python3
"""H2 — reproducibility of acceptance obligations (RC2 §9.2).

For each task, K is the frozen acceptance-vector length: the canonical SWE-bench
`FAIL_TO_PASS` and `PASS_TO_PASS` tests, run only by the independent evaluator
after termination. For two runs r, s of one task–agent–condition block,
D(r, s) = (1/K) Σ_j I[c_rj ≠ c_sj], and D_group is the mean over pairs r < s.

Rules:
- an evaluator failure is distinguished from a tested software failure: a run
  whose evaluation did not complete, or a test the evaluator could not run, is
  `UNAVAILABLE`, never `FAIL`;
- the primary block score is computed only when every predeclared component of
  every run in the block is observed; otherwise the block's primary outcome is
  `MISSING` (it enters the registered sensitivity analyses);
- a secondary "available-checks" pairwise measure is reported with its changing
  denominator explicit.

Input: a JSON file of evaluator results, a list of
`{runId, task, agent, condition, evaluator: {status}, checks: {testId: PASS|FAIL|UNAVAILABLE}}`,
and a JSON acceptance manifest `{task: [testId, ...]}` (the frozen vector order).

Usage: score_h2.py RESULTS.json --manifest MANIFEST.json [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

PASS, FAIL, UNAVAILABLE = "PASS", "FAIL", "UNAVAILABLE"


def vector(result: dict[str, Any], tests: list[str]) -> list[str]:
    """The run's acceptance vector in frozen order; an incomplete evaluation makes every component unavailable."""
    if (result.get("evaluator") or {}).get("status") != "completed":
        return [UNAVAILABLE] * len(tests)
    checks = result.get("checks") or {}
    return [checks.get(test) if checks.get(test) in {PASS, FAIL} else UNAVAILABLE for test in tests]


def disagreement(a: list[str], b: list[str]) -> float | None:
    """D(r, s) over all K components, or None when a component of either run is unavailable."""
    if UNAVAILABLE in a or UNAVAILABLE in b:
        return None
    return sum(x != y for x, y in zip(a, b)) / len(a)


def available_disagreement(a: list[str], b: list[str]) -> tuple[float | None, int]:
    """Secondary measure over the components observed in both runs, with that denominator."""
    pairs = [(x, y) for x, y in zip(a, b) if x != UNAVAILABLE and y != UNAVAILABLE]
    return (sum(x != y for x, y in pairs) / len(pairs), len(pairs)) if pairs else (None, 0)


def score(results: list[dict[str, Any]], manifest: dict[str, list[str]]) -> list[dict[str, Any]]:
    blocks: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for result in results:
        blocks.setdefault((result["task"], result["agent"], result["condition"]), []).append(result)
    report = []
    for (task, agent, condition), runs in sorted(blocks.items()):
        tests = manifest[task]
        vectors = {run["runId"]: vector(run, tests) for run in runs}
        pairs = list(combinations(sorted(vectors), 2))
        primary = [disagreement(vectors[r], vectors[s]) for r, s in pairs]
        secondary = [available_disagreement(vectors[r], vectors[s]) for r, s in pairs]
        unavailable = sorted(run for run, values in vectors.items() if UNAVAILABLE in values)
        if len(runs) < 2:
            outcome, value = "MISSING", None
            reason = "fewer than two runs in the block"
        elif any(item is None for item in primary):
            outcome, value = "MISSING", None
            reason = "unavailable components in runs " + ", ".join(unavailable)
        else:
            outcome, value, reason = "OBSERVED", sum(primary) / len(primary), None
        report.append({
            "task": task, "agent": agent, "condition": condition, "K": len(tests), "runs": len(runs), "pairs": len(pairs),
            "primary": {"outcome": outcome, "dGroup": value, "reason": reason},
            "secondaryAvailableChecks": [{"pair": [r, s], "d": d, "denominator": n}
                                         for (r, s), (d, n) in zip(pairs, secondary)],
        })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = score(json.loads(args.results.read_text()), json.loads(args.manifest.read_text()))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for block in report:
            value = "-" if block["primary"]["dGroup"] is None else f"{block['primary']['dGroup']:.4f}"
            print(f"{block['task']} {block['agent']} {block['condition']}: D_group {value} "
                  f"({block['primary']['outcome']}{', ' + block['primary']['reason'] if block['primary']['reason'] else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
