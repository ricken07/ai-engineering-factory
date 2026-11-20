"""Identity of the human who approves a gate.

A gate approval carries human accountability, so the Runtime records how the
approver's identity was established instead of assuming one:

- typed at an interactive terminal: the Runtime asked, on the controlling
  terminal of the command, to retype the gate id, and read it there. Agent
  sessions run without a controlling terminal, so the approval is `OBSERVED`
  as coming from a person at that terminal. This is not authentication: it
  does not prove who sat at the terminal, and a determined process can
  allocate a pseudo-terminal.
- relayed by an agent session (the caller holds the execution lease, or runs
  inside an agent harness): the agent reports a human decision the Runtime did
  not see, so the approver is `DECLARED`.
- any other non-interactive call: the caller's claim is `DECLARED`.

Whatever the channel, an agent identity of the execution (producer, reviewer,
lease owner, handoff) can never be recorded as the approver.
"""
from __future__ import annotations

import getpass
import os
from typing import Any, Callable, Mapping

from .identity import actor_identity

Confirm = Callable[[str], "str | None"]

# Environment markers that agent harnesses set for the commands they run.
HARNESS_MARKERS = {
    "CLAUDECODE": "claude-code",
    "CODEX_SANDBOX": "codex",
    "CODEX_SANDBOX_NETWORK_DISABLED": "codex",
}


def terminal_confirm(prompt: str) -> str | None:
    """Ask on the controlling terminal; None when the process has none."""
    try:
        descriptor = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    except OSError:
        return None
    with os.fdopen(descriptor, "r+", buffering=1) as terminal:
        terminal.write(prompt)
        terminal.flush()
        return terminal.readline().strip()


def agent_harness(env: Mapping[str, str]) -> str | None:
    return next((name for marker, name in HARNESS_MARKERS.items() if env.get(marker)), None)


def _os_user() -> str | None:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - an unknown account is simply not observed
        return None


def agent_identities(execution: dict[str, Any], lease: dict[str, Any] | None) -> set[str]:
    identities = {actor.get("id") for actor in execution.get("actors", {}).values()
                  if isinstance(actor, dict) and actor.get("type") == "agent"}
    identities |= {item.get("from") for item in execution.get("handoffs", [])}
    if lease:
        identities.add(lease.get("owner"))
    return {identity for identity in identities if identity}


def human_approval_actor(
    execution: dict[str, Any],
    gate: str,
    *,
    approver: str | None,
    relayed_by: str | None,
    lease: dict[str, Any] | None,
    confirm: Confirm = terminal_confirm,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if env is None else env
    execution_id = execution["metadata"]["id"]
    agents = agent_identities(execution, lease)
    if approver and approver in agents:
        raise PermissionError(f"an agent identity of this execution cannot approve its gates: {approver}")
    harness = agent_harness(env)
    observations = {"execution": execution_id, "gate": gate, "osUser": _os_user(), "harness": harness}
    if relayed_by or harness:
        return actor_identity(approver or "human", "human", "adapter", "DECLARED",
                              channel="agent-relay", relayedBy=relayed_by, **observations)
    answer = confirm(f"Approve {gate} for execution {execution_id}? Type '{gate}' to confirm: ")
    if answer is None:
        return actor_identity(approver or observations["osUser"] or "human", "human", "runtime", "DECLARED",
                              channel="non-interactive", **observations)
    if answer != gate:
        raise PermissionError(f"approval of {gate} was not confirmed at the terminal")
    return actor_identity(approver or observations["osUser"] or "human", "human", "terminal-confirmation",
                          "OBSERVED", channel="interactive-terminal", **observations)
