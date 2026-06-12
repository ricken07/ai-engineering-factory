from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import yaml
from jsonschema import Draft202012Validator

from .compiler import compile_workflow
from .intake import TaskRegistry, create_request, normalize_task, resolve_intent
from .project import find_project, load_project
from .runtime import Execution
from .tracking import evaluate_tracking


class RuntimeService:
    """Deterministic boundary shared by all agent adapters."""

    def __init__(self, project: Path, factory: Path):
        self.project_root = find_project(project)
        self.project = load_project(self.project_root)
        self.factory = factory.resolve()
        manifest_path = self.factory / "factory.yaml"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Factory manifest not found: {manifest_path}")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        installed = manifest.get("metadata", {}).get("version")
        requested = self.project.get("factory", {}).get("version")
        if installed != requested:
            raise RuntimeError(f"project requires Factory {requested}, but {installed} was provided")

    def intake(self, text: str, agent: str | None = None) -> dict[str, Any]:
        request = create_request(text, agent)
        intent = resolve_intent(request)
        task = normalize_task(request, intent)
        task_path = TaskRegistry(self.project_root).save(task)
        intake_root = task_path.parent
        (intake_root / "request.yaml").write_text(yaml.safe_dump(request, sort_keys=False, allow_unicode=True), encoding="utf-8")
        (intake_root / "intent.yaml").write_text(yaml.safe_dump(intent, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return {"request": request, "intent": intent, "task": task, "path": str(task_path)}

    def start(self, text: str, agent: str | None = None) -> Execution:
        intake = self.intake(text, agent)
        workflow = compile_workflow(self.factory, intake["task"]["workflow"])
        return Execution.create(self.project_root, workflow, intake["task"]["metadata"]["id"], agent)

    def execution(self, execution_id: str) -> Execution:
        root = self.project_root / ".ai" / "runtime" / "executions" / execution_id
        if not root.is_dir():
            raise FileNotFoundError(f"execution not found: {execution_id}")
        return Execution.load(root)

    def complete_phase(self, execution_id: str, output: dict[str, Any]) -> Execution:
        execution = self.execution(execution_id)
        phase = execution.next_phase()
        if phase is None:
            raise RuntimeError("execution is already complete")
        compiled = compile_workflow(self.factory, execution.data["workflow"]["id"])
        definition = next((item for item in compiled["phases"] if item["id"] == phase["id"]), None)
        if definition is None:
            raise RuntimeError(f"phase {phase['id']} is absent from the pinned workflow")
        schema_path = self.factory / definition["outputSchema"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema).iter_errors(output), key=lambda item: list(item.path))
        if errors:
            details = "; ".join(f"{'.'.join(map(str, error.path)) or 'root'}: {error.message}" for error in errors)
            raise ValueError(f"invalid output for {definition['skill']}: {details}")
        execution.advance(output)
        return execution

    def reassess_tracking(self, task_id: str, impact: dict[str, Any]) -> dict[str, Any]:
        registry = TaskRegistry(self.project_root)
        task = registry.load(task_id)
        decision = evaluate_tracking(task, impact)
        task["tracking"] = {**task.get("tracking", {}), "level": decision.level}
        task.setdefault("classification", {})
        if impact.get("risk"): task["classification"]["risk"] = impact["risk"]
        if impact.get("changeTypes") is not None: task["classification"]["changeTypes"] = impact["changeTypes"]
        if impact.get("repositories") is not None: task.setdefault("scope", {})["repositories"] = impact["repositories"]
        registry.save(task)
        return {"task": task, "decision": decision.as_dict()}
