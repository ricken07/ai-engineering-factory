from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json, re, yaml
from .project import runtime_root

def safe_task_id(task: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", task).strip("-.")
    if not value: raise ValueError("task id has no safe filesystem representation")
    return value

def statement_hash(statement: str, target: str) -> str:
    return sha256(json.dumps({"statement":statement,"target":target}, sort_keys=True).encode()).hexdigest()

def create_task_memory(project: Path, task: str) -> Path:
    root = runtime_root(project) / "tasks" / safe_task_id(task)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "state.yaml"
    if not path.exists():
        data = {"apiVersion":"aief.dev/v1alpha1","kind":"TaskMemory","metadata":{"id":safe_task_id(task)},"task":task,"status":"pending","repositories":[],"artifacts":{},"decisions":[],"openQuestions":[],"updatedAt":datetime.now(timezone.utc).isoformat()}
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path

def approve_candidate(candidate: dict[str, Any], approved_by: str) -> dict[str, Any]:
    if candidate.get("kind") != "MemoryCandidate" or candidate.get("status") != "proposed": raise ValueError("only a proposed MemoryCandidate can be approved")
    digest = statement_hash(candidate["statement"], candidate["target"])
    return {"apiVersion":"aief.dev/v1alpha1","kind":"KnowledgePromotion","metadata":{"id":f"promotion-{candidate['metadata']['id']}"},"candidate":candidate["metadata"]["id"],"target":candidate["target"],"approval":{"status":"approved","approvedBy":approved_by,"approvedAt":datetime.now(timezone.utc).isoformat()},"contentHash":digest,"status":"pending"}

def verify_approval(candidate: dict[str, Any], promotion: dict[str, Any]) -> bool:
    return promotion.get("approval",{}).get("status") == "approved" and promotion.get("candidate") == candidate.get("metadata",{}).get("id") and promotion.get("target") == candidate.get("target") and promotion.get("contentHash") == statement_hash(candidate.get("statement",""), candidate.get("target",""))
