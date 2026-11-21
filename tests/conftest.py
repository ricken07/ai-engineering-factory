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
