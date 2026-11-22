#!/usr/bin/env python3
"""H3 — verified evidence completeness (RC2 §9.3), skeleton.

VerifiedEvidenceCompleteness_r = independently verified required evidence items
/ required evidence items, over the common checklist E01–E12. Evidence is
credited only when the item was produced or durably preserved during the
execution — by the run itself or by a common, condition-neutral execution-time
capture mechanism explicitly permitted for that item — and independently
verified. Post-hoc evaluator outputs never satisfy an item.

Per item the scorer records `VERIFIED`, `MISSING` (absence established) or
`UNAVAILABLE` (study infrastructure corrupted or inaccessible). A run with an
`UNAVAILABLE` required item has no primary score (it enters the
sensitivity/missingness analyses); otherwise the score is the verified share.

Items E01–E04 and E10–E12 have built-in verifiers over the launcher's
execution-time capture (`run.yaml`, `final/`), the permitted common mechanism.
Items E05–E09 depend on each task's evidence manifest (exact evidence object,
path, production boundary and independent verification, RC2 §9.3): until the
manifest gives them, they are reported `UNAVAILABLE` with the reason
"task manifest required", or taken from an observation file the task-specific
verifiers produce.

Usage: score_h3.py RUN_DIR [--manifest MANIFEST.yaml] [--observations OBS.json] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

VERIFIED, MISSING, UNAVAILABLE = "VERIFIED", "MISSING", "UNAVAILABLE"
ITEMS = {
    "E01": "Task identity/reference",
    "E02": "Starting revision",
    "E03": "Resulting patch digest",
    "E04": "Changed-file inventory",
    "E05": "Reported verification command/log",
    "E06": "Verification outcome linked to code revision",
    "E07": "Condition-visible acceptance validation record",
    "E08": "Condition-visible regression verification record",
    "E09": "Recorded compliance evidence for common policies",
    "E10": "Start/end execution timestamps",
    "E11": "Agent and model identity",
    "E12": "Environment manifest identifier",
}
MANIFEST_ITEMS = ("E05", "E06", "E07", "E08", "E09")


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.is_file() else {}


def _result(status: str, detail: str, source: str = "execution-capture") -> dict[str, Any]:
    return {"status": status, "detail": detail, "source": source}


def e01(run_dir: Path, run: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    task = (run.get("task") or {}).get("id")
    expected = manifest.get("task")
    if not task:
        return _result(MISSING, "no task identity recorded")
    if expected and task != expected:
        return _result(MISSING, f"recorded task {task} is not the manifest task {expected}")
    return _result(VERIFIED, f"task {task}")


def e02(run_dir: Path, run: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    starting = (run.get("task") or {}).get("startingCommit")
    expected = manifest.get("baseRevision")
    if not starting:
        return _result(MISSING, "no starting revision recorded")
    if expected and starting != expected:
        return _result(MISSING, "recorded starting revision differs from the frozen base revision")
    return _result(VERIFIED, starting)


def e03(run_dir: Path, run: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    patch = run_dir / "final" / "workspace.patch"
    if not patch.is_file():
        return _result(MISSING, "final/workspace.patch not preserved")
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    recorded = ((run.get("final") or {}).get("patchSha256"))
    if recorded and recorded != digest:
        return _result(MISSING, "preserved patch does not match its recorded digest")
    return _result(VERIFIED, f"sha256 {digest}")


def e04(run_dir: Path, run: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    patch = run_dir / "final" / "workspace.patch"
    if not patch.is_file():
        return _result(MISSING, "no preserved patch to derive the inventory from")
    files = sorted(set(re.findall(r"^diff --git a/(\S+) b/", patch.read_text(encoding="utf-8", errors="replace"), re.M)))
    return _result(VERIFIED, f"{len(files)} changed file(s)")


def e10(run_dir: Path, run: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    steps = run.get("steps") or []
    if not steps or not steps[0].get("startedAt") or not steps[-1].get("endedAt"):
        return _result(MISSING, "no start/end timestamps")
    if steps[-1]["endedAt"] < steps[0]["startedAt"]:
        return _result(MISSING, "end precedes start")
    return _result(VERIFIED, f"{steps[0]['startedAt']} .. {steps[-1]['endedAt']}")


def e11(run_dir: Path, run: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    agent = run.get("agent") or {}
    if not agent.get("name") or not agent.get("version"):
        return _result(MISSING, "agent name or observed version missing")
    if not agent.get("modelIdentifier"):
        return _result(MISSING, "model identifier not recorded")
    return _result(VERIFIED, f"{agent['name']} {agent['version']} / {agent['modelIdentifier']}")


def e12(run_dir: Path, run: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    identifier = run.get("environmentIdentifier")
    expected = manifest.get("environmentIdentifier")
    if not identifier:
        return _result(MISSING, "no environment identifier")
    if expected and identifier != expected:
        return _result(MISSING, "environment identifier differs from the frozen environment manifest")
    return _result(VERIFIED, identifier)


BUILT_IN: dict[str, Callable[[Path, dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "E01": e01, "E02": e02, "E03": e03, "E04": e04, "E10": e10, "E11": e11, "E12": e12,
}


def score(run_dir: Path, manifest: dict[str, Any] | None = None,
          observations: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or {}
    observations = observations or {}
    run = _load(run_dir / "run.yaml")
    required = manifest.get("requiredItems") or list(ITEMS)
    items = {}
    for item in required:
        observed = observations.get(item)
        if observed is not None:
            status, source = observed.get("status"), observed.get("source", "execution")
            if source == "evaluator":
                # A post-hoc evaluator output never satisfies an execution-evidence obligation.
                items[item] = _result(MISSING, "evaluator-only result is not execution evidence", source)
            else:
                items[item] = _result(status if status in {VERIFIED, MISSING, UNAVAILABLE} else UNAVAILABLE,
                                      observed.get("detail", ""), source)
        elif item in BUILT_IN:
            items[item] = BUILT_IN[item](run_dir, run, manifest) if run else _result(UNAVAILABLE, "run.yaml unavailable", "study-infrastructure")
        else:
            items[item] = _result(UNAVAILABLE, "task manifest required", "none")
    unavailable = [item for item, value in items.items() if value["status"] == UNAVAILABLE]
    verified = sum(value["status"] == VERIFIED for value in items.values())
    primary = None if unavailable else verified / len(required)
    return {"run": str(run_dir), "requiredItems": len(required), "verified": verified,
            "primary": {"outcome": "OBSERVED" if primary is not None else "UNAVAILABLE",
                        "verifiedEvidenceCompleteness": primary, "unavailableItems": unavailable},
            "items": {item: {"name": ITEMS.get(item, item), **value} for item, value in items.items()}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--manifest", type=Path, help="task evidence manifest (YAML)")
    parser.add_argument("--observations", type=Path, help="task-specific verifier observations (JSON)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    manifest = _load(args.manifest) if args.manifest else {}
    observations = json.loads(args.observations.read_text()) if args.observations else {}
    report = score(args.run_dir, manifest, observations)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        value = report["primary"]["verifiedEvidenceCompleteness"]
        print(f"{report['run']}: {('-' if value is None else f'{value:.3f}')} ({report['primary']['outcome']})")
        for item, value in report["items"].items():
            print(f"  {item} {value['status']:11} {value['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
