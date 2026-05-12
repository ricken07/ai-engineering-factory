from pathlib import Path
from aief.adapters import INTENTS, adapter_mapping, select_workflow
ROOT = Path(__file__).parents[1]
def test_commands_and_language_select_same_workflow():
    assert select_workflow("/implement EGW-142") == select_workflow("implement EGW-142") == "implement-task"
def test_adapters_resolve_every_public_intent():
    for adapter in ("codex", "claude-code"):
        for workflow in INTENTS.values(): assert adapter_mapping(ROOT, adapter, workflow).is_file()
