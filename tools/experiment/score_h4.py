#!/usr/bin/env python3
"""H4 — cost of control (RC2 §9.4), per run.

Primary duration: wall-clock time from the first agent step start to the
terminal run transition, including validation, review, rework and human
waiting. For L3, the terminal transition is the later of the last agent step
end and the execution's terminal timestamp; when integration is required, the
recorded `before-merge` decision or expiry is part of the terminal boundary.

Human waits are the gate-wait intervals recorded by the Runtime
(`waitStartedAt` .. `decidedAt`, each with OBSERVED, DERIVED or UNAVAILABLE
provenance); overlapping intervals are merged, and active wall-clock is the
total elapsed interval minus the union of the gate-wait intervals. In L0–L2 a
human gate is `NOT_APPLICABLE`, not a measured zero. Unknown values are never
imputed as zero (`unknown ≠ 0`).

Secondary measures: agent process time (sum of launcher steps), Runtime and
validation durations (with their availability), rework count, human
interventions (gate decisions and refused attempts), and whether the run
reached its resource limit. Invalid-attempt overhead is aggregated across the
attempts of a unit by the analysis, not per run.

Usage: score_h4.py RUN_DIR [--json]   (L3: RUN_DIR/aief/execution.yaml as collected by the launcher)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

NOT_APPLICABLE, UNAVAILABLE = "NOT_APPLICABLE", "UNAVAILABLE"


def _load(path: Path) -> dict[str, Any]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.is_file() else {}


def _time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _clip(intervals: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> float:
    return sum(max(0.0, (min(b, end) - max(a, start)).total_seconds()) for a, b in intervals)


def _metric(execution: dict[str, Any], name: str) -> dict[str, Any]:
    value = ((execution.get("metrics") or {}).get(name) or {}).get("durationMs") or {}
    return {"ms": value.get("value"), "availability": value.get("availability", UNAVAILABLE)} if value else \
        {"ms": None, "availability": UNAVAILABLE}


def score(run_dir: Path) -> dict[str, Any]:
    run = _load(run_dir / "run.yaml")
    steps = run.get("steps") or []
    l3 = run.get("experimentalCondition") == "L3"
    execution = _load(run_dir / "aief" / "execution.yaml") if l3 else {}
    start = _time(steps[0].get("startedAt")) if steps else None
    ends = [_time(steps[-1].get("endedAt"))] if steps else []
    waits: list[dict[str, Any]] = []
    if l3:
        ends.append(_time(((execution.get("metrics") or {}).get("execution") or {}).get("completedAt")))
        for decision in execution.get("gateDecisions") or []:
            began, decided = _time(decision.get("waitStartedAt")), _time(decision.get("decidedAt"))
            availability = (decision.get("waitDurationMs") or {}).get("availability", UNAVAILABLE)
            waits.append({"gate": decision.get("gate"), "decision": decision.get("decision"),
                          "start": began, "end": decided,
                          "provenance": availability if began and decided else UNAVAILABLE})
            if decision.get("gate") == "before-merge":
                ends.append(decided)
    known_ends = [item for item in ends if item]
    end = max(known_ends) if known_ends else None
    wall = (end - start).total_seconds() if start and end else None
    agent = round(sum(step.get("durationSeconds") or 0 for step in steps), 3) if steps else None
    if not l3:
        gate_wait: dict[str, Any] = {"seconds": NOT_APPLICABLE, "provenance": NOT_APPLICABLE, "intervals": 0}
        active = wall
    elif any(item["provenance"] == UNAVAILABLE for item in waits) or wall is None:
        gate_wait = {"seconds": None, "provenance": UNAVAILABLE, "intervals": len(waits)}
        active = None
    else:
        union = merge([(item["start"], item["end"]) for item in waits])
        seconds = _clip(union, start, end)
        provenances = {item["provenance"] for item in waits}
        gate_wait = {"seconds": round(seconds, 3), "intervals": len(waits),
                     "provenance": "DERIVED" if "DERIVED" in provenances else ("OBSERVED" if waits else "OBSERVED")}
        active = round(wall - seconds, 3)
    return {
        "run": str(run_dir), "condition": run.get("experimentalCondition"),
        "primary": {"wallClockSeconds": round(wall, 3) if wall is not None else None,
                    "outcome": "OBSERVED" if wall is not None else UNAVAILABLE},
        "activeWallClockSeconds": active,
        "gateWait": gate_wait,
        "agentProcessSeconds": agent,
        "runtime": _metric(execution, "runtime") if l3 else NOT_APPLICABLE,
        "validation": _metric(execution, "validation") if l3 else NOT_APPLICABLE,
        "reworks": len(execution.get("reworks") or []) if l3 else NOT_APPLICABLE,
        "humanInterventions": (len(execution.get("gateDecisions") or []) + len(execution.get("approvalRefusals") or []))
        if l3 else NOT_APPLICABLE,
        "resourceLimitReached": bool(run.get("resourceLimitReached")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = score(args.run_dir)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"{report['run']} ({report['condition']}): wall-clock {report['primary']['wallClockSeconds']} s, "
              f"active {report['activeWallClockSeconds']} s, gate wait {report['gateWait']['seconds']} "
              f"({report['gateWait']['provenance']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
