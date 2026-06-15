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
    def create(cls, project: Path, workflow: dict[str, Any], task: str, agent: str | None = None) -> "Execution":
        identifier = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        root = project / ".ai" / "runtime" / "executions" / identifier
        root.mkdir(parents=True)
        create_task_memory(project, task)
        phases = [{"id": p["id"], "skill": p["skill"], "status": "pending", "artifacts": [], **({"gate": p["gate"]} if "gate" in p else {}), "recovery": {"status":"active", "minimumAttempts":p.get("recovery",{}).get("minimumAttempts",10), "maximumAttempts":p.get("recovery",{}).get("maximumAttempts",15), "attempts":[]}} for p in workflow["phases"]]
        project_file = project / ".ai" / "project.yaml"
        project_id = "local-project"
        if project_file.is_file():
            project_id = yaml.safe_load(project_file.read_text(encoding="utf-8")).get("metadata", {}).get("id", project_id)
        metadata = workflow.get("metadata", {})
        workflow_id = workflow.get("id") or metadata.get("id")
        workflow_version = workflow.get("version") or metadata.get("version", "0.0.0")
        data = {"apiVersion":"factory.gaddigital.io/v1alpha1", "kind":"Execution", "metadata":{"id":identifier}, "project":project_id, "workflow":{"id":workflow_id,"version":workflow_version}, "task":task, "status":"pending", "phases":phases, "artifacts":[]}
        if agent: data["agent"] = {"adapter": agent}
        execution = cls(root, data)
        execution.save(); return execution
    @classmethod
    def load(cls, root: Path) -> "Execution":
        return cls(root, yaml.safe_load((root / "execution.yaml").read_text(encoding="utf-8")))
    def save(self) -> None: (self.root / "execution.yaml").write_text(yaml.safe_dump(self.data, sort_keys=False), encoding="utf-8")
    def next_phase(self) -> dict[str, Any] | None:
        return next((p for p in self.data["phases"] if p["status"] not in TERMINAL), None)
    def _persist_output(self, phase: dict[str, Any], output: dict[str, Any]) -> None:
        artifact = self.root / f"{phase['id']}.yaml"
        artifact.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=True), encoding="utf-8")
        if artifact.name not in phase["artifacts"]: phase["artifacts"].append(artifact.name)
        if artifact.name not in self.data["artifacts"]: self.data["artifacts"].append(artifact.name)
    def advance(self, output: dict[str, Any] | None = None, approved: bool = False) -> str:
        phase = self.next_phase()
        if not phase: self.data["status"] = "completed"; self.save(); return "completed"
        if approved and phase["status"] != "waiting-approval":
            raise RuntimeError("approval is only valid for a phase waiting for approval")
        if phase["status"] == "waiting-approval":
            if not approved:
                return "waiting-approval"
            phase["status"] = "completed"
            self.data["status"] = "completed" if self.next_phase() is None else "running"
            self.save(); return self.data["status"]
        if output is not None:
            self._persist_output(phase, output)
        if "gate" in phase and not approved:
            phase["status"] = "waiting-approval"; self.data["status"] = "waiting-approval"; self.save(); return "waiting-approval"
        phase["status"] = "completed"
        self.data["status"] = "completed" if self.next_phase() is None else "running"; self.save(); return self.data["status"]
    def fail_phase(self, output: dict[str, Any]) -> str:
        phase = self.next_phase()
        if not phase: raise RuntimeError("execution has no active phase")
        self._persist_output(phase, output)
        phase["status"] = "failed"; self.data["status"] = "failed"; self.save()
        return "failed"
    def handoff(self) -> Path:
        next_phase = self.next_phase()
        data = {"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"Handoff","metadata":{"id":f"handoff-{self.data['metadata']['id']}"},"execution":self.data["metadata"]["id"],"task":self.data["task"],"status":self.data["status"],"summary":f"Execution {self.data['status']} for workflow {self.data['workflow']['id']}.","artifacts":self.data["artifacts"],"decisions":[],"constraints":[],"openQuestions":[],"nextActions":([f"Resume phase {next_phase['id']}"] if next_phase else [])}
        path = self.root / "handoff.yaml"; path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"); return path
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
