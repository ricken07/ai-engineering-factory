#!/usr/bin/env python3
"""Map the Runtime facts of an L3 run to its study outcome.

The Runtime records what happened (execution status, blocking or
cancellation reason, gate decisions, integration). The study classifies it.
This mapping is applied outside the Runtime and never rewrites a recorded
fact: it reads the records the launcher collected and writes its own
`study-outcome.yaml` next to them, with the facts it used copied verbatim.

Outcomes, in order of precedence:

| Outcome | When |
|---|---|
| `protocol-deviation` | a gate decision departs from the decision rule (tools/experiment/check_decisions.py), a review finding was waived, review waivers were not disabled, or the execution was cancelled without a gate decision |
| `setup-invalid` | the deciding rejection is classified setup-invalid by the rule, or the execution is blocked because required enforcement is unavailable on the runner |
| `operationally-invalid` | the deciding gate expired; eligible for one predeclared replay |
| `incomplete` | the execution or its integration still waits for a human when the run is collected: the run is not finished and is not scored |
| `execution-failure` | the deciding rejection is attributed to the execution, the execution failed, review rework is exhausted, the execution is left blocked for any other reason, or the agent stopped before the execution ended |
| `completed` | the execution is completed and, when `before-merge` is required, its integration is integrated |

The task oracle is separate: `completed` says the governed execution ended as
the protocol requires, not that the change is correct.

Usage: study_outcome.py RUN_DIR... --rule-sha256 HASH [--write] [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import yaml

_spec = importlib.util.spec_from_file_location("check_decisions", Path(__file__).with_name("check_decisions.py"))
check_decisions = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(check_decisions)

MAPPING_VERSION = "1"
OUTPUT = "study-outcome.yaml"


def _facts(execution: dict[str, Any]) -> dict[str, Any]:
    """The Runtime facts the mapping reads, copied verbatim."""
    keys = ("status", "blockingReason", "cancelledReason", "integration")
    facts = {key: execution[key] for key in keys if key in execution}
    facts["reviewWaivers"] = (execution.get("reproducibility", {}).get("reviewWaivers") or {}).get("value")
    facts["findingDecisions"] = len(execution.get("findingDecisions") or [])
    return facts


def outcome(execution: dict[str, Any], report: dict[str, Any]) -> tuple[str, str]:
    """`report` is the check_decisions report of the same execution. Returns (outcome, reason)."""
    status = execution.get("status")
    decisions = report["decisions"]
    integration = (execution.get("integration") or {}).get("status")
    deviations = [f"{item['gate']}: {'; '.join(item['deviations'])}" for item in decisions if not item["conforms"]]
    if deviations:
        return "protocol-deviation", "; ".join(deviations)
    if execution.get("findingDecisions"):
        return "protocol-deviation", "a review finding was waived"
    waivers = (execution.get("reproducibility", {}).get("reviewWaivers") or {}).get("value")
    if waivers != "disabled":
        return "protocol-deviation", f"review waivers are {waivers!r}, not 'disabled'"
    closing = [item for item in decisions if item["decision"] in {"rejected", "expired"}]
    if closing:
        deciding = closing[-1]
        label = deciding["classification"]
        if label == "protocol-gap":
            return "protocol-deviation", f"{deciding['gate']} rejected without a comparator"
        return label, f"{deciding['gate']} {deciding['decision']}"
    if status == "cancelled":
        return "protocol-deviation", f"cancelled without a gate decision: {execution.get('cancelledReason')}"
    if status == "waiting-approval" or integration == "awaiting-approval":
        return "incomplete", "a human gate was still waiting when the run was collected"
    if status == "failed":
        return "execution-failure", "the execution failed"
    if status == "blocked":
        reason = (execution.get("blockingReason") or {}).get("type")
        if reason == "enforcement-unavailable":
            return "setup-invalid", "required enforcement is unavailable on the runner"
        return "execution-failure", f"blocked: {reason}"
    if status == "completed":
        if integration in {None, "integrated"}:
            return "completed", "completed" + (" and integrated" if integration else "")
        return "execution-failure", f"integration {integration}"
    return "execution-failure", f"the agent stopped while the execution was {status}"


def classify_run(run_dir: Path, rule_sha256: str) -> dict[str, Any]:
    path, repo, initial = check_decisions._target(run_dir)
    if not path.is_file():
        return {"run": str(run_dir), "mappingVersion": MAPPING_VERSION, "outcome": "incomplete",
                "reason": "no collected execution (run the launcher's finish first)", "runtimeFacts": {}}
    execution = check_decisions._load(path)
    report = check_decisions.check_execution(path, rule_sha256, None, repo, initial)
    result, reason = outcome(execution, report)
    return {"run": str(run_dir), "execution": report["execution"], "mappingVersion": MAPPING_VERSION,
            "decisionRuleSha256": rule_sha256, "outcome": result, "reason": reason,
            "replayEligible": result == "operationally-invalid",
            "runtimeFacts": _facts(execution),
            "decisions": [{key: item[key] for key in ("gate", "decision", "comparatorOutcome", "classification", "conforms")}
                          for item in report["decisions"]]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="+", type=Path, help="launcher run directories")
    parser.add_argument("--rule-sha256", required=True, help="SHA-256 of the pinned decision rule")
    parser.add_argument("--write", action="store_true", help=f"write {OUTPUT} into each run directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = [classify_run(run, args.rule_sha256) for run in args.runs]
    if args.write:
        for run, result in zip(args.runs, results):
            (run / OUTPUT).write_text(yaml.safe_dump(result, sort_keys=False, allow_unicode=True), encoding="utf-8")
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            print(f"{result['run']}: {result['outcome']} ({result['reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
