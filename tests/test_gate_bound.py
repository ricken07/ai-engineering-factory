"""Upper bound on the human gate requests of one study run (G_max, SAP C9/H4).

The worst-case elapsed time of an L3 run is its active budget plus one response
limit per sequential human wait. This test derives the bound from the Factory
itself, so that a change to the study workflows, to the gates that hold a run or
to the rework budget breaks it instead of silently invalidating the SAP.

Derivation for the study workflows (implement-task, fix-bug):
- phase gates of the workflow, once each (a plan revision is refused when the plan is bound);
- policy gates that hold a run are only those `_pending_policy_gates` returns, plus
  `before-merge` after completion; each gate id is created once per execution,
  however often the policy is reassessed, and stays approved across reworks;
- except `apply-proposal`, recreated for every implementation attempt: at most
  1 + MAX_REWORKS times;
- `before-commit` and `before-submission` hold the run together at submission:
  two requests, one wait.
"""
from pathlib import Path

import yaml

from aief import service as runtime_service
from aief.proposal import APPLY_GATE

ROOT = Path(__file__).parents[1]
STUDY_WORKFLOWS = ("implement-task", "fix-bug")
HOLDING_POLICY_GATES = {"before-implementation", "before-commit", "before-submission", APPLY_GATE}


def phase_gates(workflow: str) -> list[str]:
    data = yaml.safe_load((ROOT / "core" / "workflows" / workflow / "workflow.yaml").read_text())
    return [phase["gate"]["id"] for phase in data["phases"] if phase.get("gate")]


def bound(workflow: str) -> tuple[int, int]:
    """(G_max requests, sequential waits) for one run of the workflow."""
    attempts = 1 + runtime_service.MAX_REWORKS
    phases = len(phase_gates(workflow))
    requests = phases + 1 + attempts + 2 + 1      # phase gates, before-implementation, apply-proposal, commit+submission, merge
    waits = phases + 1 + attempts + 1 + 1         # commit and submission share one wait
    return requests, waits


def test_only_known_policy_gates_can_hold_a_run():
    held = set()
    for phase in ("understanding", "planning", "implementation", "validation", "review", "summary", "traceability", "submission"):
        class Probe:
            data = {"policyGates": [{"id": gate, "status": "pending"} for gate in
                                    ("before-implementation", "before-commit", "before-submission", APPLY_GATE,
                                     "before-merge", "before-destructive-action", "before-external-task-write",
                                     "before-project-knowledge-write")]}
        held |= runtime_service.RuntimeService._pending_policy_gates(Probe, phase)
    # before-merge holds the integration, not a phase; the others are recorded but never hold a run.
    assert held == HOLDING_POLICY_GATES


def test_g_max_of_the_study_workflows():
    assert runtime_service.MAX_REWORKS == 3
    assert phase_gates("implement-task") == ["plan-gate", "submission-gate"]
    assert phase_gates("fix-bug") == []
    assert bound("implement-task") == (10, 9)
    assert bound("fix-bug") == (8, 7)
    worst = max(waits for _, waits in map(bound, STUDY_WORKFLOWS))
    # Worst-case elapsed time: 120 active minutes plus one 30-minute response limit per wait.
    assert 120 + worst * 30 == 390
