import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

from aief import payload_ledger
from aief.phase_brief import render_phase_brief
from aief.project import initialize
from aief.service import RuntimeService
from aief.validation import assert_schema


ROOT = Path(__file__).parents[1]


def project(tmp_path: Path) -> RuntimeService:
    root = tmp_path / "project"; initialize(ROOT / "templates/project", root)
    data = yaml.safe_load((root / ".ai/project.yaml").read_text()); data["autonomy"] = {"default": "L3", "maximum": "L3"}
    data["repositories"] = [{"id": "main", "path": ".", "role": "application", "profiles": ["generic"],
                             "responsibilities": [], "dependencies": [], "criticalDomains": []}]
    (root / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return RuntimeService(root, ROOT)


def started(service: RuntimeService, **kwargs) -> str:
    execution = service.start("Implémente une évolution locale", confirmed=True,
                              experiment={"condition": "L3"}, **kwargs)
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"] = "completed"
    execution.data["status"] = "running"; execution.save()
    return execution.data["metadata"]["id"]


def output(summary: str, details: dict) -> dict:
    return {"summary": summary, "status": "completed", "evidence": ["verified"], "unknowns": [], "details": details}


def test_each_phase_preparation_appends_a_validated_entry(tmp_path: Path):
    service = project(tmp_path); identifier = started(service)
    prepared = service.prepare_phase(identifier)
    root = service.execution(identifier).root
    ledger = payload_ledger.load(root)
    assert_schema(ROOT, "payload-ledger.schema.json", ledger)
    assert ledger["experimentalCondition"] == "L3" and len(ledger["entries"]) == 1
    entry = ledger["entries"][0]
    assert entry["phase"] == "analyze-impact" and entry["attempt"] == 0
    kinds = {item["kind"]: item for item in entry["items"]}
    assert {"phase-brief", "execution-next-output", "skill-instructions", "skill-manifest", "output-schema"} <= set(kinds)
    brief = kinds["phase-brief"]
    assert brief["sha256"] == prepared["phaseBrief"]["sha256"]
    assert (root / brief["path"]).read_text() == Path(prepared["phaseBrief"]["path"]).read_text()
    assert kinds["skill-instructions"]["base"] == "factory"
    assert kinds["skill-instructions"]["path"] == "core/skills/analyze-impact/SKILL.md"
    assert payload_ledger.LEDGER in service.execution(identifier).data["artifacts"]
    assert service.delivered_payloads(identifier)["gaps"] == []


def test_execution_next_output_is_snapshotted_as_printed(tmp_path: Path):
    from aief.phase_brief import compact_prepared
    service = project(tmp_path); identifier = started(service)
    prepared = service.prepare_phase(identifier)
    root = service.execution(identifier).root
    item = next(item for item in payload_ledger.load(root)["entries"][0]["items"] if item["kind"] == "execution-next-output")
    assert json.loads((root / item["path"]).read_text()) == json.loads(json.dumps(compact_prepared(prepared), default=str))


def test_brief_sections_are_classified(tmp_path: Path):
    phase = {"id": "implementation", "skill": "implement-change", "action": "propose-change",
             "rework": {"number": 1, "review": "review.yaml", "decision": "changes-requested",
                        "findings": [{"severity": "high", "finding": "missing test"}]}}
    contract = {"instructions": "SKILL.md", "manifest": "skill.yaml", "outputSchema": "output.schema.json"}
    contexts = [{"repository": "main", "metadata": {"id": "ctx"}, "fingerprint": "f", "profiles": [],
                 "taskContext": {"summary": "s"}, "practices": [{"id": "p", "content": "c"}]}]
    decisions = [{"review": "review.yaml", "finding": 1, "summary": "s", "actor": {"id": "h", "assurance": "OBSERVED"},
                  "justification": "j"}]
    binding = {"plan": {"artifact": "bound-plan/plan.md", "sha256": "0" * 64}}
    sections = payload_ledger.brief_sections(render_phase_brief(phase, contract, contexts, decisions, binding))
    classes = {section["id"]: section["classification"] for section in sections}
    assert classes == {"preamble": "procedural", "skill-contract": "procedural", "bound-plan": "task-plan",
                       "rework": "review-feedback", "human-decisions": "human-decision",
                       "authorized-action": "procedural", "repositories": "project-context",
                       "task-context": "task-context", "practices": "project-context"}


def test_unknown_section_is_reported_as_a_gap(tmp_path: Path):
    service = project(tmp_path); identifier = started(service)
    prepared = service.prepare_phase(identifier)
    root = service.execution(identifier).root
    ledger = payload_ledger.load(root)
    brief = next(item for item in ledger["entries"][0]["items"] if item["kind"] == "phase-brief")
    brief["sections"].append({"id": "x", "heading": "## Hint", "classification": "unclassified", "sha256": "0" * 64, "bytes": 0})
    ledger["fingerprint"] = "sha256:" + hashlib.sha256(json.dumps(ledger["entries"], sort_keys=True).encode()).hexdigest()
    (root / payload_ledger.LEDGER).write_text(yaml.safe_dump(ledger, sort_keys=False))
    assert any("unclassified" in gap for gap in service.delivered_payloads(identifier)["gaps"])


def test_changed_snapshot_or_ledger_is_reported(tmp_path: Path):
    service = project(tmp_path); identifier = started(service)
    service.prepare_phase(identifier)
    root = service.execution(identifier).root
    brief = next(item for item in payload_ledger.load(root)["entries"][0]["items"] if item["kind"] == "phase-brief")
    (root / brief["path"]).write_text("edited\n")
    assert any("changed after it was delivered" in gap for gap in service.delivered_payloads(identifier)["gaps"])
    text = (root / payload_ledger.LEDGER).read_text().replace("attempt: 0", "attempt: 2")
    (root / payload_ledger.LEDGER).write_text(text)
    assert "ledger fingerprint does not match its entries" in service.delivered_payloads(identifier)["gaps"]


def test_a_rerun_phase_keeps_both_payloads(tmp_path: Path):
    service = project(tmp_path); identifier = started(service)
    service.prepare_phase(identifier)
    first = service.execution(identifier)
    first.next_phase()["rework"] = {"number": 1, "review": "review.yaml", "decision": "changes-requested",
                                    "findings": ["add the missing test"]}
    first.save()
    service.prepare_phase(identifier)
    root = service.execution(identifier).root
    entries = payload_ledger.load(root)["entries"]
    assert [entry["attempt"] for entry in entries] == [0, 1]
    briefs = [next(item for item in entry["items"] if item["kind"] == "phase-brief") for entry in entries]
    assert briefs[0]["path"] != briefs[1]["path"] and briefs[0]["sha256"] != briefs[1]["sha256"]
    assert "add the missing test" not in (root / briefs[0]["path"]).read_text()
    assert any(section["classification"] == "review-feedback" for section in briefs[1]["sections"])
    assert service.delivered_payloads(identifier)["gaps"] == []


def test_bound_files_are_listed_as_task_plan(tmp_path: Path):
    source = tmp_path / "frozen"; source.mkdir()
    (source / "plan.md").write_text("# Plan\n")
    (source / "verification.yaml").write_text("acceptanceCriteria:\n- {id: AC-1, statement: works}\n")
    service = project(tmp_path)
    identifier = started(service, bound_plan=source / "plan.md", bound_verification=source / "verification.yaml")
    service.prepare_phase(identifier)
    items = payload_ledger.load(service.execution(identifier).root)["entries"][0]["items"]
    bound = {item["kind"]: item for item in items if item["kind"].startswith("bound-")}
    assert set(bound) == {"bound-plan", "bound-verification"}
    assert all(item["classification"] == "task-plan" and item["base"] == "execution" for item in bound.values())


def test_cli_reports_ledger_and_fails_on_gaps(tmp_path: Path):
    service = project(tmp_path); identifier = started(service)
    service.prepare_phase(identifier)
    command = [sys.executable, "-m", "aief.cli", "execution", "payload-ledger", identifier,
               "--project", str(service.project_root), "--factory", str(ROOT), "--json"]
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ledger"]["entries"][0]["phase"] == "analyze-impact"
    root = service.execution(identifier).root
    (root / payload_ledger.LEDGER).write_text((root / payload_ledger.LEDGER).read_text().replace("attempt: 0", "attempt: 3"))
    assert subprocess.run(command, capture_output=True, text=True, cwd=ROOT).returncode == 1


def test_every_heading_the_brief_emits_is_classified():
    import re
    source = "".join((ROOT / name).read_text() for name in ("aief/phase_brief.py", "aief/plan_binding.py"))
    # Placeholders of f-strings are filled with a sample value before matching.
    headings = [re.sub(r"\{[^}]*\}", "1", item) for item in re.findall(r'f?"(#{1,2} [^"]*)"', source)]
    assert len(headings) >= 9 and all(payload_ledger._section(heading) for heading in headings), headings


def test_headings_inside_practice_content_stay_in_their_section():
    text = "# Phase brief: x (y)\n\nRead.\n\n## Practices\n\n### p\n\n# Architecture Context\n\n## Secret management\n"
    sections = payload_ledger.brief_sections(text)
    assert [section["id"] for section in sections] == ["preamble", "practices"]
