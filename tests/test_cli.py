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
