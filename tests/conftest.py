import pytest

from aief import approval


@pytest.fixture(autouse=True)
def no_approval_terminal(monkeypatch):
    """Tests never prompt on the developer's terminal nor inherit an agent harness."""
    monkeypatch.setattr(approval, "terminal_confirm", lambda prompt: None)
    for marker in approval.HARNESS_MARKERS:
        monkeypatch.delenv(marker, raising=False)
