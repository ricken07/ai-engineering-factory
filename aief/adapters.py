from __future__ import annotations
from pathlib import Path
import yaml
from .intake import INTENT_WORKFLOWS, create_request, resolve_intent

INTENTS = INTENT_WORKFLOWS

def select_workflow(text: str) -> str:
    return resolve_intent(create_request(text))["workflow"]

def adapter_mapping(factory: Path, adapter: str, workflow: str) -> Path:
    config = yaml.safe_load((factory / "adapters" / adapter / "adapter.yaml").read_text(encoding="utf-8"))
    relative = config["mappings"]["workflows"].get(workflow)
    if not relative: raise KeyError(f"adapter {adapter} does not support {workflow}")
    return factory / relative
