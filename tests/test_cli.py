from pathlib import Path
from aief.cli import main

def test_inspect_example(capsys):
    assert main(["inspect", "examples/emmany", "--json"]) == 0
    assert '"id": "emmany"' in capsys.readouterr().out

def test_doctor_example():
    assert main(["doctor", "examples/emmany"]) == 0

def test_init(tmp_path: Path):
    destination = tmp_path / "demo"
    assert main(["init", str(destination)]) == 0
    assert (destination / ".ai/project.yaml").is_file()
    assert (destination / ".ai/memory/patterns.md").is_file()
    assert (destination / ".ai/README.md").is_file()
    assert (destination / ".ai/mcp.env.example").is_file()
    assert (destination / ".ai/runtime/README.md").is_file()
    assert ".ai/runtime/" in (destination / ".gitignore").read_text()

def test_intake_and_run_commands(tmp_path: Path, capsys):
    destination = tmp_path / "demo"
    assert main(["init", str(destination)]) == 0
    capsys.readouterr()
    assert main(["intake", "Corrige le bug DEMO-12", "--project", str(destination), "--factory", ".", "--activation-confirmed", "--json"]) == 0
    assert '"workflow": "fix-bug"' in capsys.readouterr().out
    assert main(["run", "/analyze DEMO-12", "--project", str(destination), "--factory", ".", "--agent", "codex"]) == 0
    assert "nextPhase: understand" in capsys.readouterr().out


def test_activation_gate_native_command_and_unconfirmed_free_text(tmp_path: Path, capsys):
    from aief.intake import ActivationRequired

    destination = tmp_path / "demo"
    assert main(["init", str(destination)]) == 0
    capsys.readouterr()
    # Default `activation.mode: auto` — a native command always runs directly.
    assert main(["intake", "/fix DEMO-13", "--project", str(destination), "--factory", ".", "--json"]) == 0
    assert '"workflow": "fix-bug"' in capsys.readouterr().out
    # Free text is refused until the developer explicitly confirms it.
    import pytest
    with pytest.raises(ActivationRequired):
        main(["intake", "Corrige le bug DEMO-13", "--project", str(destination), "--factory", "."])
    assert main(["intake", "Corrige le bug DEMO-13", "--project", str(destination), "--factory", ".", "--activation-confirmed", "--json"]) == 0
    assert '"workflow": "fix-bug"' in capsys.readouterr().out


def test_activation_gate_manual_mode_blocks_free_text_but_not_native_commands(tmp_path: Path, capsys):
    import yaml
    from aief.intake import ActivationDeclined

    destination = tmp_path / "demo"
    assert main(["init", str(destination)]) == 0
    project_file = destination / ".ai/project.yaml"
    data = yaml.safe_load(project_file.read_text())
    data["activation"]["mode"] = "manual"
    project_file.write_text(yaml.safe_dump(data, sort_keys=False))
    capsys.readouterr()

    # A native command still activates the Factory, for this execution only.
    assert main(["intake", "/fix DEMO-14", "--project", str(destination), "--factory", ".", "--json"]) == 0
    assert '"workflow": "fix-bug"' in capsys.readouterr().out

    # Free text is never routed through the Factory, confirmed or not.
    import pytest
    with pytest.raises(ActivationDeclined):
        main(["intake", "Corrige le bug DEMO-14", "--project", str(destination), "--factory", ".", "--activation-confirmed"])


def test_run_adapter_contract_pins_intent_and_workflow(tmp_path: Path, capsys):
    destination = tmp_path / "demo"
    assert main(["init", str(destination)]) == 0
    capsys.readouterr()
    assert main([
        "run", "Feature 1.1 — Fixer les trois contrats cassés",
        "--project", str(destination), "--factory", ".",
        "--agent", "claude-code", "--intent", "implement",
        "--expect-workflow", "implement-task",
    ]) == 0
    output = capsys.readouterr().out
    assert "runtimeReceipt: created" in output
    assert "intent: implement" in output
    assert "mutating: true" in output
    assert "id: implement-task" in output
    assert "taskLog:" in output


def test_task_log_command(tmp_path: Path, capsys):
    destination = tmp_path / "demo"
    assert main(["init", str(destination)]) == 0
    capsys.readouterr()
    assert main(["run", "/analyze DEMO-42", "--project", str(destination), "--factory", "."]) == 0
    capsys.readouterr()
    assert main(["task", "log", "DEMO-42", "--project", str(destination), "--factory", ".", "--json"]) == 0
    output = capsys.readouterr().out
    assert '"type": "task.normalized"' in output
    assert '"type": "workflow.started"' in output


def test_task_inspect_accepts_explicit_factory_path(tmp_path: Path, capsys):
    destination = tmp_path / "demo"
    assert main(["init", str(destination)]) == 0
    capsys.readouterr()
    assert main(["run", "/analyze DEMO-42", "--project", str(destination), "--factory", "."]) == 0
    capsys.readouterr()
    assert main(["task", "inspect", "DEMO-42", "--project", str(destination), "--factory", ".", "--json"]) == 0
    assert '"id": "DEMO-42"' in capsys.readouterr().out

def test_engineering_context_command(capsys):
    assert main(["engineering-context","egw-api","review-change","--project","examples/emmany","--factory",".","--json"]) == 0
    output = capsys.readouterr().out
    assert '"kind": "EffectiveEngineeringContext"' in output
    assert '"id": "organization-code-review"' in output

def test_task_tracking_status_command(tmp_path: Path, capsys):
    from aief.project import initialize
    from aief.service import RuntimeService
    project=tmp_path/"project"; initialize(Path("templates/project"),project); service=RuntimeService(project,Path("."))
    intake=service.intake("Corrige un petit bug", confirmed=True); identifier=intake["task"]["metadata"]["id"]
    service.reassess_tracking(identifier,{"risk":"low","repositories":["main"],"changeTypes":["refactoring"]})
    assert main(["task","tracking",identifier,"--project",str(project),"--factory",".","--json"]) == 0
    assert '"level": "optional"' in capsys.readouterr().out
