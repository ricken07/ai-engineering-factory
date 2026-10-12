from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import re
import uuid

from .knowledge import safe_task_id
from .timing import Clock, SystemClock, timestamp
from .project import runtime_root

EVENT_TYPES = {
    "request.created", "intent.resolved", "task.normalized", "workflow.started",
    "phase.started", "phase.completed", "phase.failed",
    "policy.evaluated", "policy.reclassified",
    "gate.requested", "gate.approved", "gate.rejected",
    "workspace.prepared", "workspace.blocked",
    "integration.resolved", "integration.failed",
    "execution.completed", "execution.failed", "execution.cancelled",
    "question.asked", "question.answered",
}

_SENSITIVE_KEYS = {
    "secret", "secrets", "token", "tokens", "password", "passwords",
    "apikey", "api_key", "authorization", "credential", "credentials",
    "privatekey", "private_key",
}
_CONTENT_KEYS = {"content", "prompt", "prompts", "body"}
_SECRET_PATTERNS = [
    re.compile(pattern) for pattern in (
        r"AKIA[0-9A-Z]{16}",
        r"gh[pousr]_[A-Za-z0-9]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]+",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    )
]


def _redact(value: Any, allow_content: bool) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if lowered in _SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            elif lowered in _CONTENT_KEYS and not allow_content:
                redacted[key] = "[OMITTED:opt-in required]"
            else:
                redacted[key] = _redact(item, allow_content)
        return redacted
    if isinstance(value, list):
        return [_redact(item, allow_content) for item in value]
    if isinstance(value, str):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                return "[REDACTED]"
        return value
    return value


def _export_opentelemetry(record: dict[str, Any]) -> None:
    """Best-effort, strictly optional export. Never raises, never required.

    Only attempted when explicitly enabled via AIEF_OBSERVABILITY_OTEL; a
    missing `opentelemetry` package or any exporter failure is swallowed so a
    normal Execution is never blocked by observability export.
    """
    if os.environ.get("AIEF_OBSERVABILITY_OTEL") not in {"1", "true", "True"}:
        return
    try:
        from opentelemetry import trace  # type: ignore
    except Exception:
        return
    try:
        tracer = trace.get_tracer("aief.runtime")
        with tracer.start_as_current_span(record["event"]["type"]) as span:
            span.set_attribute("aief.event.id", record["event"]["id"])
            span.set_attribute("aief.task.id", record["task"]["id"])
            if "execution" in record:
                span.set_attribute("aief.execution.id", record["execution"]["id"])
    except Exception:
        return


class TaskEventLog:
    """Append-only, agent-neutral structured audit trail for one Runtime Task.

    Local JSONL storage is the only required backend. OpenTelemetry export is
    an optional, disabled-by-default side effect of the same `append` call —
    it never replaces local storage and never blocks it.
    """

    def __init__(self, project_root: Path, task_id: str, *,
                 project_id: str | None = None, factory_version: str | None = None,
                 clock: Clock | None = None):
        self.task_id = task_id
        self.project_id = project_id or "local-project"
        self.factory_version = factory_version or "0.0.0"
        self.clock = clock or SystemClock()
        self.path = (
            runtime_root(project_root) / "tasks" /
            safe_task_id(task_id) / "events.jsonl"
        )

    def append(self, event_type: str, *, execution: str | None = None,
               payload: dict[str, Any] | None = None, allow_content: bool = False) -> dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown runtime event type: {event_type}")
        record: dict[str, Any] = {
            "event": {
                "id": f"event-{uuid.uuid4().hex[:12]}",
                "type": event_type,
                "timestamp": timestamp(self.clock),
            },
            "factory": {"version": self.factory_version},
            "project": {"id": self.project_id},
            "task": {"id": self.task_id},
        }
        if execution is not None:
            record["execution"] = {"id": execution}
        record["payload"] = _redact(payload or {}, allow_content)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        _export_opentelemetry(record)
        return record

    def read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
