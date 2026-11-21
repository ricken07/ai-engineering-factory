"""Human approval typed in the agent session and delivered by the coding agent harness.

The human types `/approve` (Claude Code) or `$approve` (Codex) in the agent
session. Before the model sees the message, the harness runs its
`UserPromptSubmit` hook, which calls `aief approval hook`: the Runtime reads
the human's message from the harness, not from the model, records the
approval with the `harness-hook` channel and tells the model, as added
context, that the approval is recorded. Without the hook the message reaches
the model only, which cannot approve (the Runtime refuses relayed approvals):
the human then approves in their own terminal.

`/waive <finding-number> <justification>` (`$waive` in Codex) travels the same
way: the human decides that a blocking review finding does not block the
change (see aief.findings).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

HOOK_EVENT = "UserPromptSubmit"
COMMAND = re.compile(r"^\s*[/$]approve(?:\s+(?P<args>[^\n]*))?\s*$")
WAIVE = re.compile(r"^\s*[/$]waive(?:\s+(?P<args>.*?))?\s*$", re.S)
# Where each harness reads project hooks, and the rule that keeps the agent
# itself from invoking the hook entry point through its shell tool.
CONFIG = {"claude-code": Path(".claude/settings.json"), "codex": Path(".codex/hooks.json")}
# Only the human approves: the agent may run neither the approval commands nor
# the hook entry point (defense in depth; the Runtime refuses relays anyway).
CLAUDE_DENY = ["Bash(aief approval *)", "Bash(aief execution approve *)", "Bash(aief execution approve-policy *)",
               "Bash(aief execution waive-finding *)"]
CODEX_RULES = Path(".codex/rules/aief-approval.rules")
CODEX_RULE = """# Only the human approves a Factory gate: the agent may run neither the
# approval commands nor the approval hook, which the Codex harness runs itself.
prefix_rule(
    pattern = ["aief", "approval"],
    decision = "forbidden",
    justification = "Only the harness delivers a human approval to the Runtime",
)

prefix_rule(
    pattern = ["aief", "execution", ["approve", "approve-policy", "waive-finding"]],
    decision = "forbidden",
    justification = "Only the human approves a Factory gate; the Runtime refuses relayed approvals",
)
"""


def hook_command(agent: str) -> str:
    return f"aief approval hook --agent {agent}"


def parse(prompt: str | None) -> list[str] | None:
    """Arguments of an approval message, or None for any other message."""
    match = COMMAND.match(prompt or "")
    if not match:
        return None
    return (match.group("args") or "").split()


USAGE_WAIVE = "waive [<execution-id>] <finding-number> <justification>"


def parse_waive(prompt: str | None) -> tuple[str | None, int | None, str | None] | None:
    """(execution id or None, finding number, justification) of a waive
    message, None for any other message. An incomplete message (no number or
    no justification) yields None for the missing parts: the hook then lists
    the findings waiting for a decision."""
    match = WAIVE.match(prompt or "")
    if not match:
        return None
    text = (match.group("args") or "").strip()
    execution = None
    first = text.split(maxsplit=1)
    if first and not first[0].isdigit():
        execution, text = first[0], (first[1] if len(first) > 1 else "")
    words = text.split(maxsplit=1)
    if not words:
        return execution, None, None
    if not words[0].isdigit():
        raise ValueError(f"usage: {USAGE_WAIVE}")
    justification = words[1].strip() if len(words) > 1 else ""
    return execution, int(words[0]), justification or None


def pending_findings(service: Any, execution: str) -> tuple[str, list[str]]:
    """Review name and numbered lines of its blocking findings still waiting
    for a human decision."""
    from .findings import blocking_findings, unresolved
    record = service.execution(execution)
    name, _ = service._waivable_review(record)
    findings = blocking_findings(record.root / name)
    lines = []
    for number in unresolved(record.data, record.root / name):
        item = findings[number - 1]
        if isinstance(item, dict):
            head = " ".join(str(item[key]) for key in ("severity", "criterion") if item.get(key)) or "finding"
            where = f" ({item['location']})" if item.get("location") else ""
            text = " ".join(str(item.get("finding", "")).split())
            lines.append(f"  {number}. {head}{where}: {text[:220]}{'...' if len(text) > 220 else ''}")
        else:
            lines.append(f"  {number}. {' '.join(str(item).split())[:220]}")
    return name, lines


def waive_listing(service: Any, execution: str | None, candidates: list[str]) -> str:
    """What the human needs to type a complete waive: the findings waiting
    for a decision, numbered, and the exact syntax."""
    targets = [execution] if execution else candidates
    if not targets:
        return "No review finding of this project is waiting for a decision."
    blocks = []
    for identifier in targets:
        name, lines = pending_findings(service, identifier)
        blocks.append(f"Execution {identifier}, review {name}:\n" + ("\n".join(lines) or "  (every finding is decided)"))
    example = "/waive 1 <why this finding does not block the change>" if len(targets) == 1 \
        else f"/waive {targets[0]} 1 <why this finding does not block the change>"
    return ("Blocking findings waiting for your decision:\n" + "\n".join(blocks) +
            f"\nType: {USAGE_WAIVE} (for example: {example}); $waive in Codex.")


def waivable_executions(service: Any) -> list[str]:
    from .project import runtime_root
    root = runtime_root(service.project_root, service.project) / "executions"
    result = []
    for path in sorted(root.glob("*/execution.yaml")) if root.is_dir() else []:
        try:
            service._waivable_review(service.execution(path.parent.name))
        except (ValueError, StopIteration):
            continue
        result.append(path.parent.name)
    return result


def awaited_approvals(service: Any) -> list[dict[str, str]]:
    """Approvals the executions of the project are currently waiting for."""
    from .project import runtime_root
    root = runtime_root(service.project_root, service.project) / "executions"
    result = []
    for path in sorted(root.glob("*/execution.yaml")) if root.is_dir() else []:
        execution = service.execution(path.parent.name)
        if execution.data.get("status") != "waiting-approval":
            continue
        phase = execution.next_phase()
        if phase is None:
            continue
        identifier = execution.data["metadata"]["id"]
        if phase.get("status") == "waiting-approval":
            result.append({"execution": identifier, "gate": phase["id"], "kind": "phase"})
            continue
        for gate in sorted(service._pending_policy_gates(execution, phase["id"])):
            result.append({"execution": identifier, "gate": gate, "kind": "policy"})
    return result


def select(arguments: list[str], awaited: list[dict[str, str]]) -> list[dict[str, str]]:
    executions = {item["execution"] for item in awaited}
    wanted_execution = next((value for value in arguments if value in executions), None)
    gates = [value for value in arguments if value != wanted_execution]
    if len(gates) > 1 or (arguments and wanted_execution is None and not gates):
        raise ValueError("usage: approve [<execution-id>] [<gate>]")
    candidates = [item for item in awaited
                  if (wanted_execution is None or item["execution"] == wanted_execution)
                  and (not gates or item["gate"] == gates[0])]
    if not candidates:
        raise ValueError("no execution is waiting for this approval" if awaited
                         else "no execution of this project is waiting for an approval")
    if len({item["execution"] for item in candidates}) > 1:
        listed = ", ".join(f"{item['execution']} {item['gate']}" for item in candidates)
        raise ValueError(f"several executions are waiting; name one: {listed}")
    return candidates


def handle(payload: dict[str, Any], agent: str, open_service: Callable[[Path], Any]) -> tuple[int, str, str]:
    """(exit code, stdout, stderr) for the harness: exit 2 blocks the message."""
    arguments = parse(payload.get("prompt"))
    if arguments is None:
        return _handle_waive(payload, agent, open_service)
    fallback = ("To approve without the harness hook, run in your own terminal: "
                "aief execution approve-policy <execution-id> <gate> --approver <name>")
    try:
        service = open_service(Path(payload.get("cwd") or "."))
        chosen = select(arguments, awaited_approvals(service))
        hook = {"agent": agent, "session": payload.get("session_id"),
                "prompt": payload.get("prompt_id") or payload.get("turn_id")}
        for item in chosen:
            if item["kind"] == "phase":
                service.approve_execution(item["execution"], _hook=hook)
            else:
                service.approve_policy_gate(item["execution"], item["gate"], _hook=hook)
    except Exception as error:  # noqa: BLE001 - every refusal is reported to the human
        return 2, "", f"AIEF approval not recorded: {error}. {fallback}"
    execution = chosen[0]["execution"]
    gates = ", ".join(item["gate"] for item in chosen)
    return 0, (f"AIEF: the human approved {gates} for execution {execution} in this message; the "
               f"{agent} harness delivered it to the Runtime, which recorded it (channel harness-hook, "
               f"OBSERVED). Do not run any approval command. Continue with "
               f"'aief execution next {execution}'.\n"), ""


def _handle_waive(payload: dict[str, Any], agent: str, open_service: Callable[[Path], Any]) -> tuple[int, str, str]:
    fallback = ("To decide without the harness hook, run in your own terminal: "
                "aief execution waive-finding <execution-id> <finding-number> --reason <justification> --approver <name>")
    try:
        parsed = parse_waive(payload.get("prompt"))
        if parsed is None:
            return 0, "", ""
        execution, finding, justification = parsed
        service = open_service(Path(payload.get("cwd") or "."))
        candidates = waivable_executions(service)
        if finding is None or justification is None:
            # Incomplete message: nothing is decided; show what can be.
            listing = waive_listing(service, execution, candidates)
            missing = "" if finding is None else "A justification is required. "
            return 2, "", f"AIEF decision not recorded. {missing}{listing}"
        if execution is None:
            if len(candidates) != 1:
                raise ValueError("no execution has a review finding waiting for a decision" if not candidates
                                 else "several executions have review findings; name one: " + ", ".join(candidates))
            execution = candidates[0]
        hook = {"agent": agent, "session": payload.get("session_id"),
                "prompt": payload.get("prompt_id") or payload.get("turn_id")}
        result = service.waive_finding(execution, finding, justification, _hook=hook)
    except Exception as error:  # noqa: BLE001 - every refusal is reported to the human
        return 2, "", f"AIEF decision not recorded: {error}. {fallback}"
    if result["overruled"]:
        follow = (f"Every blocking finding of {result['review']} is now decided: the Runtime continues the execution "
                  f"(next phase: {result['next']}). Continue with 'aief execution next {execution}'.")
    elif result["remaining"]:
        follow = (f"Findings still blocking: {', '.join(map(str, result['remaining']))}. Address them; do not address "
                  f"finding {finding}. Continue with 'aief execution next {execution}'.")
    else:
        follow = (f"The rework already started: do not address finding {finding}. Continue with "
                  f"'aief execution next {execution}'.")
    return 0, (f"AIEF: the human decided in this message that finding {finding} of {result['review']} does not block "
               f"execution {execution}; the {agent} coding agent harness delivered it to the Runtime, which recorded "
               f"it (OBSERVED). Run no decision command yourself. {follow}\n"), ""


def _entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    return config.setdefault("hooks", {}).setdefault(HOOK_EVENT, [])


def installed(project_root: Path, agent: str) -> bool:
    path = project_root / CONFIG[agent]
    if not path.is_file():
        return False
    config = json.loads(path.read_text(encoding="utf-8") or "{}")
    return any(hook.get("command") == hook_command(agent)
               for entry in config.get("hooks", {}).get(HOOK_EVENT, []) for hook in entry.get("hooks", []))


def install(project_root: Path, agent: str) -> Path:
    """Add the approval hook to the project's harness configuration (idempotent)."""
    path = project_root / CONFIG[agent]
    config = json.loads(path.read_text(encoding="utf-8") or "{}") if path.is_file() else {}
    if not installed(project_root, agent):
        _entries(config).append({"hooks": [{"type": "command", "command": hook_command(agent), "timeout": 120}]})
    if agent == "claude-code":
        deny = config.setdefault("permissions", {}).setdefault("deny", [])
        deny.extend(rule for rule in CLAUDE_DENY if rule not in deny)
    else:
        rules = project_root / CODEX_RULES
        rules.parent.mkdir(parents=True, exist_ok=True)
        rules.write_text(CODEX_RULE, encoding="utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path
