#!/usr/bin/env python3
"""Run one experimental unit of the AIEF reference-model evaluation.

One unit is one coding-agent execution of one engineering task under one
control condition (reference model, section 7):

- L0 raw agent: the request only, no project or agent configuration;
- L1 contextualized agent: the request plus a frozen structured project context;
- L2 structured engineering: L1 plus the frozen task plan and verification
  specification, without governance;
- L3 governed engineering execution: the AIEF Runtime, with the same frozen
  plan and verification bound to the execution.

The launcher prepares an isolated clone at the task's starting commit,
prepares the condition, invokes the coding agent headless and records the
run. It never approves, rejects or waives anything: human gates are decided by
a human from their own terminal. It does not evaluate outcomes; the oracle and
the evidence checklist are separate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

LAUNCHER_VERSION = "2"
DEFAULT_ACTIVE_BUDGET_MINUTES = 120
CONDITIONS = ("L0", "L1", "L2", "L3")
PLAIN = {"L0", "L1", "L2"}
AGENTS = ("claude-code", "codex")
# Paths that carry project or agent configuration; L0 to L2 run without them.
STRIP = [".ai", ".claude", ".codex", "AGENTS.md", "CLAUDE.md"]
TREATMENT_DIR = ".experiment"
TERMINAL = {"completed", "failed", "cancelled"}

PROMPTS = {
    "plain": "{request}",
    "structured": ("{request}\n\nFollow the task plan in `{treatment}/{plan}`. Verify the change as specified in "
                   "`{treatment}/{verification}` and report each acceptance criterion with its verification result."),
    "governed": ("{command} {request}\n\nResearch run: when you start the AIEF Runtime with `aief run`, pass "
                 "exactly these arguments in addition to the ones of the Runtime protocol: {flags}"),
    "continue": ("Run `aief execution next {execution}` and continue the AIEF Runtime protocol for this execution "
                 "only, until a terminal or waiting state. Never approve, reject or waive anything."),
    "review": ("You are an independent review session. The AIEF execution {execution} was produced by another "
               "session, which handed it off, and waits for its review phase. Acquire the execution lease with your "
               "own owner ({agent}:<your session id>), then follow the AIEF Runtime protocol from `aief execution "
               "next` for this execution only, until a terminal or waiting state. You review another producer's "
               "change: modify no file of the worktree. Never approve, reject or waive anything."),
}
PROMPTS_SHA256 = hashlib.sha256(json.dumps(PROMPTS, sort_keys=True).encode()).hexdigest()


class LaunchError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand(value: str | None, base: Path | None = None) -> Path | None:
    if value is None:
        return None
    path = Path(os.path.expanduser(str(value)))
    return path if path.is_absolute() or base is None else (base / path)


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, env=env)
    if result.returncode != 0:
        raise LaunchError(f"git {' '.join(args)} failed in {repo}: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LaunchError(f"{path} must be a YAML mapping")
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    temporary.replace(path)


# --------------------------------------------------------------------------- prepare

def _descriptor(run: dict[str, Any], base: Path) -> dict[str, Any]:
    task = run.get("task") or {}
    for key in ("id", "repository", "startingCommit", "request"):
        if not task.get(key):
            raise LaunchError(f"task.{key} is required")
    condition = run.get("condition")
    if condition not in CONDITIONS:
        raise LaunchError(f"condition must be one of {', '.join(CONDITIONS)}")
    agent = (run.get("agent") or {}).get("name")
    if agent not in AGENTS:
        raise LaunchError(f"agent.name must be one of {', '.join(AGENTS)}")
    if not isinstance(run.get("repeatIndex"), int) or run["repeatIndex"] < 1:
        raise LaunchError("repeatIndex must be a positive integer")
    treatment = run.get("treatment") or {}
    needed = {"L0": [], "L1": ["context"], "L2": ["context", "plan", "verification"], "L3": ["plan", "verification"]}
    for key in needed[condition]:
        if not treatment.get(key):
            raise LaunchError(f"condition {condition} needs treatment.{key}")
    if condition == "L3" and not task.get("intent"):
        raise LaunchError("condition L3 needs task.intent (the AIEF native command, for example implement or fix)")
    files = {}
    for key in ("context", "plan", "verification"):
        if treatment.get(key):
            path = expand(treatment[key], base)
            if not path.is_file():
                raise LaunchError(f"treatment file not found: {path}")
            digest = sha256(path)
            frozen = (treatment.get("sha256") or {}).get(key)
            if frozen and frozen != digest:
                raise LaunchError(f"treatment.{key} {path} has SHA-256 {digest}, not the frozen {frozen}")
            files[key] = {"source": str(path), "sha256": digest, "frozen": frozen}
    if condition == "L3":
        # The plan gate compares the bound files with these hashes; without them it could only compare a file
        # with itself, and a plan that drifted from the freeze would pass the gate unseen.
        missing = [key for key in ("plan", "verification") if not files[key]["frozen"]]
        if missing:
            raise LaunchError("condition L3 needs the frozen SHA-256 of " + " and ".join(f"treatment.{key}" for key in missing)
                              + " in treatment.sha256: the plan gate compares the bound files with them")
    if "plan" in files and "verification" in files and Path(files["plan"]["source"]).name == Path(files["verification"]["source"]).name:
        raise LaunchError("the plan and the verification files need distinct names")
    return {"task": task, "condition": condition, "agent": run["agent"], "repeatIndex": run["repeatIndex"],
            "treatment": files}


def _strip(repo: Path) -> list[str]:
    removed = []
    for name in STRIP:
        if (repo / name).exists():
            git(repo, "rm", "-r", "-q", "--cached", "--ignore-unmatch", name)
            path = repo / name
            shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()
            removed.append(name)
    return removed


def _commit(repo: Path, message: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "aief-experiment", "GIT_AUTHOR_EMAIL": "aief-experiment@localhost",
           "GIT_COMMITTER_NAME": "aief-experiment", "GIT_COMMITTER_EMAIL": "aief-experiment@localhost",
           "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00"}
    git(repo, "add", "-A", env=env)
    git(repo, "commit", "-q", "--allow-empty", "-m", message, env=env)
    return git(repo, "rev-parse", "HEAD")


def _version(command: str) -> str | None:
    try:
        result = subprocess.run([command, "--version"], text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else None


def prepare(run_file: Path, environment_file: Path, output: Path, run_id: str | None = None) -> Path:
    descriptor = _descriptor(load_yaml(run_file), run_file.parent)
    environment = load_yaml(environment_file)
    if not environment.get("id"):
        raise LaunchError("environment id is required")
    agent_name = descriptor["agent"]["name"]
    agent_config = (environment.get("agents") or {}).get(agent_name)
    if not agent_config:
        raise LaunchError(f"environment has no configuration for agent {agent_name}")
    task, condition = descriptor["task"], descriptor["condition"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = run_id or f"{task['id']}-{condition}-{agent_name}-r{descriptor['repeatIndex']}-{stamp}"
    run_dir = output / run_id
    if run_dir.exists():
        raise LaunchError(f"run directory already exists: {run_dir}")
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "prompts").mkdir()
    source = expand(task["repository"])
    repo = run_dir / "repo"
    subprocess.run(["git", "clone", "-q", "--no-local", str(source), str(repo)], check=True)
    git(repo, "checkout", "-q", "-b", f"experiment/{run_id}", task["startingCommit"])
    starting = git(repo, "rev-parse", "HEAD")
    if git(repo, "rev-parse", f"{task['startingCommit']}^{{commit}}") != starting:
        raise LaunchError("the clone is not at the task's starting commit")
    initial_branches = dict(line.split() for line in
                            git(repo, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads").splitlines())
    treatment_dir = run_dir / "treatment"
    treatment_dir.mkdir()
    for key, item in descriptor["treatment"].items():
        copy = treatment_dir / Path(item["source"]).name
        shutil.copy2(item["source"], copy)
        item["copy"] = str(copy)
    setup: dict[str, Any] = {"removed": [], "added": []}
    base = starting
    if condition in PLAIN:
        setup["removed"] = _strip(repo)
        if condition in {"L1", "L2"}:
            context = Path(descriptor["treatment"]["context"]["copy"]).read_text(encoding="utf-8")
            (repo / "AGENTS.md").write_text(context, encoding="utf-8")
            (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
            setup["added"] += ["AGENTS.md", "CLAUDE.md"]
        if condition == "L2":
            target = repo / TREATMENT_DIR
            target.mkdir()
            for key in ("plan", "verification"):
                shutil.copy2(descriptor["treatment"][key]["copy"], target / Path(descriptor["treatment"][key]["copy"]).name)
            setup["added"].append(TREATMENT_DIR)
        base = _commit(repo, f"experiment: prepare {condition} environment")
    factory = expand(environment.get("factory"))
    record = {
        "apiVersion": "aief.dev/v1alpha1", "kind": "ExperimentRun", "launcherVersion": LAUNCHER_VERSION,
        "runId": run_id, "status": "prepared", "preparedAt": now(),
        "environmentFile": str(environment_file.resolve()), "initialBranches": initial_branches,
        "experimentalCondition": condition, "repeatIndex": descriptor["repeatIndex"],
        "environmentIdentifier": environment["id"],
        "task": {"id": task["id"], "intent": task.get("intent"), "repository": str(source),
                 "startingCommit": starting, "requestSha256": hashlib.sha256(task["request"].encode()).hexdigest(),
                 "acceptanceCriteria": task.get("acceptanceCriteria")},
        "agent": {"name": agent_name, "command": agent_config.get("command", agent_name),
                  "version": _version(agent_config.get("command", agent_name)),
                  "modelIdentifier": descriptor["agent"].get("model")},
        "factory": {"home": str(factory) if factory else None,
                    "commit": git(factory, "rev-parse", "HEAD") if factory and (factory / ".git").exists() else None},
        "prompts": {"version": PROMPTS_SHA256},
        "treatment": descriptor["treatment"], "setup": setup, "baseCommit": base,
        "isolation": _isolation_mode(condition, agent_config),
        # Active budget (RC2 §9.4, §12.4): elapsed time since the first agent step minus the union of human-gate waits.
        "activeBudgetSeconds": round(float(environment.get("activeBudgetMinutes", DEFAULT_ACTIVE_BUDGET_MINUTES)) * 60, 3),
        "activeSeconds": 0.0,
        "steps": [],
    }
    (run_dir / "request.txt").write_text(task["request"], encoding="utf-8")
    write_yaml(run_dir / "run.yaml", record)
    return run_dir


def _isolation_mode(condition: str, agent_config: dict[str, Any]) -> dict[str, Any]:
    group = agent_config.get("plain" if condition in PLAIN else "governed") or {}
    return {"group": "plain" if condition in PLAIN else "governed", "isolatedHome": bool(group.get("isolatedHome")),
            "note": "organization-managed settings, hooks and instructions of the agent account still apply"}


# --------------------------------------------------------------------------- agent invocation

def _home(run_dir: Path, environment: dict[str, Any], agent: str, agent_config: dict[str, Any]) -> Path:
    home = run_dir / "home"
    home.mkdir(exist_ok=True)
    real = Path.home()
    for name in (environment.get("isolation") or {}).get("homeLinks", []):
        if (real / name).exists() and not (home / name).exists():
            (home / name).symlink_to(real / name)
    if agent == "codex":
        codex = home / ".codex"
        codex.mkdir(exist_ok=True)
        auth = expand(agent_config.get("authFile", "~/.codex/auth.json"))
        if not auth.is_file():
            raise LaunchError(f"codex auth file not found: {auth}")
        if not (codex / "auth.json").exists():
            (codex / "auth.json").symlink_to(auth)
    return home


def _command(record: dict[str, Any], environment: dict[str, Any], run_dir: Path, prompt: str,
             session: str | None, last: Path) -> tuple[list[str], dict[str, str]]:
    agent = record["agent"]["name"]
    config = environment["agents"][agent]
    group = config.get(record["isolation"]["group"]) or {}
    command = config.get("command", agent)
    env = {**os.environ}
    if record["experimentalCondition"] == "L3" and record["factory"]["home"]:
        env["AI_FACTORY_HOME"] = record["factory"]["home"]
    if group.get("isolatedHome"):
        home = _home(run_dir, environment, agent, config)
        env["HOME"] = str(home)
        if agent == "codex":
            env["CODEX_HOME"] = str(home / ".codex")
        if agent == "claude-code":
            token = expand(config.get("tokenFile"))
            if not token or not token.is_file():
                raise LaunchError("an isolated Claude Code home needs tokenFile (created with `claude setup-token`)")
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token.read_text(encoding="utf-8").strip()
    model = record["agent"].get("modelIdentifier")
    args = [str(item) for item in group.get("args", [])]
    if agent == "claude-code":
        argv = [command, "-p", prompt, "--output-format", "json", *args]
        if model:
            argv += ["--model", model]
        if session:
            argv += ["--resume", session]
    else:
        argv = [command, "exec", "--skip-git-repo-check", "--json", "-o", str(last), *args]
        if model:
            argv += ["-m", model]
        argv += (["resume", session, prompt] if session else [prompt])
    return argv, env


def _session(agent: str, stdout: str) -> tuple[str | None, bool | None]:
    if agent == "claude-code":
        try:
            data = json.loads(stdout)
        except ValueError:
            return None, None
        return data.get("session_id"), data.get("is_error")
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        identifier = event.get("thread_id") or event.get("session_id") or (event.get("msg") or {}).get("session_id")
        if identifier:
            return identifier, None
    return None, None


def _parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _gate_intervals(run_dir: Path, at: datetime) -> list[tuple[datetime, datetime]]:
    """Human-gate waits the Runtime recorded for the run's execution; a gate still waiting runs until `at`.

    L0–L2 runs have no Runtime and therefore no gate wait."""
    executions = _executions(run_dir / "repo")
    if not executions:
        return []
    data = load_yaml(executions[-1])
    intervals = []
    for decision in data.get("gateDecisions") or []:
        start, end = _parse_time(decision.get("waitStartedAt")), _parse_time(decision.get("decidedAt"))
        if start and end:
            intervals.append((start, end))
    for phase in data.get("phases", []):
        timing = phase.get("gateTiming") or {}
        if phase.get("status") == "waiting-approval" and not timing.get("decidedAt") and not timing.get("closedAt"):
            start = _parse_time(timing.get("blockedAt"))
            if start:
                intervals.append((start, at))
    for gate in data.get("policyGates", []):
        timing = gate.get("timing") or {}
        if gate.get("status") == "pending" and timing.get("blockedAt") and not timing.get("decidedAt"):
            intervals.append((_parse_time(timing["blockedAt"]), at))
    integration = data.get("integration") or {}
    if integration.get("status") == "awaiting-approval" and _parse_time(integration.get("requestedAt")):
        intervals.append((_parse_time(integration["requestedAt"]), at))
    return [(start, end) for start, end in intervals if start and end and end > start]


def _active_seconds(run_dir: Path, record: dict[str, Any], at: datetime | None = None) -> float:
    """Active wall-clock (RC2 §9.4): elapsed time since the first agent step minus the union of gate waits."""
    steps = record.get("steps") or []
    first = _parse_time(steps[0].get("startedAt")) if steps else None
    if first is None:
        return 0.0
    at = at or datetime.now(timezone.utc)
    merged: list[list[datetime]] = []
    for start, end in sorted(_gate_intervals(run_dir, at)):
        start, end = max(start, first), min(end, at)
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    waiting = sum((end - start).total_seconds() for start, end in merged)
    return max(0.0, (at - first).total_seconds() - waiting)


def _remaining_budget(record: dict[str, Any], run_dir: Path | None = None) -> float:
    """Seconds of active budget left: elapsed time since the first step counts, human-gate waits do not."""
    budget = record.get("activeBudgetSeconds", DEFAULT_ACTIVE_BUDGET_MINUTES * 60)
    if run_dir is None:
        return budget - sum(step.get("durationSeconds") or 0 for step in record.get("steps", []))
    return budget - _active_seconds(run_dir, record)


def _invoke(run_dir: Path, role: str, kind: str, prompt: str, session: str | None = None,
            agent: str | None = None) -> dict[str, Any]:
    record = load_yaml(run_dir / "run.yaml")
    if record.get("resourceLimitReached"):
        raise LaunchError("the run reached its active budget (RESOURCE_LIMIT_REACHED): it is finished, collect it")
    remaining = _remaining_budget(record, run_dir)
    if remaining <= 0:
        _limit_reached(run_dir)
        raise LaunchError("the run has no active budget left (RESOURCE_LIMIT_REACHED): collect it")
    environment = load_yaml(Path(record["environmentFile"]))
    if agent and agent != record["agent"]["name"]:
        record = {**record, "agent": {**record["agent"], "name": agent, "modelIdentifier": None,
                                      "command": environment["agents"][agent].get("command", agent)}}
    index = len(load_yaml(run_dir / "run.yaml")["steps"]) + 1
    name = f"step-{index:02d}-{role}"
    prompt_file = run_dir / "prompts" / f"{name}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    last = run_dir / "logs" / f"{name}.last.txt"
    argv, env = _command(record, environment, run_dir, prompt, session, last)
    started, clock = now(), time.monotonic()
    with open(run_dir / "logs" / f"{name}.out", "w", encoding="utf-8") as out, \
            open(run_dir / "logs" / f"{name}.err", "w", encoding="utf-8") as err:
        try:
            result = subprocess.run(argv, cwd=run_dir / "repo", env=env, stdout=out, stderr=err,
                                    stdin=subprocess.DEVNULL, text=True, timeout=remaining)
            exit_code, limit = result.returncode, False
        except subprocess.TimeoutExpired:
            # subprocess.run kills the agent process when the budget runs out.
            exit_code, limit = None, True
    stdout = (run_dir / "logs" / f"{name}.out").read_text(encoding="utf-8", errors="replace")
    identifier, is_error = _session(record["agent"]["name"], stdout)
    step = {"index": index, "role": role, "kind": kind, "agent": record["agent"]["name"],
            "prompt": str(prompt_file.relative_to(run_dir)), "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "startedAt": started, "endedAt": now(), "durationSeconds": round(time.monotonic() - clock, 3),
            "exitCode": exit_code, "sessionId": identifier or session, "agentReportedError": is_error,
            "stdout": f"logs/{name}.out", "stderr": f"logs/{name}.err"}
    if limit:
        step["resourceLimitReached"] = True
    current = load_yaml(run_dir / "run.yaml")
    current["steps"].append(step)
    current["agentSeconds"] = round(sum(item.get("durationSeconds") or 0 for item in current["steps"]), 3)
    current["activeSeconds"] = round(_active_seconds(run_dir, current), 3)
    current["status"] = "running"
    write_yaml(run_dir / "run.yaml", current)
    if limit:
        _limit_reached(run_dir)
    return step


def _limit_reached(run_dir: Path) -> None:
    """RESOURCE_LIMIT_REACHED is an outcome of a valid run, not an exclusion (RC2 §12.4)."""
    current = load_yaml(run_dir / "run.yaml")
    current.update({"resourceLimitReached": True, "status": "resource-limit-reached", "resourceLimitReachedAt": now()})
    write_yaml(run_dir / "run.yaml", current)


def _governed_flags(record: dict[str, Any], run_dir: Path) -> str:
    treatment = record["treatment"]
    model = record["agent"].get("modelIdentifier")
    flags = ["--experiment-condition", "L3", "--repeat-index", str(record["repeatIndex"]),
             "--environment-identifier", record["environmentIdentifier"],
             "--agent-session", f"{record['agent']['name']}:{record['runId']}",
             "--bound-plan", treatment["plan"]["copy"], "--bound-verification", treatment["verification"]["copy"],
             "--expect-plan-sha256", treatment["plan"]["frozen"],
             "--expect-verification-sha256", treatment["verification"]["frozen"]]
    if model:
        flags += ["--model-identifier", model]
    return " ".join(f'"{item}"' if " " in item else item for item in flags)


def start(run_dir: Path) -> dict[str, Any]:
    record = load_yaml(run_dir / "run.yaml")
    if record["steps"]:
        raise LaunchError("the run already started; use continue, review or finish")
    request = (run_dir / "request.txt").read_text(encoding="utf-8")
    condition = record["experimentalCondition"]
    if condition in {"L0", "L1"}:
        prompt = PROMPTS["plain"].format(request=request)
    elif condition == "L2":
        prompt = PROMPTS["structured"].format(request=request, treatment=TREATMENT_DIR,
                                              plan=Path(record["treatment"]["plan"]["copy"]).name,
                                              verification=Path(record["treatment"]["verification"]["copy"]).name)
    else:
        prefix = "/" if record["agent"]["name"] == "claude-code" else "$"
        prompt = PROMPTS["governed"].format(command=f"{prefix}{record['task']['intent']}", request=request,
                                            flags=_governed_flags(record, run_dir))
    step = _invoke(run_dir, "producer", "start", prompt)
    _observe(run_dir)
    return step


# --------------------------------------------------------------------------- AIEF state (L3)

def _executions(repo: Path) -> list[Path]:
    root = repo / ".ai" / "runtime" / "executions"
    return sorted(root.glob("*/execution.yaml")) if root.is_dir() else []


def _observe(run_dir: Path) -> dict[str, Any] | None:
    """Record the AIEF execution of an L3 run as the Runtime persisted it."""
    record = load_yaml(run_dir / "run.yaml")
    if record["experimentalCondition"] != "L3":
        return None
    executions = _executions(run_dir / "repo")
    if not executions:
        record["aief"] = {"executionId": None, "status": "not-started"}
    else:
        data = load_yaml(executions[-1])
        phase = next((item for item in data.get("phases", []) if item.get("status") != "completed"), None)
        record["aief"] = {"executionId": data["metadata"]["id"], "executions": len(executions),
                          "status": data.get("status"), "nextPhase": phase["id"] if phase else None,
                          "blockingReason": data.get("blockingReason"), "observedAt": now()}
        if data.get("integration"):
            record["aief"]["integration"] = data["integration"].get("status")
    write_yaml(run_dir / "run.yaml", record)
    return record["aief"]


def _require_execution(run_dir: Path) -> str:
    state = _observe(run_dir)
    if state is None:
        raise LaunchError("continue, review and wait apply to L3 runs only")
    if not state.get("executionId"):
        raise LaunchError("no AIEF execution exists in this run yet")
    return state["executionId"]


def continue_run(run_dir: Path, message: str | None = None) -> dict[str, Any]:
    execution = _require_execution(run_dir)
    record = load_yaml(run_dir / "run.yaml")
    producer = next((step for step in reversed(record["steps"]) if step["role"] == "producer" and step.get("sessionId")), None)
    prompt = message or PROMPTS["continue"].format(execution=execution)
    step = _invoke(run_dir, "producer", "continue", prompt, session=producer["sessionId"] if producer else None)
    _observe(run_dir)
    return step


def review(run_dir: Path, agent: str) -> dict[str, Any]:
    execution = _require_execution(run_dir)
    if agent not in AGENTS:
        raise LaunchError(f"reviewer agent must be one of {', '.join(AGENTS)}")
    step = _invoke(run_dir, "reviewer", "review", PROMPTS["review"].format(execution=execution, agent=agent), agent=agent)
    _observe(run_dir)
    return step


def _aief(run_dir: Path, args: list[str]) -> subprocess.CompletedProcess | None:
    """Runs an `aief execution` command on the run's project, with the Factory of the run."""
    factory = load_yaml(run_dir / "run.yaml").get("factory", {}).get("home")
    env = {**os.environ, **({"AI_FACTORY_HOME": factory} if factory else {})}
    try:
        return subprocess.run(["aief", "execution", *args, "--project", str(run_dir / "repo")],
                              cwd=run_dir / "repo", env=env, capture_output=True, text=True)
    except FileNotFoundError:
        return None


def _waiting(state: dict[str, Any]) -> bool:
    return state.get("status") == "waiting-approval" or state.get("integration") == "awaiting-approval"


def wait(run_dir: Path, interval: float = 20.0, timeout: float = 0.0) -> dict[str, Any]:
    """Wait while the execution, or its integration, waits for a human: the human decides from their own terminal.

    Each poll goes through `aief execution gate-check`, which applies a
    response limit that has passed: a gate that nobody decided expires at its
    deadline instead of keeping the run waiting."""
    clock = time.monotonic()
    while True:
        state = _observe(run_dir) or {}
        if state.get("executionId") and _waiting(state):
            _aief(run_dir, ["gate-check", state["executionId"], "--json"])
            state = _observe(run_dir) or {}
        if not _waiting(state):
            return state
        if timeout and time.monotonic() - clock > timeout:
            return state
        time.sleep(interval)


# --------------------------------------------------------------------------- finish

def _snapshot_diff(repo: Path, base: str, target: Path) -> None:
    """Diff of everything in the working tree (untracked files included) against base, without touching the index."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git(repo, "read-tree", "HEAD", env=env)
        git(repo, "add", "-A", env=env)
        diff = subprocess.run(["git", "diff", "--cached", "--binary", base], cwd=repo, env=env, capture_output=True)
    target.write_bytes(diff.stdout)


def _aief_outputs(run_dir: Path, execution: str, factory: str | None) -> dict[str, Any]:
    out = run_dir / "aief"
    out.mkdir(exist_ok=True)
    root = run_dir / "repo" / ".ai" / "runtime" / "executions" / execution
    env = {**os.environ, **({"AI_FACTORY_HOME": factory} if factory else {})}
    results = {}
    # gate-check first: it applies a passed deadline, so the copied state is final.
    for command in (["gate-check", "--json"], ["payload-ledger", "--json"], ["metrics", "--json"]):
        result = subprocess.run(["aief", "execution", command[0], execution, *command[1:], "--project", str(run_dir / "repo")],
                                cwd=run_dir / "repo", env=env, capture_output=True, text=True)
        (out / f"{command[0]}.json").write_text(result.stdout, encoding="utf-8")
        results[command[0]] = result.returncode
    for name in ("execution.yaml", "evidence-bundle.yaml", "workspace.yaml"):
        if (root / name).is_file():
            shutil.copy2(root / name, out / name)
    return results


def finish(run_dir: Path) -> dict[str, Any]:
    record = load_yaml(run_dir / "run.yaml")
    repo = run_dir / "repo"
    final = run_dir / "final"
    final.mkdir(exist_ok=True)
    _snapshot_diff(repo, record["baseCommit"], final / "workspace.patch")
    (final / "status.txt").write_text(git(repo, "status", "--porcelain=v1", "--untracked-files=all"), encoding="utf-8")
    (final / "commits.txt").write_text(git(repo, "log", "--format=%H %s", f"{record['baseCommit']}..HEAD"), encoding="utf-8")
    branches = {}
    for line in git(repo, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads").splitlines():
        name, head = line.split()
        if name != f"experiment/{record['runId']}" and record.get("initialBranches", {}).get(name) != head:
            patch = final / f"branch-{name.replace('/', '_')}.patch"
            patch.write_bytes(subprocess.run(["git", "diff", "--binary", record["baseCommit"], head], cwd=repo,
                                             capture_output=True).stdout)
            branches[name] = {"head": head, "patch": str(patch.relative_to(run_dir))}
    record = load_yaml(run_dir / "run.yaml")
    record["final"] = {"finishedAt": now(), "head": git(repo, "rev-parse", "HEAD"), "branches": branches,
                       "workspacePatch": "final/workspace.patch",
                       "workspacePatchSha256": sha256(final / "workspace.patch")}
    if record["experimentalCondition"] == "L3":
        write_yaml(run_dir / "run.yaml", record)
        state = _observe(run_dir) or {}
        record = load_yaml(run_dir / "run.yaml")
        if state.get("executionId"):
            record["aief"]["outputs"] = _aief_outputs(run_dir, state["executionId"], record["factory"]["home"])
    steps = record["steps"]
    record["timing"] = {"firstStepAt": steps[0]["startedAt"] if steps else None,
                        "agentSeconds": round(sum(step["durationSeconds"] for step in steps), 3)}
    record["status"] = "finished"
    write_yaml(run_dir / "run.yaml", record)
    return record


# --------------------------------------------------------------------------- render-context

def render_context(project: Path, factory: Path, repositories: list[str], skill: str, output: Path) -> str:
    """Render the structured project context AIEF resolves for a skill, as a
    single Markdown file to freeze as the L1/L2 treatment."""
    env = {**os.environ, "AI_FACTORY_HOME": str(factory)}
    seen: dict[str, dict[str, Any]] = {}
    for repository in repositories:
        result = subprocess.run(["aief", "engineering-context", repository, skill, "--project", str(project),
                                 "--factory", str(factory), "--json"], text=True, capture_output=True, env=env)
        if result.returncode != 0:
            raise LaunchError(f"aief engineering-context failed: {(result.stderr or result.stdout).strip()[:300]}")
        for practice in json.loads(result.stdout).get("practices", []):
            seen.setdefault(practice["id"], {**practice, "repositories": []})["repositories"].append(repository)
    lines = ["# Project context", "", "Engineering context of this project. Follow every practice that applies to the "
             "repository you change."]
    for practice in seen.values():
        lines += ["", f"## {practice['id']}", "", f"Applies to: {', '.join(practice['repositories'])}.", "",
                  practice.get("content", "").strip()]
    text = "\n".join(lines) + "\n"
    output.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aief_experiment", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="clone the task and prepare the condition")
    p.add_argument("run", type=Path); p.add_argument("--environment", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True); p.add_argument("--run-id")
    for name in ("start", "status", "finish"):
        sub.add_parser(name).add_argument("run_dir", type=Path)
    c = sub.add_parser("continue", help="resume the producer session of an L3 run"); c.add_argument("run_dir", type=Path)
    c.add_argument("--message")
    r = sub.add_parser("review", help="start an independent review session of an L3 run"); r.add_argument("run_dir", type=Path)
    r.add_argument("--agent", required=True, choices=AGENTS)
    w = sub.add_parser("wait", help="wait while an L3 execution waits for a human decision"); w.add_argument("run_dir", type=Path)
    w.add_argument("--interval", type=float, default=20.0); w.add_argument("--timeout", type=float, default=0.0)
    x = sub.add_parser("render-context", help="render the L1/L2 context treatment from AIEF")
    x.add_argument("--project", type=Path, required=True); x.add_argument("--factory", type=Path, required=True)
    x.add_argument("--repository", action="append", required=True); x.add_argument("--skill", default="implement-change")
    x.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            print(prepare(args.run, args.environment, args.output, args.run_id))
        elif args.command == "start":
            print(json.dumps(start(args.run_dir), indent=2))
        elif args.command == "continue":
            print(json.dumps(continue_run(args.run_dir, args.message), indent=2))
        elif args.command == "review":
            print(json.dumps(review(args.run_dir, args.agent), indent=2))
        elif args.command == "wait":
            print(json.dumps(wait(args.run_dir, args.interval, args.timeout), indent=2))
        elif args.command == "status":
            _observe(args.run_dir)
            print(yaml.safe_dump(load_yaml(args.run_dir / "run.yaml"), sort_keys=False, allow_unicode=True))
        elif args.command == "finish":
            print(yaml.safe_dump(finish(args.run_dir), sort_keys=False, allow_unicode=True))
        elif args.command == "render-context":
            print(render_context(args.project, args.factory, args.repository, args.skill, args.output))
    except LaunchError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
