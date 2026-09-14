from __future__ import annotations
from pathlib import Path
from typing import Any
import uuid, yaml
from .knowledge import create_task_memory
from .yamlio import load_yaml
from .config import get_api_version
from .identity import actor_identity, trusted_session_actor
from .timing import Clock, SystemClock, observed_duration, timestamp, unavailable_metric

TERMINAL = {"completed", "failed", "skipped"}

class Execution:
    def __init__(self, root: Path, data: dict[str, Any], clock: Clock | None = None):
        self.root, self.data = root, data
        self.clock = clock or SystemClock()
        self._ensure_observability()

    def _ensure_observability(self) -> None:
        """Additive compatibility path for executions persisted before v1.16."""
        metrics = self.data.setdefault("metrics", {})
        metrics.setdefault("execution", {"startedAt": None, "completedAt": None, "durationMs": unavailable_metric()})
        metrics.setdefault("runtime", {"durationMs": unavailable_metric()})
        metrics.setdefault("validation", {"durationMs": unavailable_metric()})
        metrics.setdefault("gateWaiting", {"durationMs": unavailable_metric()})
        for identifier in ("agent", "review", "provider"):
            metrics.setdefault(identifier, {"durationMs": unavailable_metric()})
        metrics.setdefault("tokens", unavailable_metric())
        metrics.setdefault("cost", unavailable_metric())
        self.data.setdefault("timingState", {
            "executionStartedMonotonicNs": None,
            "runtimeAccumulatedNs": 0,
            "validationAccumulatedNs": 0,
            "gateWaitingAccumulatedNs": 0,
            "activeGateCount": 0,
            "gateWaitingStartedMonotonicNs": None,
        })
        self.data["timingState"].setdefault("activeGateCount", 0)
        self.data["timingState"].setdefault("gateWaitingStartedMonotonicNs", None)
        self.data.setdefault("actors", {})
        self.data.setdefault("enforcementPoints", [])
    @classmethod
    def create(cls, project: Path, factory: Path, workflow: dict[str, Any], task: str, agent: str | None = None,
               clock: Clock | None = None, agent_session: str | None = None) -> "Execution":
        clock = clock or SystemClock()
        identifier = f"{clock.now():%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        root = project / ".ai" / "runtime" / "executions" / identifier
        root.mkdir(parents=True)
        create_task_memory(project, task)
        phases = [{"id": p["id"], "skill": p["skill"], "status": "pending", "artifacts": [],
                   "actorType": "runtime" if p["skill"] == "validate-change" else "agent",
                   "timing": {"startedAt": None, "completedAt": None, "durationMs": unavailable_metric()},
                   **({"gate": p["gate"]} if "gate" in p else {}),
                   "recovery": {"status":"active", "minimumAttempts":p.get("recovery",{}).get("minimumAttempts",10), "maximumAttempts":p.get("recovery",{}).get("maximumAttempts",15), "attempts":[]}} for p in workflow["phases"]]
        project_file = project / ".ai" / "project.yaml"
        project_id = "local-project"
        if project_file.is_file():
            project_id = load_yaml(project_file).get("metadata", {}).get("id", project_id)
        metadata = workflow.get("metadata", {})
        workflow_id = workflow.get("id") or metadata.get("id")
        workflow_version = workflow.get("version") or metadata.get("version", "0.0.0")
        api_version = get_api_version(factory)
        started_at, started_ns = timestamp(clock), clock.monotonic_ns()
        data = {"apiVersion": api_version, "kind":"Execution", "metadata":{"id":identifier}, "project":project_id,
                "workflow":{"id":workflow_id,"version":workflow_version}, "task":task, "status":"pending", "phases":phases,
                "artifacts":[], "metrics": {
                    "execution":{"startedAt":started_at,"completedAt":None,"durationMs":unavailable_metric()},
                    "runtime":{"durationMs":unavailable_metric()}, "validation":{"durationMs":unavailable_metric()},
                    "gateWaiting":{"durationMs":unavailable_metric()},
                    "agent":{"durationMs":unavailable_metric()}, "review":{"durationMs":unavailable_metric()},
                    "provider":{"durationMs":unavailable_metric()}, "tokens":unavailable_metric(), "cost":unavailable_metric(),
                }, "timingState":{"executionStartedMonotonicNs":started_ns,"runtimeAccumulatedNs":0,
                                  "validationAccumulatedNs":0,"gateWaitingAccumulatedNs":0,
                                  "activeGateCount":0,"gateWaitingStartedMonotonicNs":None},
                "actors":{}, "enforcementPoints":[]}
        if agent:
            data["agent"] = {"adapter": agent, **({"session": agent_session} if agent_session else {})}
            # Keep the legacy role projection readable while actor assurance is
            # carried by the additive, provenance-aware actors contract.
            data["roles"] = {"producer": {"type": "agent", "identity": agent}}
            data["actors"]["producer"] = actor_identity(
                agent_session or agent, "agent", "adapter", "OBSERVED", adapter=agent,
                session=agent_session, execution=identifier,
            )
        execution = cls(root, data, clock)
        execution._start_phase(execution.next_phase())
        execution.save(); return execution
    @classmethod
    def load(cls, root: Path, clock: Clock | None = None) -> "Execution":
        return cls(root, load_yaml(root / "execution.yaml"), clock)
    def save(self) -> None:
        target=self.root/"execution.yaml"; temporary=self.root/"execution.yaml.tmp"
        temporary.write_text(yaml.safe_dump(self.data, sort_keys=False), encoding="utf-8"); temporary.replace(target)
    def next_phase(self) -> dict[str, Any] | None:
        return next((p for p in self.data["phases"] if p["status"] not in TERMINAL), None)

    def _start_phase(self, phase: dict[str, Any] | None) -> None:
        if not phase:
            return
        timing = phase.setdefault("timing", {"startedAt": None, "completedAt": None, "durationMs": unavailable_metric()})
        if timing.get("startedAt") is None:
            timing["startedAt"] = timestamp(self.clock)
            timing["startedMonotonicNs"] = self.clock.monotonic_ns()

    def _complete_phase_timing(self, phase: dict[str, Any]) -> None:
        timing = phase.setdefault("timing", {})
        if timing.get("completedAt") is not None:
            return
        timing["completedAt"] = timestamp(self.clock)
        started = timing.pop("startedMonotonicNs", None)
        timing["durationMs"] = observed_duration(self.clock.monotonic_ns() - started) if isinstance(started, int) else unavailable_metric()

    def _observe(self, metric: str, nanoseconds: int) -> None:
        if nanoseconds < 0:
            self.data["metrics"][metric]["durationMs"] = unavailable_metric()
            return
        state_key = f"{metric}AccumulatedNs"
        state = self.data["timingState"]
        state[state_key] = state.get(state_key, 0) + nanoseconds
        self.data["metrics"][metric]["durationMs"] = observed_duration(state[state_key])

    def record_runtime_duration(self, started_ns: int) -> None:
        self._observe("runtime", self.clock.monotonic_ns() - started_ns)

    def record_validation_duration(self, started_ns: int) -> None:
        elapsed = self.clock.monotonic_ns() - started_ns
        self._observe("validation", elapsed)

    def _start_gate_wait(self, gate: dict[str, Any]) -> None:
        timing = gate.setdefault("timing", {"requestedAt": None, "decidedAt": None, "durationMs": unavailable_metric()})
        if timing.get("requestedAt") is None:
            timing["requestedAt"] = timestamp(self.clock)
            timing["startedMonotonicNs"] = self.clock.monotonic_ns()
            state = self.data["timingState"]
            if state["activeGateCount"] == 0:
                state["gateWaitingStartedMonotonicNs"] = self.clock.monotonic_ns()
            state["activeGateCount"] += 1

    def _complete_gate_wait(self, gate: dict[str, Any]) -> None:
        timing = gate.setdefault("timing", {})
        if timing.get("decidedAt") is not None:
            return
        timing["decidedAt"] = timestamp(self.clock)
        started = timing.pop("startedMonotonicNs", None)
        if isinstance(started, int):
            elapsed = self.clock.monotonic_ns() - started
            timing["durationMs"] = observed_duration(elapsed)
            state = self.data["timingState"]
            state["activeGateCount"] = max(0, state["activeGateCount"] - 1)
            aggregate_started = state.get("gateWaitingStartedMonotonicNs")
            if state["activeGateCount"] == 0 and isinstance(aggregate_started, int):
                self._observe("gateWaiting", self.clock.monotonic_ns() - aggregate_started)
                state["gateWaitingStartedMonotonicNs"] = None
        else:
            timing["durationMs"] = unavailable_metric()

    def start_policy_gate(self, gate: dict[str, Any]) -> None:
        self._start_gate_wait(gate)

    def complete_policy_gate(self, gate: dict[str, Any]) -> None:
        self._complete_gate_wait(gate)

    def observe_actor(self, role: str, actor: dict[str, Any]) -> None:
        self.data.setdefault("actors", {})[role] = actor

    def _finish_execution(self) -> None:
        timing = self.data["metrics"]["execution"]
        if timing.get("completedAt") is not None:
            return
        timing["completedAt"] = timestamp(self.clock)
        started = self.data["timingState"].get("executionStartedMonotonicNs")
        timing["durationMs"] = observed_duration(self.clock.monotonic_ns() - started) if isinstance(started, int) else unavailable_metric()
    def _persist_output(self, phase: dict[str, Any], output: dict[str, Any]) -> None:
        artifact = self.root / f"{phase['id']}.yaml"
        artifact.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=True), encoding="utf-8")
        if artifact.name not in phase["artifacts"]: phase["artifacts"].append(artifact.name)
        if artifact.name not in self.data["artifacts"]: self.data["artifacts"].append(artifact.name)
    def advance(self, output: dict[str, Any] | None = None, approved: bool = False) -> str:
        runtime_started = self.clock.monotonic_ns()
        phase = self.next_phase()
        if not phase:
            self.data["status"] = "completed"; self._finish_execution(); self.record_runtime_duration(runtime_started); self.save(); return "completed"
        if approved and phase["status"] != "waiting-approval":
            raise RuntimeError("approval is only valid for a phase waiting for approval")
        if phase["status"] == "waiting-approval":
            if not approved:
                return "waiting-approval"
            if "gateTiming" in phase: self._complete_gate_wait(phase["gateTiming"])
            phase["status"] = "completed"
            self._complete_phase_timing(phase)
            self.data["status"] = "completed" if self.next_phase() is None else "running"
            self._start_phase(self.next_phase())
            if self.data["status"] == "completed": self._finish_execution()
            self.record_runtime_duration(runtime_started)
            self.save(); return self.data["status"]
        if output is not None:
            self._persist_output(phase, output)
        if "gate" in phase and not approved:
            phase["status"] = "waiting-approval"; self.data["status"] = "waiting-approval"
            phase["gateTiming"] = {"gate":phase["gate"].get("id", "phase-gate")}; self._start_gate_wait(phase["gateTiming"])
            self.record_runtime_duration(runtime_started); self.save(); return "waiting-approval"
        phase["status"] = "completed"
        self._complete_phase_timing(phase)
        self.data["status"] = "completed" if self.next_phase() is None else "running"
        self._start_phase(self.next_phase())
        if self.data["status"] == "completed": self._finish_execution()
        self.record_runtime_duration(runtime_started); self.save(); return self.data["status"]
    def fail_phase(self, output: dict[str, Any]) -> str:
        runtime_started = self.clock.monotonic_ns()
        phase = self.next_phase()
        if not phase: raise RuntimeError("execution has no active phase")
        self._persist_output(phase, output)
        phase["status"] = "failed"; self._complete_phase_timing(phase); self.data["status"] = "failed"
        self._finish_execution(); self.record_runtime_duration(runtime_started); self.save()
        return "failed"
    def cancel(self, reason: str) -> str:
        """Terminal transition to the `cancelled` status already recognized
        throughout the Runtime (readiness, service phase guards) but, until
        now, never reachable. Deliberately minimal: no retry semantics, no
        additional gating — completing the existing state machine rather
        than building a second one. Mirrors `block()`: only the Execution
        status is finalized, the active phase record is left untouched."""
        if self.data["status"] in {"completed", "failed", "cancelled"}:
            raise RuntimeError(f"terminal execution cannot be cancelled: {self.data['status']}")
        runtime_started = self.clock.monotonic_ns()
        self.data["status"] = "cancelled"; self.data["cancelledReason"] = reason; self._finish_execution()
        self.record_runtime_duration(runtime_started); self.save()
        return "cancelled"
    def block(self, reason: dict[str, str]) -> str:
        if self.data["status"] in {"completed","failed","cancelled"}: raise RuntimeError(f"terminal execution cannot be blocked: {self.data['status']}")
        self.data["status"]="blocked"; self.data["blockingReason"]=reason; self.save(); return "blocked"
    def resume(self, blocking_type: str) -> str:
        reason=self.data.get("blockingReason")
        if self.data["status"] != "blocked" or not reason or reason["type"] != blocking_type: raise RuntimeError(f"execution is not blocked by {blocking_type}")
        self.data.pop("blockingReason",None); self.data["status"]="running"; self.save(); return "running"
    def handoff(self, factory: Path) -> Path:
        next_phase = self.next_phase()
        api_version = get_api_version(factory)
        data = {"apiVersion": api_version,"kind":"Handoff","metadata":{"id":f"handoff-{self.data['metadata']['id']}"},"execution":self.data["metadata"]["id"],"task":self.data["task"],"status":self.data["status"],"summary":f"Execution {self.data['status']} for workflow {self.data['workflow']['id']}.","artifacts":self.data["artifacts"],"decisions":[],"constraints":[],"openQuestions":[],"nextActions":([f"Resume phase {next_phase['id']}"] if next_phase else [])}
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
