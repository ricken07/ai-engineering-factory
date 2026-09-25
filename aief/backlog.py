from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable
import re
import yaml

from .config import get_api_version
from .knowledge import safe_task_id
from .provider_runtime import ProviderResolutionError, resolve_task_provider
from .validation import assert_schema
from .yamlio import load_yaml
from .project import runtime_root


DEFAULT_CONFIG = {
    "granularity": "task",
    "hierarchyLevels": ["epic", "feature", "task", "bug"],
    "groupBy": "none",
    "labelingRules": {"defaultLabels": []},
    "duplicatePolicy": "always-review",
    "dependencyInference": "explicit-only",
    "allowedSourceExtensions": [".md", ".yaml", ".yml", ".feature"],
}


def _import_id(source: str, provider: str) -> str:
    digest = sha256(f"{source}::{provider}".encode()).hexdigest()[:8]
    return f"import-{safe_task_id(Path(source).name or 'source')}-{digest}"


def _resolve_config(factory: Path, config_path: str | None) -> dict[str, Any]:
    if config_path:
        supplied = load_yaml(Path(config_path))
        if supplied.get("kind") != "BacklogImportConfig":
            raise ValueError("config document must have kind: BacklogImportConfig")
        assert_schema(factory, "backlog-import-config.schema.json", supplied)
    else:
        supplied = {"apiVersion": get_api_version(factory), "kind": "BacklogImportConfig", "metadata": {"id": "default"}}
    overrides = {key: value for key, value in supplied.items() if key not in {"apiVersion", "kind", "metadata"}}
    config = {**supplied, **{**DEFAULT_CONFIG, **overrides}}
    assert_schema(factory, "backlog-import-config.schema.json", config)
    return config


def _discover_sources(source: Path, extensions: list[str]) -> list[str]:
    if not source.is_dir():
        raise FileNotFoundError(f"backlog import source is not a directory: {source}")
    allowed = set(extensions)
    files = sorted(str(path.relative_to(source)) for path in source.rglob("*") if path.is_file() and path.suffix in allowed)
    if not files:
        raise ValueError(f"no file with an allowed extension ({', '.join(sorted(allowed))}) was found under {source}")
    return files


def _topological_order(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["candidateId"]: item for item in candidates}
    state: dict[str, str] = {}
    ordered: list[dict[str, Any]] = []

    def visit(identifier: str, chain: tuple[str, ...]) -> None:
        if state.get(identifier) == "done":
            return
        if state.get(identifier) == "visiting":
            raise ValueError(f"dependency cycle detected among backlog candidates: {' -> '.join(chain + (identifier,))}")
        state[identifier] = "visiting"
        proposal = by_id[identifier]["proposal"]
        references = ([proposal["parent"]] if proposal.get("parent") else []) + list(proposal.get("dependsOn", []))
        for reference in references:
            visit(reference, chain + (identifier,))
        state[identifier] = "done"
        ordered.append(by_id[identifier])

    for item in candidates:
        visit(item["candidateId"], ())
    return ordered


class BacklogImportManager:
    def __init__(self, project_root: Path, factory: Path, project: dict[str, Any], environment: dict[str, str] | None = None):
        self.project_root, self.factory, self.project, self.environment = project_root, factory, project, environment

    def _root(self, import_id: str) -> Path:
        root = runtime_root(self.project_root, self.project) / "backlog-imports" / safe_task_id(import_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _write(self, import_id: str, name: str, data: dict[str, Any]) -> Path:
        path = self._root(import_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return path

    def _read(self, import_id: str, name: str) -> dict[str, Any]:
        path = self._root(import_id) / name
        if not path.is_file():
            raise FileNotFoundError(f"backlog import artifact not found: {name}")
        return load_yaml(path)

    def start(self, source: str, provider: str, config_path: str | None = None) -> dict[str, Any]:
        import_id = _import_id(source, provider)
        plan_path = self._root(import_id) / "plan.yaml"
        if plan_path.is_file():
            plan = load_yaml(plan_path)
            return {"importId": import_id, "plan": plan, "sourceFiles": plan.get("sourceFiles", [])}
        config = _resolve_config(self.factory, config_path)
        source_path = Path(source)
        resolved_source = source_path if source_path.is_absolute() else (self.project_root / source_path)
        files = _discover_sources(resolved_source, config["allowedSourceExtensions"])
        plan = {
            "apiVersion": get_api_version(self.factory), "kind": "BacklogImportPlan", "metadata": {"id": import_id},
            "source": source, "provider": provider, "config": config, "status": "discovering",
            "openQuestions": [], "sourceFiles": files, "candidates": [],
        }
        assert_schema(self.factory, "backlog-import-plan.schema.json", plan)
        self._write(import_id, "plan.yaml", plan)
        return {"importId": import_id, "plan": plan, "sourceFiles": files}

    def complete_draft(self, import_id: str, candidates: list[dict[str, Any]], open_questions: list[str] | None = None) -> dict[str, Any]:
        plan = self._read(import_id, "plan.yaml")
        if plan["status"] != "discovering":
            raise RuntimeError(f"backlog import is not awaiting a draft: {plan['status']}")
        if not candidates:
            raise ValueError("at least one candidate is required")
        seen: set[str] = set()
        records = []
        for proposal in candidates:
            if proposal.get("sourceImport") != import_id:
                raise ValueError("candidate proposal must set sourceImport to the import id")
            assert_schema(self.factory, "external-task-proposal.schema.json", proposal)
            candidate_id = proposal["metadata"]["id"]
            if candidate_id in seen:
                raise ValueError(f"duplicate candidate id: {candidate_id}")
            seen.add(candidate_id)
            records.append({"candidateId": candidate_id, "proposal": proposal, "duplicateMatches": [], "decision": "create"})
        for record in records:
            proposal = record["proposal"]
            references = ([proposal["parent"]] if proposal.get("parent") else []) + list(proposal.get("dependsOn", []))
            unknown = [reference for reference in references if reference not in seen]
            if unknown:
                raise ValueError(f"candidate {record['candidateId']} references unknown parent/dependency: {', '.join(unknown)}")
        plan["candidates"] = records
        plan["openQuestions"] = list(open_questions or [])
        plan["status"] = "drafted"
        assert_schema(self.factory, "backlog-import-plan.schema.json", plan)
        self._write(import_id, "plan.yaml", plan)
        queries = {record["candidateId"]: self._build_query(record["proposal"]) for record in records}
        return {"plan": plan, "queries": queries}

    def complete_duplicate_search(self, import_id: str, matches_by_candidate: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        plan = self._read(import_id, "plan.yaml")
        if plan["status"] not in {"drafted", "duplicate-assessed"}:
            raise RuntimeError(f"backlog import is not awaiting duplicate search results: {plan['status']}")
        known = {item["candidateId"] for item in plan["candidates"]}
        unknown = sorted(set(matches_by_candidate) - known)
        if unknown:
            raise ValueError(f"duplicate search results reference unknown candidates: {', '.join(unknown)}")
        for candidate in plan["candidates"]:
            matches = matches_by_candidate.get(candidate["candidateId"], [])
            candidate["duplicateMatches"] = matches
            if candidate["decision"] == "skip":
                continue
            high_confidence_link = next((m for m in matches if m.get("recommendation") == "link-existing" and m.get("confidence") == "high"), None)
            auto_link = plan["config"]["duplicatePolicy"] == "auto-link-high-confidence" and high_confidence_link
            candidate["decision"] = "link-existing" if auto_link else "create"
        plan["status"] = "duplicate-assessed"
        assert_schema(self.factory, "backlog-import-plan.schema.json", plan)
        self._write(import_id, "plan.yaml", plan)
        return plan

    def preview(self, import_id: str) -> dict[str, Any]:
        plan = self._read(import_id, "plan.yaml")
        candidates = plan["candidates"]
        counts_by_type = Counter(item["proposal"].get("type", "task") for item in candidates)
        counts_by_decision = Counter(item["decision"] for item in candidates)
        children: dict[str | None, list[str]] = defaultdict(list)
        roots = []
        for item in candidates:
            parent = item["proposal"].get("parent")
            (children[parent].append(item["candidateId"]) if parent else roots.append(item["candidateId"]))

        def render(identifier: str, depth: int) -> list[str]:
            item = next(candidate for candidate in candidates if candidate["candidateId"] == identifier)
            reference = f" -> {item['externalReference']}" if item.get("externalReference") else ""
            line = f"{'  ' * depth}- [{item['proposal'].get('type', 'task')}] {item['proposal']['title']} ({item['decision']}{reference})"
            return [line] + [entry for child in children.get(identifier, []) for entry in render(child, depth + 1)]

        hierarchy = [line for identifier in roots for line in render(identifier, 0)]
        return {
            "importId": import_id, "status": plan["status"], "countsByType": dict(counts_by_type),
            "countsByDecision": dict(counts_by_decision), "openQuestions": plan.get("openQuestions", []), "hierarchy": hierarchy,
        }

    def _resolve_provider(self, import_id: str, agent: str | None = None) -> dict[str, Any]:
        plan = self._read(import_id, "plan.yaml")
        resolution = resolve_task_provider(self.factory, self.project_root, self.project, ["create-task", "link-task"], agent, self.environment)
        if resolution["provider"]["id"] != plan["provider"]:
            raise ProviderResolutionError("PROVIDER_MISMATCH", f"project is bound to task-provider '{resolution['provider']['id']}', but import {import_id} requested '{plan['provider']}'")
        return resolution

    def _operation(self, import_id: str, candidate_id: str, operation: str, input_data: dict[str, Any], approval_required: bool, agent: str | None = None, suffix: str = "") -> dict[str, Any]:
        operation_id = f"{operation}-{safe_task_id(candidate_id)}{suffix}"
        relative = f"operations/{operation_id}.yaml"
        path = self._root(import_id) / relative
        if path.is_file():
            return load_yaml(path)
        resolution = self._resolve_provider(import_id, agent)
        provider = resolution["provider"]["id"]
        status = "waiting-approval" if approval_required else "pending"
        data = {
            "apiVersion": get_api_version(self.factory), "kind": "ExternalOperation", "metadata": {"id": operation_id},
            "task": f"{import_id}:{candidate_id}", "provider": provider, "capability": "task-provider", "operation": operation,
            "status": status, "approval": {"required": approval_required, "status": "pending" if approval_required else "not-required"},
            "input": {**input_data, "operationId": operation_id},
        }
        assert_schema(self.factory, "external-operation.schema.json", data)
        self._write(import_id, relative, data)
        return data

    def apply(self, import_id: str, approved: bool = False, agent: str | None = None) -> dict[str, Any]:
        plan = self._read(import_id, "plan.yaml")
        if plan["status"] not in {"duplicate-assessed", "applying", "applied"}:
            raise RuntimeError(f"duplicate assessment must complete before apply: {plan['status']}")
        ordered = _topological_order(plan["candidates"])
        autonomy = self.project.get("autonomy", {}).get("default", "L0")
        approval_required = int(autonomy[1:]) < 3
        operations, blocked = [], []
        plan["status"] = "applying"
        by_id = {item["candidateId"]: item for item in plan["candidates"]}
        for candidate in ordered:
            if candidate["decision"] == "skip" or candidate.get("externalReference"):
                continue
            parent_id = candidate["proposal"].get("parent")
            parent_reference = None
            if parent_id:
                parent = by_id[parent_id]
                parent_reference = self._known_reference(parent)
                if parent_reference is None and parent["decision"] != "skip":
                    blocked.append(candidate["candidateId"])
                    continue
            if candidate["decision"] == "link-existing":
                match = next((m for m in candidate.get("duplicateMatches", []) if m.get("recommendation") == "link-existing"), None)
                if not match:
                    raise ValueError(f"candidate {candidate['candidateId']} is marked link-existing without a matching duplicate")
                operation = self._operation(import_id, candidate["candidateId"], "link-task", {"reference": match["reference"]}, approval_required, agent, suffix=f"-{safe_task_id(match['reference'])}")
            else:
                input_data = {"proposal": candidate["proposal"]}
                if parent_reference:
                    input_data["parentReference"] = parent_reference
                operation = self._operation(import_id, candidate["candidateId"], "create-task", input_data, approval_required, agent)
            if approved and operation["status"] == "waiting-approval":
                operation = self.approve(import_id, operation["metadata"]["id"], True)
            candidate["operationId"] = operation["metadata"]["id"]
            operations.append(operation)
        pending = [item for item in plan["candidates"] if item["decision"] != "skip" and not item.get("externalReference")]
        plan["status"] = "applied" if not pending and not blocked else "applying"
        self._write(import_id, "plan.yaml", plan)
        return {"operations": operations, "blockedOnParent": blocked}

    def approve(self, import_id: str, operation_id: str, approved: bool) -> dict[str, Any]:
        operation = self._read(import_id, f"operations/{operation_id}.yaml")
        previous = operation.get("approval", {}).get("status")
        expected = "approved" if approved else "rejected"
        if previous == expected:
            return operation
        if previous in {"approved", "rejected"}:
            raise RuntimeError(f"operation approval is already {previous}")
        if operation["status"] != "waiting-approval":
            raise RuntimeError("operation is not waiting for approval")
        operation["approval"]["status"] = expected
        operation["status"] = "pending" if approved else "failed"
        if not approved:
            operation["error"] = {"code": "HUMAN_GATE_REJECTED", "message": "external action was rejected"}
        self._write(import_id, f"operations/{operation_id}.yaml", operation)
        return operation

    def execute(self, import_id: str, operation_id: str, executor: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        operation = self._read(import_id, f"operations/{operation_id}.yaml")
        if operation["status"] == "completed":
            return operation
        if operation["status"] == "failed" and operation.get("error", {}).get("code") == "HUMAN_GATE_REJECTED":
            raise RuntimeError("rejected external operation cannot be retried")
        if operation["status"] not in {"pending", "failed"}:
            raise RuntimeError(f"operation cannot execute from status {operation['status']}")
        operation["status"] = "running"
        self._write(import_id, f"operations/{operation_id}.yaml", operation)
        try:
            result = executor(operation)
        except Exception as exc:
            code = getattr(exc, "code", "MCP_UNAVAILABLE")
            operation["status"] = "failed"
            operation["error"] = {"code": code, "message": str(exc)}
            self._write(import_id, f"operations/{operation_id}.yaml", operation)
            return operation
        reference = result.get("reference") or operation["input"].get("reference")
        if not reference:
            raise ValueError("provider result must contain reference")
        operation["status"] = "completed"
        operation["result"] = result
        operation.pop("error", None)
        self._write(import_id, f"operations/{operation_id}.yaml", operation)
        self._link_candidate(import_id, operation, reference)
        return operation

    def _link_candidate(self, import_id: str, operation: dict[str, Any], reference: str) -> None:
        plan = self._read(import_id, "plan.yaml")
        candidate_id = operation["task"].split(":", 1)[1]
        candidate = next(item for item in plan["candidates"] if item["candidateId"] == candidate_id)
        candidate["externalReference"] = reference
        pending = [item for item in plan["candidates"] if item["decision"] != "skip" and not item.get("externalReference")]
        plan["status"] = "applied" if not pending else "applying"
        self._write(import_id, "plan.yaml", plan)

    @staticmethod
    def _known_reference(candidate: dict[str, Any]) -> str | None:
        if candidate.get("externalReference"):
            return candidate["externalReference"]
        if candidate["decision"] == "link-existing":
            match = next((m for m in candidate.get("duplicateMatches", []) if m.get("recommendation") == "link-existing"), None)
            return match["reference"] if match else None
        return None

    @staticmethod
    def _build_query(proposal: dict[str, Any]) -> dict[str, Any]:
        text = " ".join(filter(None, [proposal["title"], proposal.get("description", "")]))
        keywords = sorted(set(re.findall(r"[A-Za-zÀ-ÿ0-9_-]{4,}", text.lower())))[:20]
        return {"summary": proposal["title"], "keywords": keywords, "repositories": proposal.get("repositories", [])}
