from __future__ import annotations
from pathlib import Path
import re, yaml

INTENTS = {"analyze":"analyze-task","implement":"implement-task","fix":"fix-bug","refactor":"refactor-code","test":"add-tests","review":"review-change","document":"update-documentation","promote":"promote-knowledge"}

def select_workflow(text: str) -> str:
    normalized = text.strip().lower()
    command = re.match(r"/?([a-z-]+)", normalized)
    if command and command.group(1) in INTENTS: return INTENTS[command.group(1)]
    for intent, workflow in INTENTS.items():
        if intent in normalized: return workflow
    raise ValueError("unable to select a Factory workflow")

def adapter_mapping(factory: Path, adapter: str, workflow: str) -> Path:
    config = yaml.safe_load((factory / "adapters" / adapter / "adapter.yaml").read_text(encoding="utf-8"))
    relative = config["mappings"]["workflows"].get(workflow)
    if not relative: raise KeyError(f"adapter {adapter} does not support {workflow}")
    return factory / relative
