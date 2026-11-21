#!/usr/bin/env python3
"""Compare what an L3 execution delivered to the agent with the frozen L1/L2 treatment.

The Runtime's payload ledger (`payload-ledger.yaml`, aief.payload_ledger)
records every phase brief and `execution next` output it delivered, the Skill
and bound files it pointed to, and a classification of each brief section.
This tool reads that ledger and its snapshots, and the frozen treatment files
(L1 context, L2 plan and verification, the task request), and reports the
comparisons of the re-freeze contract §3:

| Comparison | VERIFIED when |
|---|---|
| `l3_same_l2_plan` | every bound plan delivered has the bytes of the frozen L2 plan |
| `l3_same_l2_verification` | every bound verification delivered has the bytes of the frozen L2 verification |
| `l3_same_l1_content` | every practice delivered in a producer phase brief is, word for word, a practice of the frozen L1 context; practices of reviewer phases (`review-change`) are reported as part of the review intervention |
| `no_additional_task_semantic_facts` | every brief section is classified; the task context carries only the request (objective), its scope and its classification; no snapshot contains a forbidden text (oracle material, for example) |
| `reviewer_feedback_budget` | review feedback reached the agent at most `--rework-maximum` times |
| `no_decision_rationale_leak` | no rationale of a human gate decision appears in a snapshot delivered after it |

The `## Repositories` brief section (repository ids, profiles, engineering
context ids) is L3-only project metadata. The study accepts it as procedural
(decision of 2026-11-21): it says where the Runtime-governed work happens, not
what the change is; it is reported, not counted as a task fact.

A comparison is `VERIFIED`, `FAILED` or `NEEDS_REVIEW` (the tool found
something a person has to judge, listed in `findings`). Review feedback and
human decisions are reported as intervention events: they are part of the L3
intervention, not a failure. The tool reads the records only and never
modifies them.

Usage: compare_payloads.py EXECUTION_DIR --l1-context FILE --l2-plan FILE
       --l2-verification FILE --request TEXT [--forbidden FILE...] [--rework-maximum N] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

VERIFIED, FAILED, NEEDS_REVIEW = "VERIFIED", "FAILED", "NEEDS_REVIEW"
MIN_FORBIDDEN_LINE = 20  # shorter lines (blank, braces, keywords) are too common to mean a leak


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def practices_of_brief(text: str) -> dict[str, str]:
    """Practices quoted in the `## Practices` section of a phase brief: id -> content."""
    if "\n## Practices\n" not in text:
        return {}
    section = text.split("\n## Practices\n", 1)[1]
    result = {}
    for block in re.split(r"\n### ", "\n" + section)[1:]:
        header, _, body = block.partition("\n")
        identifier = header.split()[0]
        lines = body.strip("\n").split("\n")
        if lines and lines[0].startswith("Applies to:"):
            lines = lines[1:]
        result[identifier] = "\n".join(lines).strip()
    return result


def practices_of_context(text: str) -> dict[str, str]:
    """Practices of a frozen L1 context rendered by `aief_experiment.py render-context`: id -> content."""
    result = {}
    for block in re.split(r"\n## ", "\n" + text)[1:]:
        header, _, body = block.partition("\n")
        lines = body.strip("\n").split("\n")
        if lines and lines[0].startswith("Applies to:"):
            lines = lines[1:]
        result[header.strip()] = "\n".join(lines).strip()
    return result


def task_context_lines(text: str) -> list[str]:
    if "\n## Task context\n" not in text:
        return []
    section = text.split("\n## Task context\n", 1)[1].split("\n## ", 1)[0]
    return [line[2:] for line in section.splitlines() if line.startswith("- ")]


def _result(status: str, findings: list[str], **extra: Any) -> dict[str, Any]:
    return {"status": status, "findings": findings, **extra}


ACCEPTED_AS_PROCEDURAL = {"repositories"}  # L3-only brief sections the study accepts as procedural
REVIEWER_SKILLS = {"review-change"}  # phases run by the independent reviewer session, which L2 does not have


def compare(execution_dir: Path, l1_context: Path, l2_plan: Path, l2_verification: Path, request: str,
            forbidden: list[Path] | None = None, rework_maximum: int = 3) -> dict[str, Any]:
    ledger = yaml.safe_load((execution_dir / "payload-ledger.yaml").read_text(encoding="utf-8"))
    execution = yaml.safe_load((execution_dir / "execution.yaml").read_text(encoding="utf-8"))
    briefs: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    snapshots: list[tuple[dict[str, Any], str, str]] = []
    bound: dict[str, list[str]] = {"bound-plan": [], "bound-verification": []}
    sections: list[tuple[int, dict[str, Any]]] = []
    for entry in ledger.get("entries", []):
        for item in entry["items"]:
            if item["base"] != "execution":
                continue
            path = execution_dir / item["path"]
            data = path.read_bytes() if path.is_file() else b""
            if item["kind"] in bound:
                bound[item["kind"]].append(_sha256(data))
            if item["kind"] in {"phase-brief", "execution-next-output"}:
                snapshots.append((entry, item["path"], data.decode("utf-8", errors="replace")))
            if item["kind"] == "phase-brief":
                briefs.append((entry, item, data.decode("utf-8", errors="replace")))
                sections += [(entry["sequence"], section) for section in item.get("sections", [])]

    comparisons: dict[str, Any] = {}
    for key, kind, frozen in (("l3_same_l2_plan", "bound-plan", l2_plan),
                              ("l3_same_l2_verification", "bound-verification", l2_verification)):
        expected = _sha256(frozen.read_bytes())
        delivered = bound[kind]
        wrong = sorted(set(delivered) - {expected})
        status = FAILED if wrong or not delivered else VERIFIED
        comparisons[key] = _result(status, [f"{kind} delivered with sha256 {item}" for item in wrong]
                                   + ([] if delivered else [f"no {kind} was delivered"]),
                                   expectedSha256=expected, deliveries=len(delivered))

    frozen_practices = practices_of_context(l1_context.read_text(encoding="utf-8"))
    findings, delivered_ids, reviewer_only = [], set(), {}
    for entry, _, text in briefs:
        for identifier, content in practices_of_brief(text).items():
            if entry.get("skill") in REVIEWER_SKILLS:
                if frozen_practices.get(identifier) != content:
                    reviewer_only.setdefault(identifier, []).append(entry["phase"])
                continue
            delivered_ids.add(identifier)
            if identifier not in frozen_practices:
                findings.append(f"{entry['phase']}: practice {identifier} is not in the L1 context")
            elif content != frozen_practices[identifier]:
                findings.append(f"{entry['phase']}: practice {identifier} differs from the L1 context")
    comparisons["l3_same_l1_content"] = _result(
        FAILED if findings else VERIFIED, sorted(set(findings)),
        practicesDelivered=sorted(delivered_ids), l1PracticesNotDelivered=sorted(set(frozen_practices) - delivered_ids),
        reviewerPracticesOutsideL1={key: sorted(set(value)) for key, value in reviewer_only.items()})

    facts, review = [], []
    for sequence, section in sections:
        if section["classification"] == "unclassified":
            facts.append(f"entry {sequence}: unclassified brief section {section['heading']!r}")
    for entry, _, text in briefs:
        for line in task_context_lines(text):
            key, _, value = line.partition(": ")
            if key == "objective" and request.strip() not in value:
                facts.append(f"{entry['phase']}: task objective {value!r} does not restate the request")
            elif key not in {"objective", "scope", "classification"}:
                facts.append(f"{entry['phase']}: task context field {key!r} carries information outside the request")
    needs_review = False
    for path in forbidden or []:
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                 if len(line.strip()) >= MIN_FORBIDDEN_LINE]
        for entry, name, text in snapshots:
            leaked = [line for line in lines if line in text]
            if leaked:
                facts.append(f"{name}: contains {len(leaked)} line(s) of {path.name}, first: {leaked[0][:80]!r}")
    procedural = sorted({section["id"] for _, section in sections if section["id"] in ACCEPTED_AS_PROCEDURAL})
    comparisons["no_additional_task_semantic_facts"] = _result(
        FAILED if facts else (NEEDS_REVIEW if needs_review else VERIFIED), facts,
        l3OnlySectionsAcceptedAsProcedural=procedural)

    for sequence, section in sections:
        if section["classification"] in {"review-feedback", "human-decision"}:
            review.append({"entry": sequence, "section": section["heading"], "classification": section["classification"],
                           "sha256": section["sha256"]})
    reworks = {item["section"] for item in review if item["classification"] == "review-feedback"}
    comparisons["reviewer_feedback_budget"] = _result(
        FAILED if len(reworks) > rework_maximum else VERIFIED,
        [f"{len(reworks)} distinct review feedback sections, budget {rework_maximum}"] if len(reworks) > rework_maximum else [],
        reworks=len(reworks), reworkMaximum=rework_maximum, interventionEvents=review)

    leaks = []
    for decision in execution.get("gateDecisions") or []:
        rationale = (decision.get("rationale") or "").strip()
        if not rationale:
            continue
        for entry, name, text in snapshots:
            if entry["at"] > decision["at"] and rationale in text:
                leaks.append(f"{name}: contains the rationale of the {decision['gate']} decision")
    comparisons["no_decision_rationale_leak"] = _result(FAILED if leaks else VERIFIED, leaks)

    statuses = {item["status"] for item in comparisons.values()}
    overall = FAILED if FAILED in statuses else (NEEDS_REVIEW if NEEDS_REVIEW in statuses else VERIFIED)
    return {"execution": (execution.get("metadata") or {}).get("id"), "condition": ledger.get("experimentalCondition"),
            "ledgerEntries": len(ledger.get("entries", [])), "ledgerFingerprint": ledger.get("fingerprint"),
            "treatment": {"l1ContextSha256": _sha256(l1_context.read_bytes()), "l2PlanSha256": _sha256(l2_plan.read_bytes()),
                          "l2VerificationSha256": _sha256(l2_verification.read_bytes())},
            "comparisons": comparisons, "outcome": overall}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("execution_dir", type=Path, help="the L3 execution directory (.ai/runtime/executions/<id>)")
    parser.add_argument("--l1-context", type=Path, required=True)
    parser.add_argument("--l2-plan", type=Path, required=True)
    parser.add_argument("--l2-verification", type=Path, required=True)
    parser.add_argument("--request", required=True, help="the task request, identical in every condition")
    parser.add_argument("--forbidden", type=Path, action="append", default=[],
                        help="a file whose content must never reach the agent (oracle tests, gold patch)")
    parser.add_argument("--rework-maximum", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = compare(args.execution_dir, args.l1_context, args.l2_plan, args.l2_verification, args.request,
                     args.forbidden, args.rework_maximum)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['execution']} ({report['condition']}): {report['outcome']}")
        for name, item in report["comparisons"].items():
            print(f"  {name:36} {item['status']}")
            for finding in item["findings"]:
                print(f"    - {finding}")
            if item.get("reviewNote"):
                print(f"    note: {item['reviewNote']}")
    return 1 if report["outcome"] == FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
