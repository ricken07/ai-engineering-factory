import re

import pytest

from aief import approval


@pytest.fixture(autouse=True)
def no_approval_terminal(monkeypatch):
    """Tests never prompt on the developer's terminal nor inherit an agent harness:
    the simulated human at the terminal confirms the gate the Runtime asks for."""
    monkeypatch.setattr(approval, "terminal_confirm", lambda prompt: re.search(r"Type '([^']+)'", prompt)[1])
    for marker in approval.HARNESS_MARKERS:
        monkeypatch.delenv(marker, raising=False)


@pytest.fixture(autouse=True)
def git_identity(monkeypatch):
    """Commits made by tests, and by the Runtime when it integrates a task branch, do not depend on the
    machine's Git configuration: a CI runner has no user identity, and Git refuses to commit without one."""
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "AIEF Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "aief-test@example.invalid")
