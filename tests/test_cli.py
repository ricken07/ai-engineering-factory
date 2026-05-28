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
    assert (destination / ".ai/runtime/README.md").is_file()
    assert ".ai/runtime/" in (destination / ".gitignore").read_text()
