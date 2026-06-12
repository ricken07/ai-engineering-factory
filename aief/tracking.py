from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mcp import resolve_capability


@dataclass(frozen=True)
class TrackingDecision:
    level: str
    reasons: tuple[str, ...]
    required_before: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"level": self.level, "reasons": list(self.reasons), **({"requiredBefore": self.required_before} if self.required_before else {})}


def evaluate_tracking(task: dict[str, Any], impact: dict[str, Any] | None = None) -> TrackingDecision:
    impact = impact or {}
    risk = impact.get("risk") or task.get("classification", {}).get("risk", "unknown")
    repositories = impact.get("repositories") or task.get("scope", {}).get("repositories", [])
    change_types = set(impact.get("changeTypes") or task.get("classification", {}).get("changeTypes", []))
    nature = task.get("nature", "change")
    reasons: list[str] = []
    if risk in {"high", "critical"}:
        reasons.append(f"risk is {risk}")
    if len(repositories) > 1:
        reasons.append("more than one repository is impacted")
    if reasons:
        return TrackingDecision("required", tuple(reasons), "implementation")
    if nature in {"informational", "validation", "review"} or (change_types and change_types <= {"documentation"}):
        return TrackingDecision("optional", (f"task nature is {nature}",))
    if change_types & {"functional-change", "source-code", "configuration", "dependency"} or nature == "change":
        return TrackingDecision("recommended", ("the intervention changes project assets",))
    return TrackingDecision("optional", ("no mandatory tracking condition matched",))


def promotion_plan(factory, project: dict[str, Any], task: dict[str, Any], environment: dict[str, str] | None = None) -> dict[str, Any]:
    if task.get("source", {}).get("type") != "local":
        raise ValueError("only a local Task can be promoted")
    search = resolve_capability(factory, project, "task-provider", "search-task", environment)
    create = resolve_capability(factory, project, "task-provider", "create-task", environment)
    return {
        "task": task["metadata"]["id"],
        "provider": create["provider"],
        "requiredOperations": [search["operation"], create["operation"], "link-task"],
        "gate": "before-external-task-creation",
        "duplicateSearchRequired": True,
        "approved": False,
    }
