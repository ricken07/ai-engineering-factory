from pathlib import Path

import pytest
import yaml

from aief.project import initialize
from aief.provider_runtime import ProviderResolutionError
from aief.service import RuntimeService
from aief.validation import validate_project

ROOT = Path(__file__).parents[1]
ENV = {"JIRA_MCP_URL": "https://mcp.example.test", "JIRA_TOKEN": "secret"}


def service(tmp_path: Path, autonomy="L2", provider="jira") -> RuntimeService:
    project = tmp_path / "project"
    initialize(ROOT / "templates/project", project)
    data = yaml.safe_load((project / ".ai/project.yaml").read_text())
    data["integrations"] = {"task-provider": {"provider": provider}}
    data["autonomy"]["default"] = autonomy
    (project / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    (project / "specs").mkdir()
    (project / "specs/payment-callbacks.md").write_text("# Reconcile payment callback statuses\n")
    return RuntimeService(project, ROOT, ENV)


def proposal(import_id: str, candidate_id: str, title: str, parent: str | None = None) -> dict:
    value = {
        "apiVersion": "factory.gaddigital.io/v1alpha1", "kind": "ExternalTaskProposal",
        "metadata": {"id": candidate_id}, "sourceImport": import_id, "type": "task",
        "title": title, "description": "Detail.", "acceptanceCriteria": ["It works"],
        "repositories": [], "risk": "medium",
    }
    if parent: value["parent"] = parent
    return value


def test_config_defaults_are_applied_when_omitted(tmp_path):
    runtime = service(tmp_path)
    result = runtime.backlog.start("specs", "jira")
    assert result["plan"]["config"]["duplicatePolicy"] == "always-review"
    assert result["plan"]["config"]["allowedSourceExtensions"] == [".md", ".yaml", ".yml", ".feature"]
    assert result["sourceFiles"] == ["payment-callbacks.md"]
    assert result["plan"]["status"] == "discovering"


def test_reimport_with_same_source_and_provider_is_idempotent(tmp_path):
    runtime = service(tmp_path)
    first = runtime.backlog.start("specs", "jira")
    second = runtime.backlog.start("specs", "jira")
    assert first["importId"] == second["importId"]
    assert second["plan"]["status"] == "discovering"


def test_draft_rejects_unknown_parent_reference(tmp_path):
    runtime = service(tmp_path)
    import_id = runtime.backlog.start("specs", "jira")["importId"]
    candidate = proposal(import_id, "cand-task", "Map FAILED status", parent="cand-epic-missing")
    with pytest.raises(ValueError, match="unknown parent/dependency"):
        runtime.backlog.complete_draft(import_id, [candidate])


def test_draft_builds_hierarchy_and_search_queries(tmp_path):
    runtime = service(tmp_path)
    import_id = runtime.backlog.start("specs", "jira")["importId"]
    epic = proposal(import_id, "cand-epic", "Reconcile payment callback statuses")
    task = proposal(import_id, "cand-task", "Map FAILED status", parent="cand-epic")
    result = runtime.backlog.complete_draft(import_id, [epic, task])
    assert result["plan"]["status"] == "drafted"
    assert set(result["queries"]) == {"cand-epic", "cand-task"}
    assert result["queries"]["cand-epic"]["summary"] == "Reconcile payment callback statuses"


def test_auto_link_high_confidence_duplicate_policy(tmp_path):
    runtime = service(tmp_path)
    config_path = runtime.project_root / "backlog-import-config.yaml"
    config_path.write_text(yaml.safe_dump({
        "apiVersion": "factory.gaddigital.io/v1alpha1", "kind": "BacklogImportConfig",
        "metadata": {"id": "auto-link"}, "duplicatePolicy": "auto-link-high-confidence",
    }))
    import_id = runtime.backlog.start("specs", "jira", str(config_path))["importId"]
    runtime.backlog.complete_draft(import_id, [proposal(import_id, "cand-epic", "Reconcile payment callback statuses")])
    matches = {"cand-epic": [{"reference": "EMM-441", "title": "Incorrect MTN callback status mapping", "confidence": "high", "rationale": ["same component"], "recommendation": "link-existing"}]}
    plan = runtime.backlog.complete_duplicate_search(import_id, matches)
    assert plan["candidates"][0]["decision"] == "link-existing"
    assert plan["status"] == "duplicate-assessed"


def test_default_policy_leaves_decision_create_for_human_review(tmp_path):
    runtime = service(tmp_path)
    import_id = runtime.backlog.start("specs", "jira")["importId"]
    runtime.backlog.complete_draft(import_id, [proposal(import_id, "cand-epic", "Reconcile payment callback statuses")])
    matches = {"cand-epic": [{"reference": "EMM-441", "title": "Incorrect MTN callback status mapping", "confidence": "high", "rationale": [], "recommendation": "link-existing"}]}
    plan = runtime.backlog.complete_duplicate_search(import_id, matches)
    assert plan["candidates"][0]["decision"] == "create"


def test_apply_defers_child_until_parent_reference_is_known(tmp_path):
    runtime = service(tmp_path, "L3")
    import_id = runtime.backlog.start("specs", "jira")["importId"]
    epic = proposal(import_id, "cand-epic", "Reconcile payment callback statuses")
    task = proposal(import_id, "cand-task", "Map FAILED status", parent="cand-epic")
    runtime.backlog.complete_draft(import_id, [epic, task])
    runtime.backlog.complete_duplicate_search(import_id, {})

    first = runtime.backlog.apply(import_id, approved=True)
    assert [op["input"]["proposal"]["metadata"]["id"] for op in first["operations"]] == ["cand-epic"]
    assert first["blockedOnParent"] == ["cand-task"]
    epic_operation = first["operations"][0]

    executed = runtime.execute_backlog_operation(import_id, epic_operation["metadata"]["id"], lambda operation: {"reference": "EMM-700"})
    assert executed["status"] == "completed"

    second = runtime.backlog.apply(import_id, approved=True)
    assert second["blockedOnParent"] == []
    task_operation = second["operations"][0]
    assert task_operation["input"]["parentReference"] == "EMM-700"
    runtime.execute_backlog_operation(import_id, task_operation["metadata"]["id"], lambda operation: {"reference": "EMM-701"})

    plan = runtime.backlog._read(import_id, "plan.yaml")
    assert plan["status"] == "applied"
    assert validate_project(runtime.project_root, ROOT) == []


def test_apply_gates_approval_below_l3(tmp_path):
    runtime = service(tmp_path, "L2")
    import_id = runtime.backlog.start("specs", "jira")["importId"]
    runtime.backlog.complete_draft(import_id, [proposal(import_id, "cand-epic", "Reconcile payment callback statuses")])
    runtime.backlog.complete_duplicate_search(import_id, {})
    result = runtime.backlog.apply(import_id)
    assert result["operations"][0]["status"] == "waiting-approval"
    with pytest.raises(RuntimeError, match="operation cannot execute"):
        runtime.execute_backlog_operation(import_id, result["operations"][0]["metadata"]["id"], lambda operation: {"reference": "EMM-1"})


def test_apply_before_duplicate_assessment_is_rejected(tmp_path):
    runtime = service(tmp_path)
    import_id = runtime.backlog.start("specs", "jira")["importId"]
    runtime.backlog.complete_draft(import_id, [proposal(import_id, "cand-epic", "Reconcile payment callback statuses")])
    with pytest.raises(RuntimeError, match="duplicate assessment must complete"):
        runtime.backlog.apply(import_id)


def test_dependency_cycle_is_rejected(tmp_path):
    runtime = service(tmp_path, "L3")
    import_id = runtime.backlog.start("specs", "jira")["importId"]
    first = proposal(import_id, "cand-a", "A"); first["dependsOn"] = ["cand-b"]
    second = proposal(import_id, "cand-b", "B"); second["dependsOn"] = ["cand-a"]
    runtime.backlog.complete_draft(import_id, [first, second])
    runtime.backlog.complete_duplicate_search(import_id, {})
    with pytest.raises(ValueError, match="dependency cycle"):
        runtime.backlog.apply(import_id, approved=True)


def test_provider_mismatch_is_explicit(tmp_path):
    runtime = service(tmp_path, "L3", provider="jira")
    import_id = runtime.backlog.start("specs", "gitlab")["importId"]
    runtime.backlog.complete_draft(import_id, [proposal(import_id, "cand-epic", "Reconcile payment callback statuses")])
    runtime.backlog.complete_duplicate_search(import_id, {})
    with pytest.raises(ProviderResolutionError) as error:
        runtime.backlog.apply(import_id, approved=True)
    assert error.value.code == "PROVIDER_MISMATCH"
