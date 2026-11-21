"""Experiment launcher (tools/experiment): conditions, isolation and run records, with fake agents."""
import importlib.util
import json
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("aief_experiment", ROOT / "tools" / "experiment" / "aief_experiment.py")
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
if sys.argv[1:] == ["--version"]:
    print("9.9.9 (Fake Claude)"); sys.exit(0)
if os.environ.get("FAKE_AGENT_SECONDS"):
    import time; time.sleep(float(os.environ["FAKE_AGENT_SECONDS"]))
Path("agent-note.txt").write_text(json.dumps({"argv": sys.argv[1:], "home": os.environ.get("HOME"),
    "factory": os.environ.get("AI_FACTORY_HOME"), "files": sorted(p.name for p in Path(".").iterdir())}))
if "/fix" in sys.argv[2]:
    root = Path(".ai/runtime/executions/exec-1"); root.mkdir(parents=True, exist_ok=True)
    (root / "execution.yaml").write_text("metadata: {id: exec-1}\\nstatus: waiting-approval\\nphases: [{id: planning, status: waiting-approval}]\\n")
print(json.dumps({"session_id": "claude-session-1", "is_error": False, "result": "done"}))
"""

FAKE_CODEX = """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
if sys.argv[1:] == ["--version"]:
    print("fake-codex 9.9.9"); sys.exit(0)
out = sys.argv[sys.argv.index("-o") + 1]
Path(out).write_text("done")
if os.environ.get("FAKE_AGENT_SECONDS"):
    import time; time.sleep(float(os.environ["FAKE_AGENT_SECONDS"]))
Path("agent-note.txt").write_text(json.dumps({"argv": sys.argv[1:], "home": os.environ.get("HOME"),
    "codexHome": os.environ.get("CODEX_HOME")}))
print(json.dumps({"type": "thread.started", "thread_id": "codex-thread-1"}))
"""


@pytest.fixture
def campaign(tmp_path: Path):
    source = tmp_path / "source"; source.mkdir()
    (source / "app.txt").write_text("one\n"); (source / "AGENTS.md").write_text("project rules\n")
    (source / ".ai").mkdir(); (source / ".ai" / "project.yaml").write_text("metadata: {id: p}\n")
    (source / ".claude").mkdir(); (source / ".claude" / "settings.json").write_text("{}\n")
    git(source, "init", "-q", "-b", "main"); git(source, "add", "-A"); git(source, "commit", "-qm", "init")
    start = git(source, "rev-parse", "HEAD")
    (source / "app.txt").write_text("later\n"); git(source, "commit", "-qam", "later")
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    for name, body in (("fake-claude", FAKE_CLAUDE), ("fake-codex", FAKE_CODEX)):
        (bin_dir / name).write_text(body); (bin_dir / name).chmod(0o755)
    auth = tmp_path / "auth.json"; auth.write_text("{}")
    treatment = tmp_path / "treatment"; treatment.mkdir()
    (treatment / "context.md").write_text("# Context\n")
    (treatment / "plan.md").write_text("# Plan\n")
    (treatment / "verification.yaml").write_text("acceptanceCriteria: [{id: AC-1, statement: s}]\n")
    environment = tmp_path / "environment.yaml"
    environment.write_text(yaml.safe_dump({"id": "test-env", "factory": str(tmp_path / "factory"),
        "isolation": {"homeLinks": [".gitconfig"]},
        "agents": {"claude-code": {"command": str(bin_dir / "fake-claude"),
                                   "plain": {"isolatedHome": False, "args": ["--disable-slash-commands"]},
                                   "governed": {"isolatedHome": False, "args": []}},
                   "codex": {"command": str(bin_dir / "fake-codex"), "authFile": str(auth),
                             "plain": {"isolatedHome": True, "args": ["--ignore-user-config"]},
                             "governed": {"isolatedHome": False, "args": []}}}}))

    def descriptor(condition: str, agent: str = "claude-code", **extra) -> Path:
        path = tmp_path / f"run-{condition}-{agent}.yaml"
        data = {"task": {"id": "T-1", "intent": "fix", "repository": str(source), "startingCommit": start,
                         "request": "Change one to two."},
                "condition": condition, "agent": {"name": agent}, "repeatIndex": 1,
                "treatment": {"context": str(treatment / "context.md"), "plan": str(treatment / "plan.md"),
                              "verification": str(treatment / "verification.yaml")}}
        data.update(extra)
        path.write_text(yaml.safe_dump(data))
        return path
    return {"descriptor": descriptor, "environment": environment, "output": tmp_path / "runs", "start": start,
            "treatment": treatment}


def note(run_dir: Path) -> dict:
    return json.loads((run_dir / "repo" / "agent-note.txt").read_text())


def test_l0_runs_at_the_starting_commit_without_project_or_agent_configuration(campaign):
    run_dir = launcher.prepare(campaign["descriptor"]("L0"), campaign["environment"], campaign["output"])
    record = yaml.safe_load((run_dir / "run.yaml").read_text())
    assert record["task"]["startingCommit"] == campaign["start"] and record["status"] == "prepared"
    assert sorted(record["setup"]["removed"]) == [".ai", ".claude", "AGENTS.md"]
    repo = run_dir / "repo"
    assert (repo / "app.txt").read_text() == "one\n" and not (repo / ".ai").exists() and not (repo / "AGENTS.md").exists()
    step = launcher.start(run_dir)
    assert step["exitCode"] == 0 and step["sessionId"] == "claude-session-1"
    assert (run_dir / step["prompt"]).read_text() == "Change one to two."
    assert "--disable-slash-commands" in note(run_dir)["argv"]
    assert record["agent"]["version"] == "9.9.9 (Fake Claude)"


def test_l1_gives_the_frozen_context_and_l2_the_frozen_plan_and_verification(campaign):
    l1 = launcher.prepare(campaign["descriptor"]("L1"), campaign["environment"], campaign["output"])
    assert (l1 / "repo" / "AGENTS.md").read_text() == "# Context\n"
    assert (l1 / "repo" / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    l2 = launcher.prepare(campaign["descriptor"]("L2"), campaign["environment"], campaign["output"])
    for name in ("plan.md", "verification.yaml"):
        assert (l2 / "repo" / ".experiment" / name).read_bytes() == (campaign["treatment"] / name).read_bytes()
    step = launcher.start(l2)
    prompt = (l2 / step["prompt"]).read_text()
    assert prompt.startswith("Change one to two.") and ".experiment/plan.md" in prompt and ".experiment/verification.yaml" in prompt


def test_frozen_hashes_are_enforced(campaign):
    path = campaign["descriptor"]("L2", treatment={"context": str(campaign["treatment"] / "context.md"),
        "plan": str(campaign["treatment"] / "plan.md"), "verification": str(campaign["treatment"] / "verification.yaml"),
        "sha256": {"plan": "0" * 64}})
    with pytest.raises(launcher.LaunchError, match="not the frozen"):
        launcher.prepare(path, campaign["environment"], campaign["output"])


def test_codex_plain_runs_in_an_isolated_home(campaign):
    run_dir = launcher.prepare(campaign["descriptor"]("L0", "codex"), campaign["environment"], campaign["output"])
    step = launcher.start(run_dir)
    seen = note(run_dir)
    assert seen["home"] == str(run_dir / "home") and seen["codexHome"] == str(run_dir / "home" / ".codex")
    assert (run_dir / "home" / ".codex" / "auth.json").is_symlink()
    assert step["sessionId"] == "codex-thread-1" and "--ignore-user-config" in seen["argv"]


def frozen_l3(campaign) -> Path:
    import hashlib
    files = {key: campaign["treatment"] / name for key, name in (("plan", "plan.md"), ("verification", "verification.yaml"))}
    return campaign["descriptor"]("L3", treatment={**{key: str(path) for key, path in files.items()},
        "sha256": {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in files.items()}})


def test_l3_needs_the_frozen_hashes_of_the_bound_files(campaign):
    with pytest.raises(launcher.LaunchError, match="frozen SHA-256 of treatment.plan and treatment.verification"):
        launcher.prepare(campaign["descriptor"]("L3"), campaign["environment"], campaign["output"])


def test_l3_runs_the_governed_command_with_the_research_metadata_and_never_decides(campaign):
    run_dir = launcher.prepare(frozen_l3(campaign), campaign["environment"], campaign["output"])
    assert (run_dir / "repo" / ".ai" / "project.yaml").is_file()  # the governed project keeps its configuration
    step = launcher.start(run_dir)
    prompt = (run_dir / step["prompt"]).read_text()
    for flag in ("--experiment-condition L3", "--repeat-index 1", "--environment-identifier test-env",
                 "--bound-plan", "--expect-plan-sha256", "--expect-verification-sha256"):
        assert flag in prompt
    assert prompt.startswith("/fix Change one to two.")
    plan_hash = yaml.safe_load(frozen_l3(campaign).read_text())["treatment"]["sha256"]["plan"]
    assert f"--expect-plan-sha256 {plan_hash}" in prompt
    assert note(run_dir)["factory"] == str(campaign["output"].parent / "factory")
    state = launcher.wait(run_dir, interval=0.01, timeout=0.05)
    assert state["executionId"] == "exec-1" and state["status"] == "waiting-approval"
    review = launcher.review(run_dir, "codex")
    assert review["role"] == "reviewer" and review["agent"] == "codex"
    assert "Never approve, reject or waive" in (run_dir / review["prompt"]).read_text()


def test_finish_records_the_change_without_touching_the_index(campaign):
    run_dir = launcher.prepare(campaign["descriptor"]("L0"), campaign["environment"], campaign["output"])
    launcher.start(run_dir)
    repo = run_dir / "repo"
    (repo / "app.txt").write_text("two\n")
    record = launcher.finish(run_dir)
    patch = (run_dir / "final" / "workspace.patch").read_text()
    assert "+two" in patch and "agent-note.txt" in patch
    assert record["status"] == "finished" and record["final"]["workspacePatchSha256"]
    assert git(repo, "diff", "--cached", "--name-only") == ""


FAKE_AIEF = """#!/usr/bin/env python3
import sys
from pathlib import Path
# gate-check applies the passed deadline: the integration of the completed execution expires.
if sys.argv[1:3] == ["execution", "gate-check"]:
    path = Path(".ai/runtime/executions/exec-1/execution.yaml")
    path.write_text(path.read_text().replace("integration: {status: awaiting-approval", "integration: {status: expired"))
    Path("gate-checks.txt").open("a").write("checked\\n")
"""


def test_wait_goes_through_the_runtime_so_an_undecided_gate_expires(campaign, tmp_path, monkeypatch):
    bin_dir = tmp_path / "aief-bin"; bin_dir.mkdir()
    (bin_dir / "aief").write_text(FAKE_AIEF); (bin_dir / "aief").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{__import__('os').environ['PATH']}")
    run_dir = launcher.prepare(frozen_l3(campaign), campaign["environment"], campaign["output"])
    launcher.start(run_dir)
    execution = run_dir / "repo" / ".ai" / "runtime" / "executions" / "exec-1" / "execution.yaml"
    execution.write_text("metadata: {id: exec-1}\nstatus: completed\nphases: []\n"
                         "integration: {status: awaiting-approval, gate: before-merge}\n")
    state = launcher.wait(run_dir, interval=0.01, timeout=5)
    assert state["status"] == "completed" and state["integration"] == "expired"
    assert (run_dir / "repo" / "gate-checks.txt").read_text() == "checked\n"


def test_active_budget_counts_agent_steps_only_and_stops_at_the_limit(campaign, monkeypatch):
    environment = yaml.safe_load(campaign["environment"].read_text())
    environment["activeBudgetMinutes"] = 0.05  # 3 seconds
    campaign["environment"].write_text(yaml.safe_dump(environment))
    run_dir = launcher.prepare(campaign["descriptor"]("L0"), campaign["environment"], campaign["output"])
    assert yaml.safe_load((run_dir / "run.yaml").read_text())["activeBudgetSeconds"] == 3.0
    monkeypatch.setenv("FAKE_AGENT_SECONDS", "1")
    first = launcher.start(run_dir)
    record = yaml.safe_load((run_dir / "run.yaml").read_text())
    assert first["exitCode"] == 0 and 1 <= record["activeSeconds"] < 3 and not record.get("resourceLimitReached")
    # Time spent between steps (a human gate holding the run) is not active time.
    import time; time.sleep(1.5)
    assert launcher._remaining_budget(yaml.safe_load((run_dir / "run.yaml").read_text())) > 0.5
    monkeypatch.setenv("FAKE_AGENT_SECONDS", "10")
    second = launcher._invoke(run_dir, "producer", "continue", "go on", session=first["sessionId"])
    record = yaml.safe_load((run_dir / "run.yaml").read_text())
    assert second["resourceLimitReached"] is True and second["exitCode"] is None and second["durationSeconds"] < 5
    assert record["resourceLimitReached"] is True and record["status"] == "resource-limit-reached"
    with pytest.raises(launcher.LaunchError, match="RESOURCE_LIMIT_REACHED"):
        launcher._invoke(run_dir, "producer", "continue", "again")
