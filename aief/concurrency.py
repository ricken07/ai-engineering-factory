from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
import hashlib
import json
import os

import yaml


class LeaseConflict(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionLease:
    """Filesystem lease acquired atomically and shared by all adapters."""

    def __init__(self, execution_root: Path):
        self.path = execution_root / "lease.yaml"

    def read(self) -> dict[str, Any] | None:
        return yaml.safe_load(self.path.read_text(encoding="utf-8")) if self.path.is_file() else None

    def acquire(self, owner: str, ttl_seconds: int = 300) -> dict[str, Any]:
        if not owner.strip(): raise ValueError("lease owner is required")
        current = self.read()
        now = _now()
        if current and datetime.fromisoformat(current["expiresAt"]) > now and current["owner"] != owner:
            raise LeaseConflict(f"execution is leased by {current['owner']} until {current['expiresAt']}")
        lease = {"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"ExecutionLease",
                 "metadata":{"id":f"lease-{self.path.parent.name}"},"execution":self.path.parent.name,
                 "owner":owner,"acquiredAt":now.isoformat(),"expiresAt":(now+timedelta(seconds=ttl_seconds)).isoformat(),"status":"active"}
        payload = yaml.safe_dump(lease, sort_keys=False).encode()
        if current:
            temporary = self.path.with_suffix(".tmp"); temporary.write_bytes(payload); temporary.replace(self.path)
        else:
            try:
                descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return self.acquire(owner, ttl_seconds)
            with os.fdopen(descriptor, "wb") as stream: stream.write(payload)
        return lease

    def assert_owner(self, owner: str) -> dict[str, Any]:
        lease = self.read()
        if not lease: raise LeaseConflict("execution has no active lease")
        if datetime.fromisoformat(lease["expiresAt"]) <= _now(): raise LeaseConflict("execution lease has expired")
        if lease["owner"] != owner: raise LeaseConflict(f"execution is leased by {lease['owner']}")
        return lease

    def renew(self, owner: str, ttl_seconds: int = 300) -> dict[str, Any]:
        self.assert_owner(owner); return self.acquire(owner, ttl_seconds)

    def release(self, owner: str) -> dict[str, Any]:
        lease = self.assert_owner(owner); lease["status"]="released"; lease["releasedAt"]=_now().isoformat()
        archive=self.path.parent/"lease-released.yaml"; archive.write_text(yaml.safe_dump(lease,sort_keys=False),encoding="utf-8")
        self.path.unlink(); return lease


class OperationJournal:
    def __init__(self, execution_root: Path):
        self.root=execution_root/"operations"; self.root.mkdir(exist_ok=True)

    @staticmethod
    def fingerprint(kind: str, payload: dict[str, Any]) -> str:
        encoded=json.dumps({"kind":kind,"payload":payload},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        return hashlib.sha256(encoded).hexdigest()

    def execute(self, operation_id: str, kind: str, payload: dict[str, Any], action: Callable[[], Any]) -> tuple[Any, bool]:
        if not operation_id or "/" in operation_id or ".." in operation_id: raise ValueError("invalid operationId")
        path=self.root/f"{operation_id}.yaml"; fingerprint=self.fingerprint(kind,payload)
        if path.is_file():
            existing=yaml.safe_load(path.read_text(encoding="utf-8"))
            if existing["fingerprint"] != fingerprint: raise IdempotencyConflict(f"operationId {operation_id} was already used with different input")
            if existing["status"] == "completed": return existing["result"], True
            if existing["status"] == "running": raise IdempotencyConflict(f"operationId {operation_id} is already running")
        pending={"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"RuntimeOperation","metadata":{"id":operation_id},
                 "execution":self.root.parent.name,"operationId":operation_id,"operationKind":kind,
                 "fingerprint":fingerprint,"status":"running","startedAt":_now().isoformat()}
        encoded=yaml.safe_dump(pending,sort_keys=False).encode()
        if not path.is_file():
            try: descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            except FileExistsError: return self.execute(operation_id,kind,payload,action)
            with os.fdopen(descriptor,"wb") as stream: stream.write(encoded)
        else:
            # A failed operation with the same fingerprint is an explicit retry.
            temporary=path.with_suffix(".tmp"); temporary.write_bytes(encoded); temporary.replace(path)
        try: result=action()
        except Exception as exc:
            pending.update({"status":"failed","error":{"type":type(exc).__name__,"message":str(exc)}}); self._replace(path,pending); raise
        serializable=result.data if hasattr(result,"data") else result
        pending.update({"status":"completed","completedAt":_now().isoformat(),"result":serializable})
        self._replace(path,pending)
        return serializable, False

    @staticmethod
    def _replace(path: Path, data: dict[str, Any]) -> None:
        temporary=path.with_suffix(".tmp"); temporary.write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True),encoding="utf-8"); temporary.replace(path)
