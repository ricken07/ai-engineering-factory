import pytest

from aief.approval import human_approval_actor
from aief.identity import trusted_session_actor

EXECUTION = {"metadata": {"id": "exec-1"},
             "actors": {"producer": trusted_session_actor("codex:impl"),
                        "reviewer": trusted_session_actor("claude:review", handoffFrom="codex:impl")},
             "handoffs": [{"from": "codex:impl"}]}


def approve(**kwargs):
    options = {"approver": None, "relayed_by": None, "lease": None, "confirm": lambda prompt: None, "env": {}}
    options.update(kwargs)
    return human_approval_actor(EXECUTION, "before-commit", **options)


def test_terminal_confirmation_is_observed():
    actor = approve(approver="alice", confirm=lambda prompt: "before-commit")
    assert (actor["id"], actor["type"], actor["source"], actor["assurance"], actor["channel"]) == (
        "alice", "human", "terminal-confirmation", "OBSERVED", "interactive-terminal")


def test_wrong_terminal_confirmation_refuses():
    with pytest.raises(PermissionError, match="not confirmed"):
        approve(confirm=lambda prompt: "yes")


def test_agent_relay_is_declared_and_never_asks():
    asked = []
    actor = approve(relayed_by="codex:impl-2", lease={"owner": "codex:impl-2"},
                    confirm=lambda prompt: asked.append(prompt) or "before-commit")
    assert actor["assurance"] == "DECLARED" and actor["channel"] == "agent-relay"
    assert actor["relayedBy"] == "codex:impl-2" and actor["id"] == "human" and not asked
    harness = approve(env={"CLAUDECODE": "1"}, confirm=lambda prompt: "before-commit")
    assert harness["assurance"] == "DECLARED" and harness["harness"] == "claude-code"


def test_non_interactive_call_is_declared():
    actor = approve(approver="alice")
    assert (actor["id"], actor["assurance"], actor["channel"]) == ("alice", "DECLARED", "non-interactive")


@pytest.mark.parametrize("approver", ["codex:impl", "claude:review", "codex:lease"])
def test_agent_identity_cannot_approve(approver):
    with pytest.raises(PermissionError, match="cannot approve"):
        approve(approver=approver, lease={"owner": "codex:lease"})
