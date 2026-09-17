from pathlib import Path
import subprocess

import pytest
import yaml

from aief.concurrency import LeaseConflict
from aief.evidence import build_evidence_bundle
from aief.knowledge import approve_candidate
from aief.project import StateStoreConflict, find_project, initialize
from aief.runtime import Execution
from aief.service import RuntimeService
from aief.workspace import WorkspaceManager


ROOT = Path(__file__).parents[1]


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=path, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def project_with_worktrees(tmp_path: Path) -> tuple[Path, Path, Path]:
    main = tmp_path / "main"
    initialize(ROOT / "templates/project", main)
    git(main, "init", "-b", "main")
    git(main, "config", "user.email", "factory@example.invalid")
    git(main, "config", "user.name", "Factory Test")
    git(main, "add", ".")
    git(main, "commit", "-m", "baseline")
    first, second = tmp_path / "worktree-a", tmp_path / "worktree-b"
    git(main, "worktree", "add", "-b", "worktree-a", str(first))
    git(main, "worktree", "add", "-b", "worktree-b", str(second))
    return main, first, second


def test_linked_worktrees_share_canonical_project_task_and_execution_store(tmp_path: Path):
    main, first, second = project_with_worktrees(tmp_path)
    assert find_project(first) == main.resolve()
    assert find_project(second) == main.resolve()

    first_service = RuntimeService(first, ROOT)
    second_service = RuntimeService(second, ROOT)
    first_execution = first_service.start("/analyze DEMO-1", "claude-code", agent_session="claude-session")
    second_execution = second_service.start("/analyze DEMO-1", "codex", agent_session="codex-session")

    assert first_execution.data["task"] == second_execution.data["task"] == "DEMO-1"
    assert first_execution.data["metadata"]["id"] != second_execution.data["metadata"]["id"]
    assert first_execution.root.parent == second_execution.root.parent == main.resolve() / ".ai/runtime/executions"
    assert (main / ".ai/runtime/tasks/DEMO-1/state.yaml").is_file()


def test_configured_runtime_root_is_the_single_state_store(tmp_path: Path):
    main = tmp_path / "configured"
    initialize(ROOT / "templates/project", main)
    project_file = main / ".ai/project.yaml"
    project = yaml.safe_load(project_file.read_text(encoding="utf-8"))
    project["runtime"]["root"] = ".project-state/runtime"
    project_file.write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
    service = RuntimeService(main, ROOT)
    execution = service.start("/analyze CONFIGURED-1", "codex")
    assert execution.root == (main / ".project-state/runtime/executions").resolve() / execution.data["metadata"]["id"]
    assert (main / ".project-state/runtime/tasks/CONFIGURED-1/events.jsonl").is_file()
    assert not (main / ".ai/runtime/executions").exists()


def test_noncanonical_worktree_state_fragment_fails_closed(tmp_path: Path):
    main, first, _ = project_with_worktrees(tmp_path)
    fragment = first / ".ai/runtime/executions/legacy-execution"
    fragment.mkdir(parents=True)
    (fragment / "execution.yaml").write_text("kind: Execution\n", encoding="utf-8")

    with pytest.raises(StateStoreConflict, match="non-canonical .ai/runtime state store"):
        find_project(first)
    assert find_project(main) == main.resolve()


def test_cross_worktree_handoff_and_execution_scoped_lease_isolation(tmp_path: Path):
    main, first, second = project_with_worktrees(tmp_path)
    claude = RuntimeService(first, ROOT)
    execution = claude.start("/analyze DEMO-2", "claude-code", agent_session="claude-session")
    other = claude.start("/analyze DEMO-2", "claude-code", agent_session="parallel-session")
    identifier = execution.data["metadata"]["id"]
    other_identifier = other.data["metadata"]["id"]

    claude.lease(identifier, "acquire", "claude-code:session-a")
    claude.lease(other_identifier, "acquire", "claude-code:parallel")
    with pytest.raises(LeaseConflict):
        claude.lease(identifier, "acquire", "codex:session-b")
    handoff = claude.handoff_execution(identifier, "claude-code:session-a")

    codex = RuntimeService(second, ROOT)
    assert codex.project_root == main.resolve()
    assert codex.execution(identifier).root == execution.root
    assert handoff.is_file()
    assert codex.lease(identifier, "acquire", "codex:session-b")["owner"] == "codex:session-b"


def test_execution_workspace_deletion_preserves_state_handoff_and_evidence(tmp_path: Path):
    main, _, _ = project_with_worktrees(tmp_path)
    execution = Execution.create(main, ROOT, {
        "metadata": {"id": "test-workflow", "version": "1.0.0"},
        "phases": [{"id": "work", "skill": "implement-change"}],
    }, "DEMO-3", "codex")
    manager = WorkspaceManager(main, {
        "workspaceSafety": {"mode": "worktree", "baseBranch": "main"},
        "runtime": {"root": ".ai/runtime"},
        "repositories": [{"id": "main", "path": ".", "role": "application"}],
    }, execution.root)
    state = manager.prepare(["main"], "DEMO-3", execute=True)
    workspace = Path(state["repositories"]["main"]["executionPath"])
    binding = state["repositories"]["main"]["workspaceBinding"]
    assert binding["workspaceId"] == f"{execution.data['metadata']['id']}:main"
    assert binding["physicalLocation"]["portability"] == "LOCAL_ONLY"

    execution.advance({"summary": "completed"})
    assert execution.data["status"] == "completed"
    handoff = execution.handoff(ROOT)
    bundle = build_evidence_bundle(execution.root)
    evidence = execution.root / "evidence-bundle.yaml"
    manager.rollback(execute=True)

    assert not workspace.exists()
    assert (execution.root / "execution.yaml").is_file()
    assert handoff.is_file() and evidence.is_file()
    assert yaml.safe_load(evidence.read_text())["fingerprint"] == bundle["fingerprint"]
    assert manager.verify()["drift"] == [{"repository": "main", "reason": "workspace-missing"}]


def test_stale_execution_worktree_branch_blocks_without_rebinding(tmp_path: Path):
    main, _, _ = project_with_worktrees(tmp_path)
    execution = Execution.create(main, ROOT, {
        "metadata": {"id": "test-workflow", "version": "1.0.0"},
        "phases": [{"id": "work", "skill": "implement-change"}],
    }, "DEMO-STALE")
    manager = WorkspaceManager(main, {
        "workspaceSafety": {"mode": "worktree", "baseBranch": "main"},
        "runtime": {"root": ".ai/runtime"},
        "repositories": [{"id": "main", "path": ".", "role": "application"}],
    }, execution.root)
    state = manager.prepare(["main"], "DEMO-STALE", execute=True)
    workspace = Path(state["repositories"]["main"]["executionPath"])
    git(workspace, "switch", "-c", "unexpected-branch")
    verification = manager.verify()
    assert verification["status"] == "blocked"
    assert verification["drift"] == [{"repository": "main", "reason": "branch-changed"}]


def test_project_knowledge_is_versioned_and_not_created_by_candidate_approval(tmp_path: Path):
    main, _, _ = project_with_worktrees(tmp_path)
    durable = main / ".ai/memory/shared.md"
    before = durable.read_text(encoding="utf-8")
    candidate = {"apiVersion": "aief.dev/v1alpha1", "kind": "MemoryCandidate",
                 "metadata": {"id": "MC-1"}, "sourceTask": "TASK-1",
                 "statement": "Use normalized errors.", "evidence": ["validation.yaml"],
                 "target": "project-memory", "status": "proposed"}
    promotion = approve_candidate(candidate, "reviewer")
    assert promotion["status"] == "pending"
    assert durable.read_text(encoding="utf-8") == before

    durable.write_text(before + "\nValidated project knowledge.\n", encoding="utf-8")
    git(main, "add", ".ai/memory/shared.md")
    git(main, "commit", "-m", "promote validated knowledge")
    fresh = tmp_path / "knowledge-worktree"
    git(main, "worktree", "add", "-b", "knowledge-worktree", str(fresh), "HEAD")
    assert "Validated project knowledge." in (fresh / ".ai/memory/shared.md").read_text(encoding="utf-8")


def test_polyrepository_worktree_bindings_are_distinct_and_execution_owned(tmp_path: Path):
    project = tmp_path / "polyrepo"
    project.mkdir()
    repositories = []
    for identifier in ("api", "app"):
        repository = project / identifier
        repository.mkdir()
        git(repository, "init", "-b", "main")
        git(repository, "config", "user.email", "factory@example.invalid")
        git(repository, "config", "user.name", "Factory Test")
        (repository / "README.md").write_text(identifier, encoding="utf-8")
        git(repository, "add", "README.md")
        git(repository, "commit", "-m", "baseline")
        repositories.append({"id": identifier, "path": identifier, "role": "application"})
    execution_root = project / ".ai/runtime/executions/exec-poly"
    execution_root.mkdir(parents=True)
    manager = WorkspaceManager(project, {"workspaceSafety": {"mode": "worktree"},
                                          "runtime": {"root": ".ai/runtime"},
                                          "repositories": repositories}, execution_root)
    state = manager.prepare(["api", "app"], "TASK-POLY", execute=True)
    bindings = [item["workspaceBinding"] for item in state["repositories"].values()]
    assert {item["workspaceId"] for item in bindings} == {"exec-poly:api", "exec-poly:app"}
    assert len({item["physicalLocation"]["value"] for item in bindings}) == 2
    assert manager.verify()["status"] == "ready"
