import json
from pathlib import Path

from aief import approval_hook
from aief.approval_hook import handle, install, installed, parse
from test_dynamic_policy import PATCH, critical_implementation, output


def test_only_approval_messages_are_handled():
    assert parse("/approve") == [] and parse("$approve exec-1 before-commit") == ["exec-1", "before-commit"]
    assert parse("please /approve this") is None and parse("/approved") is None
    assert handle({"prompt": "Looks good"}, "codex", lambda cwd: None) == (0, "", "")


def proposed(tmp_path: Path):
    service, identifier, root = critical_implementation(tmp_path)
    execution = service.execution(identifier); (execution.root / "change.patch").write_text(PATCH)
    service.complete_phase(identifier, output("Proposed", {"repositories": ["main"], "proposal": {"patches": [{"repository": "main", "path": "change.patch"}]}}))
    service.prepare_phase(identifier)
    return service, identifier, root


def test_harness_delivered_approval_is_observed_while_the_agent_holds_the_lease(tmp_path: Path):
    service, identifier, root = proposed(tmp_path)
    service.lease(identifier, "acquire", "claude-code:session-1")
    code, out, err = handle({"prompt": "/approve", "session_id": "s-1", "prompt_id": "p-1", "cwd": str(root)},
                            "claude-code", lambda cwd: service)
    assert (code, err) == (0, "") and "apply-proposal" in out and "Do not run any approval command" in out
    execution = service.execution(identifier)
    gate = next(item for item in execution.data["policyGates"] if item["id"] == "apply-proposal")
    assert (gate["actor"]["source"], gate["actor"]["assurance"], gate["actor"]["harness"], gate["actor"]["session"]) == (
        "harness-hook", "OBSERVED", "claude-code", "s-1")
    assert (root / "app.txt").read_text() == "two\n"


def test_refused_approval_blocks_the_message_with_the_terminal_fallback(tmp_path: Path):
    service, identifier, root = proposed(tmp_path)
    code, out, err = handle({"prompt": "/approve before-merge"}, "codex", lambda cwd: service)
    assert code == 2 and out == "" and "no execution is waiting for this approval" in err
    assert "aief execution approve-policy" in err
    assert service.execution(identifier).data["proposal"]["status"] == "proposed"


def test_install_is_idempotent_and_denies_the_entry_point_to_the_agent(tmp_path: Path):
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude/settings.json").write_text('{"permissions": {"allow": ["Bash(aief *)"]}}')
    for _ in range(2):
        install(tmp_path, "claude-code"); install(tmp_path, "codex")
    claude = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert len(claude["hooks"]["UserPromptSubmit"]) == 1
    assert claude["permissions"] == {"allow": ["Bash(aief *)"], "deny": [approval_hook.CLAUDE_DENY]}
    codex = json.loads((tmp_path / ".codex/hooks.json").read_text())
    assert codex["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] == "aief approval hook --agent codex"
    assert installed(tmp_path, "claude-code") and installed(tmp_path, "codex")
    assert 'pattern = ["aief", "approval"]' in (tmp_path / approval_hook.CODEX_RULES).read_text()
