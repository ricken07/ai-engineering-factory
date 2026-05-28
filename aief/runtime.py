from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid, yaml
from .knowledge import create_task_memory

TERMINAL = {"completed", "failed", "skipped"}

class Execution:
    def __init__(self, root: Path, data: dict[str, Any]): self.root, self.data = root, data
    @classmethod
    def create(cls, project: Path, workflow: dict[str, Any], task: str) -> "Execution":
        identifier = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        root = project / ".ai" / "runtime" / "executions" / identifier
        root.mkdir(parents=True)
        task_memory = create_task_memory(project, task)
        phases = [{"id": p["id"], "skill": p["skill"], "status": "pending", **({"gate": p["gate"]} if "gate" in p else {}), "recovery": {"status":"active", "minimumAttempts":p.get("recovery",{}).get("minimumAttempts",10), "maximumAttempts":p.get("recovery",{}).get("maximumAttempts",15), "attempts":[]}} for p in workflow["phases"]]
        execution = cls(root, {"id": identifier, "workflow": workflow["metadata"]["id"], "task": task, "taskMemory": str(task_memory.relative_to(project)), "status": "pending", "phases": phases, "artifacts": []})
        execution.save(); return execution
    @classmethod
    def load(cls, root: Path) -> "Execution":
        return cls(root, yaml.safe_load((root / "execution.yaml").read_text(encoding="utf-8")))
    def save(self) -> None: (self.root / "execution.yaml").write_text(yaml.safe_dump(self.data, sort_keys=False), encoding="utf-8")
    def next_phase(self) -> dict[str, Any] | None:
        return next((p for p in self.data["phases"] if p["status"] not in TERMINAL), None)
    def advance(self, output: dict[str, Any] | None = None, approved: bool = False) -> str:
        phase = self.next_phase()
        if not phase: self.data["status"] = "completed"; self.save(); return "completed"
        if "gate" in phase and not approved:
            phase["status"] = "waiting-approval"; self.data["status"] = "waiting-approval"; self.save(); return "waiting-approval"
        phase["status"] = "completed"
        if output is not None:
            artifact = self.root / f"{phase['id']}.yaml"; artifact.write_text(yaml.safe_dump(output, sort_keys=False), encoding="utf-8"); self.data["artifacts"].append(artifact.name)
        self.data["status"] = "completed" if self.next_phase() is None else "running"; self.save(); return self.data["status"]
    def handoff(self) -> Path:
        path = self.root / "handoff.yaml"; path.write_text(yaml.safe_dump({"execution":self.data["id"],"workflow":self.data["workflow"],"task":self.data["task"],"status":self.data["status"],"nextPhase":(self.next_phase() or {}).get("id"),"artifacts":self.data["artifacts"]}, sort_keys=False), encoding="utf-8"); return path
    def record_attempt(self, error: str, hypothesis: str, action: str, outcome: str, evidence: list[str] | None = None) -> str:
        phase = self.next_phase()
        if not phase: raise RuntimeError("execution has no active phase")
        recovery = phase["recovery"]; attempts = recovery["attempts"]
        if attempts and attempts[-1]["hypothesis"] == hypothesis and attempts[-1]["action"] == action:
            raise ValueError("a recovery attempt must use a distinct hypothesis or action")
        if len(attempts) >= recovery["maximumAttempts"]: raise RuntimeError("recovery budget exhausted")
        attempts.append({"number":len(attempts)+1,"error":error,"hypothesis":hypothesis,"action":action,"outcome":outcome,"evidence":evidence or []})
        if outcome == "resolved": recovery["status"] = "resolved"
        elif len(attempts) >= recovery["maximumAttempts"]: recovery["status"] = "exhausted"
        self.save(); return recovery["status"]
    def ask_user(self, question: str, requires_authority: bool = False) -> None:
        phase = self.next_phase()
        if not phase: raise RuntimeError("execution has no active phase")
        recovery = phase["recovery"]
        if not requires_authority and len(recovery["attempts"]) < recovery["minimumAttempts"]:
            raise RuntimeError("minimum recovery attempts not reached")
        recovery.update({"status":"waiting-user", "question":question}); phase["status"] = "blocked"; self.data["status"] = "blocked"; self.save()
    def answer_user_question(self, answer: str) -> None:
        phase = self.next_phase()
        if not phase or phase["recovery"]["status"] != "waiting-user": raise RuntimeError("no pending user question")
        phase["recovery"].update({"answer":answer, "status":"active"}); phase["status"] = "pending"; self.data["status"] = "running"; self.save()
