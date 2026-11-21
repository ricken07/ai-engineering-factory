"""L3/L2 payload comparison (tools/experiment/compare_payloads.py) on synthetic ledgers."""
import hashlib
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("compare_payloads", ROOT / "tools" / "experiment" / "compare_payloads.py")
tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

PLAN = "# Plan\n1. Add greeting().\n"
VERIFICATION = "acceptanceCriteria:\n- {id: AC-1, statement: greeting returns Hello}\n"
REQUEST = "Add a greeting function"
PRACTICE = "# Testing baseline\n\n- Every behavior change requires relevant automated evidence."
L1 = f"# Project context\n\nEngineering context of this project.\n\n## testing-baseline\n\nApplies to: main.\n\n{PRACTICE}\n"


def brief(phase: str, practices: dict[str, str] | None = None, task: list[str] | None = None, extra: str = "") -> str:
    lines = [f"# Phase brief: {phase} (skill)", "", "Read this file completely.", "", "## Skill contract", "", "- x", extra]
    if task is not None:
        lines += ["", "## Task context", ""] + [f"- {line}" for line in task]
    lines += ["", "## Practices", "", "Each practice applies to the repositories listed with it."]
    for identifier, content in (practices if practices is not None else {"testing-baseline": PRACTICE}).items():
        lines += ["", f"### {identifier} 1.0.0", "", "Applies to: `main`. Category: testing. Enforcement: mandatory.", "", content]
    return "\n".join(lines) + "\n"


def section(heading: str, identifier: str, classification: str) -> dict:
    return {"id": identifier, "heading": heading, "classification": classification, "sha256": "x" * 64, "bytes": 1}


def execution_dir(tmp_path: Path, phases: list[dict], plan: str = PLAN, decisions: list | None = None) -> Path:
    """`phases`: {phase, skill, brief, at?, sections?}. Writes the ledger, snapshots and bound files."""
    root = tmp_path / "execution"; (root / "payloads").mkdir(parents=True); (root / "bound-plan").mkdir()
    (root / "bound-plan" / "plan.md").write_text(plan); (root / "bound-plan" / "verification.yaml").write_text(VERIFICATION)
    entries = []
    for index, phase in enumerate(phases, 1):
        name = f"payloads/{index:03d}-phase-brief-{phase['phase']}.md"
        (root / name).write_text(phase["brief"])
        sections = phase.get("sections") or [section(f"# Phase brief: {phase['phase']} (skill)", "preamble", "procedural"),
                                             section("## Practices", "practices", "project-context")]
        items = [{"kind": "phase-brief", "base": "execution", "path": name, "sha256": "", "classification": "procedural",
                  "sections": sections}]
        for kind, file in (("bound-plan", "bound-plan/plan.md"), ("bound-verification", "bound-plan/verification.yaml")):
            items.append({"kind": kind, "base": "execution", "path": file, "sha256": "", "classification": "task-plan"})
        entries.append({"sequence": index, "phase": phase["phase"], "skill": phase["skill"],
                        "at": phase.get("at", f"2026-11-21T10:{index:02d}:00+00:00"), "items": items})
    (root / "payload-ledger.yaml").write_text(yaml.safe_dump({"experimentalCondition": "L3", "entries": entries, "fingerprint": "f"}))
    (root / "execution.yaml").write_text(yaml.safe_dump({"metadata": {"id": "exec-1"}, "gateDecisions": decisions or []}))
    return root


def treatment(tmp_path: Path) -> dict:
    frozen = tmp_path / "frozen"; frozen.mkdir(exist_ok=True)
    (frozen / "context.md").write_text(L1); (frozen / "plan.md").write_text(PLAN); (frozen / "verification.yaml").write_text(VERIFICATION)
    return {"l1_context": frozen / "context.md", "l2_plan": frozen / "plan.md", "l2_verification": frozen / "verification.yaml",
            "request": REQUEST}


def statuses(report: dict) -> dict:
    return {name: item["status"] for name, item in report["comparisons"].items()}


def test_identical_treatment_is_verified(tmp_path: Path):
    root = execution_dir(tmp_path, [{"phase": "implementation", "skill": "implement-change",
                                     "brief": brief("implementation", task=[f"objective: {{'summary': '{REQUEST}'}}", "scope: {}"])}])
    report = tool.compare(root, **treatment(tmp_path))
    assert report["outcome"] == "VERIFIED", report
    assert report["comparisons"]["l3_same_l1_content"]["practicesDelivered"] == ["testing-baseline"]


def test_a_different_plan_or_practice_fails(tmp_path: Path):
    root = execution_dir(tmp_path, [{"phase": "implementation", "skill": "implement-change",
                                     "brief": brief("implementation", {"testing-baseline": PRACTICE + " Extra."})}],
                         plan=PLAN + "3. Also refactor.\n")
    report = tool.compare(root, **treatment(tmp_path))
    assert statuses(report)["l3_same_l2_plan"] == "FAILED"
    assert statuses(report)["l3_same_l1_content"] == "FAILED"
    assert report["outcome"] == "FAILED"


def test_reviewer_practices_are_part_of_the_review_intervention(tmp_path: Path):
    root = execution_dir(tmp_path, [{"phase": "review", "skill": "review-change",
                                     "brief": brief("review", {"testing-baseline": PRACTICE, "code-review": "# Review"})}])
    report = tool.compare(root, **treatment(tmp_path))
    content = report["comparisons"]["l3_same_l1_content"]
    assert content["status"] == "VERIFIED" and content["reviewerPracticesOutsideL1"] == {"code-review": ["review"]}


def test_task_context_beyond_the_request_and_unclassified_sections_fail(tmp_path: Path):
    root = execution_dir(tmp_path, [{"phase": "implementation", "skill": "implement-change",
                                     "brief": brief("implementation", task=["objective: {'summary': 'Something else'}",
                                                                            "hint: the bug is in parser.py"]),
                                     "sections": [section("## Secret notes", "Secret notes", "unclassified")]}])
    findings = tool.compare(root, **treatment(tmp_path))["comparisons"]["no_additional_task_semantic_facts"]["findings"]
    assert any("does not restate the request" in item for item in findings)
    assert any("'hint'" in item for item in findings)
    assert any("unclassified" in item for item in findings)


def test_forbidden_content_reaching_the_agent_fails(tmp_path: Path):
    oracle = tmp_path / "oracle.py"; oracle.write_text("assert greeting() == 'Hello'  # hidden oracle line\nx\n")
    root = execution_dir(tmp_path, [{"phase": "implementation", "skill": "implement-change",
                                     "brief": brief("implementation", extra="assert greeting() == 'Hello'  # hidden oracle line")}])
    report = tool.compare(root, forbidden=[oracle], **treatment(tmp_path))
    assert statuses(report)["no_additional_task_semantic_facts"] == "FAILED"


def test_review_feedback_is_counted_against_the_rework_budget(tmp_path: Path):
    phases = [{"phase": "implementation", "skill": "implement-change", "brief": brief("implementation"),
               "sections": [section(f"## Rework {n}: review findings", "rework", "review-feedback")]} for n in range(1, 5)]
    report = tool.compare(execution_dir(tmp_path, phases), **treatment(tmp_path))
    budget = report["comparisons"]["reviewer_feedback_budget"]
    assert budget["status"] == "FAILED" and budget["reworks"] == 4 and len(budget["interventionEvents"]) == 4
    report = tool.compare(execution_dir(tmp_path / "ok", phases[:2]), rework_maximum=3, **treatment(tmp_path))
    assert report["comparisons"]["reviewer_feedback_budget"]["status"] == "VERIFIED"


def test_a_decision_rationale_delivered_after_the_decision_leaks(tmp_path: Path):
    decision = {"gate": "plan-gate", "decision": "rejected", "at": "2026-11-21T10:01:30+00:00",
                "rationale": "the plan misses the null input case"}
    phases = [{"phase": "understand", "skill": "understand-task", "brief": brief("understand")},
              {"phase": "implementation", "skill": "implement-change",
               "brief": brief("implementation", extra="Note: the plan misses the null input case")}]
    report = tool.compare(execution_dir(tmp_path, phases, decisions=[decision]), **treatment(tmp_path))
    assert statuses(report)["no_decision_rationale_leak"] == "FAILED"


def test_brief_parsers_match_the_rendered_formats():
    assert tool.practices_of_context(L1) == {"testing-baseline": PRACTICE}
    assert tool.practices_of_brief(brief("x")) == {"testing-baseline": PRACTICE}
    assert hashlib.sha256(PLAN.encode()).hexdigest()


def test_the_repositories_section_is_accepted_as_procedural(tmp_path: Path):
    text = brief("implementation", extra="\n## Repositories\n\n- `main`: profiles maven; context `c` (0123)")
    sections = [section("# Phase brief: implementation (skill)", "preamble", "procedural"),
                section("## Repositories", "repositories", "project-context"),
                section("## Practices", "practices", "project-context")]
    root = execution_dir(tmp_path, [{"phase": "implementation", "skill": "implement-change", "brief": text, "sections": sections}])
    facts = tool.compare(root, **treatment(tmp_path))["comparisons"]["no_additional_task_semantic_facts"]
    assert facts["status"] == "VERIFIED" and facts["l3OnlySectionsAcceptedAsProcedural"] == ["repositories"]
