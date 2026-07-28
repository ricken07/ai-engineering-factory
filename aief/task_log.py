from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid

from .knowledge import safe_task_id


class TaskEventLog:
    """Append-only, agent-neutral audit trail for one Runtime Task."""

    def __init__(self, project_root: Path, task_id: str):
        self.task_id = task_id
        self.path = (
            project_root / ".ai" / "runtime" / "tasks" /
            safe_task_id(task_id) / "events.jsonl"
        )

    def append(self, event: str, *, execution: str | None = None,
               agent: str | None = None, phase: str | None = None,
               status: str | None = None, summary: str | None = None,
               data: dict[str, Any] | None = None) -> dict[str, Any]:
        record: dict[str, Any] = {
            "id": f"event-{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": self.task_id,
            "event": event,
        }
        for key, value in (
            ("execution", execution), ("agent", agent), ("phase", phase),
            ("status", status), ("summary", summary),
        ):
            if value is not None:
                record[key] = value
        if data:
            record["data"] = data
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
