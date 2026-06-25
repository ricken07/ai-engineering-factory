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
    assert main(["intake", "Corrige le bug DEMO-12", "--project", str(destination), "--factory", ".", "--json"]) == 0
    assert '"workflow": "fix-bug"' in capsys.readouterr().out
    assert main(["run", "/analyze DEMO-12", "--project", str(destination), "--factory", ".", "--agent", "codex"]) == 0
    assert "nextPhase: understand" in capsys.readouterr().out

def test_engineering_context_command(capsys):
    assert main(["engineering-context","egw-api","review-change","--project","examples/emmany","--factory",".","--json"]) == 0
    output = capsys.readouterr().out
    assert '"kind": "EffectiveEngineeringContext"' in output
    assert '"id": "organization-code-review"' in output

def test_task_tracking_status_command(tmp_path: Path, capsys):
    from aief.project import initialize
    from aief.service import RuntimeService
    project=tmp_path/"project"; initialize(Path("templates/project"),project); service=RuntimeService(project,Path("."))
    intake=service.intake("Corrige un petit bug"); identifier=intake["task"]["metadata"]["id"]
    service.reassess_tracking(identifier,{"risk":"low","repositories":["main"],"changeTypes":["refactoring"]})
    assert main(["task","tracking",identifier,"--project",str(project),"--factory",".","--json"]) == 0
    assert '"level": "optional"' in capsys.readouterr().out
