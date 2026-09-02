from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re
import uuid
import yaml
from .yamlio import load_yaml
from .config import get_api_version


class ActivationRequired(RuntimeError):
    """A natural-language request needs explicit human confirmation before the
    Factory activates (`activation.mode: auto`, the default)."""


class ActivationDeclined(RuntimeError):
    """A natural-language request was submitted while Factory activation is
    disabled (`activation.mode: manual`); only a native command activates it,
    and only for its own execution."""


INTENT_WORKFLOWS = {
    "analyze": "analyze-task",
    "implement": "implement-task",
    "fix": "fix-bug",
    "refactor": "refactor-code",
    "test": "add-tests",
    "review": "review-change",
    "document": "update-documentation",
    "promote": "promote-knowledge",
}

MUTATING = {"implement", "fix", "refactor", "test", "document", "promote"}
REFERENCE = re.compile(r"https?://[^\s]+/-/issues/\d+|(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+#\d+|(?<![A-Za-z0-9])(?:[A-Z][A-Z0-9]+-\d+|!\d+|#\d+)(?![A-Za-z0-9])")
COMMAND = re.compile(r"^\s*[/\$](analyze|implement|fix|refactor|test|review|document|promote)(?:\s+(.*))?$", re.I | re.S)

KEYWORDS = {
    "fix": ("fix", "corrige", "corriger", "bug", "problème", "erreur", "failure", "failed", "panne"),
    "refactor": ("refactor", "refactore", "refactorise", "sans changer son comportement"),
    "test": ("test", "teste", "ajoute des tests", "coverage", "couverture"),
    "review": ("review", "revue", "relis", "merge request", "pull request"),
    "document": ("document", "documente", "documentation", "readme"),
    "implement": ("implement", "implémente", "implemente", "ajoute", "développe", "feature"),
    "analyze": ("analyze", "analyse", "explique", "comprends", "investigue", "comment fonctionne"),
    "promote": ("promote", "promeus", "capitalise"),
}


def _identifier(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"


def create_request(text: str, factory: Path | None = None, agent: str | None = None) -> dict[str, Any]:
    if not text.strip():
        raise ValueError("request text must not be empty")
    match = COMMAND.match(text)
    api_version = get_api_version(factory) if factory else "aief.dev/v1alpha1"
    data: dict[str, Any] = {
        "apiVersion": api_version,
        "kind": "Request",
        "metadata": {"id": _identifier("request")},
        "text": text.strip(),
        "receivedAt": datetime.now(timezone.utc).isoformat(),
    }
    if agent:
        data["agent"] = agent
    if match:
        data["command"] = match.group(1).lower()
        if match.group(2):
            data["arguments"] = match.group(2).strip()
    return data


def resolve_intent(request: dict[str, Any], factory: Path | None = None) -> dict[str, Any]:
    text = request["text"].lower()
    if request.get("command") in INTENT_WORKFLOWS:
        intent, confidence, source = request["command"], "high", "explicit-command"
        reason = "agent-native command selected an exact Factory intent"
    else:
        matches = [intent for intent, words in KEYWORDS.items() if any(word in text for word in words)]
        if len(matches) == 1:
            intent, confidence, source = matches[0], "medium", "explicit-language"
            reason = "one supported intent matched explicit request language"
        elif matches and "fix" in matches:
            intent, confidence, source = "fix", "medium", "agent-classification"
            reason = "bug/failure language takes precedence over a generic change verb"
        else:
            intent, confidence, source = "analyze", "ambiguous", "conservative-fallback"
            reason = "no unique mutating intent was established; analysis is the safe default"
    reference = REFERENCE.search(request.get("arguments") or request["text"])
    api_version = get_api_version(factory) if factory else "aief.dev/v1alpha1"
    return {
        "apiVersion": api_version,
        "kind": "IntentResolution",
        "metadata": {"id": _identifier("intent")},
        "request": request["metadata"]["id"],
        "intent": intent,
        "confidence": confidence,
        "source": source,
        "mutating": intent in MUTATING,
        "workflow": INTENT_WORKFLOWS[intent],
        **({"taskReference": reference.group(0)} if reference else {}),
        "reason": reason,
        "requiresClarification": confidence == "ambiguous" and intent in MUTATING,
    }


def enforce_activation(resolution: dict[str, Any], mode: str, confirmed: bool) -> None:
    """Gate Factory routing for non-command requests per `activation.mode`.

    A native command (`source: explicit-command`) always activates the
    Factory for its own execution, regardless of `mode`. Only natural-language
    requests are gated: `manual` never routes them through the Factory;
    `auto` (the default) requires explicit human confirmation first.
    """
    if resolution["source"] == "explicit-command":
        return
    if mode == "manual":
        raise ActivationDeclined(
            "activation.mode is 'manual': natural-language requests are not routed "
            "through the Factory. Use a native command to activate it for this "
            "execution, or handle this request directly without the Factory."
        )
    if mode == "auto" and not confirmed:
        raise ActivationRequired(
            "activation.mode is 'auto': ask the human whether this natural-language "
            "request should be routed through the Factory. Retry with confirmed=True "
            "only after an explicit yes; otherwise handle the request directly "
            "without the Factory."
        )


def normalize_task(request: dict[str, Any], resolution: dict[str, Any], factory: Path | None = None) -> dict[str, Any]:
    reference = resolution.get("taskReference")
    task_id = reference or _identifier("local")
    intent = resolution["intent"]
    nature = "informational" if intent == "analyze" else "review" if intent == "review" else "validation" if intent == "test" else "change"
    source: dict[str, str] = {"type": "issue", "reference": reference} if reference else {"type": "local"}
    if reference and ("/-/issues/" in reference or ("/" in reference and "#" in reference)):
        source["provider"]="gitlab"
    api_version = get_api_version(factory) if factory else "aief.dev/v1alpha1"
    return {
        "apiVersion": api_version,
        "kind": "Task",
        "metadata": {"id": task_id},
        "source": source,
        "nature": nature,
        "intent": {"type": intent, "confidence": resolution["confidence"]},
        "objective": {"summary": request.get("arguments") or request["text"]},
        "workflow": resolution["workflow"],
        "tracking": {"level": "optional" if nature in {"informational", "validation", "review"} else "recommended"},
    }


class TaskRegistry:
    def __init__(self, project: Path):
        self.root = project / ".ai" / "runtime" / "tasks"

    def save(self, task: dict[str, Any]) -> Path:
        from .knowledge import safe_task_id

        task_root = self.root / safe_task_id(task["metadata"]["id"])
        task_root.mkdir(parents=True, exist_ok=True)
        path = task_root / "task.yaml"
        path.write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return path

    def list(self) -> list[dict[str, Any]]:
        """Every registered Task, ordered by directory name for determinism."""
        if not self.root.is_dir():
            return []
        return [load_yaml(path) for path in sorted(self.root.glob("*/task.yaml"))]

    def load(self, task_id: str) -> dict[str, Any]:
        from .knowledge import safe_task_id

        path = self.root / safe_task_id(task_id) / "task.yaml"
        if not path.is_file():
            raise FileNotFoundError(f"task not found: {task_id}")
        return load_yaml(path)
