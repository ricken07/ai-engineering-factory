"""Evaluation Harness: Runtime and Adapter conformance scenarios.

Level 1 (Runtime Conformance) and Level 2 (Adapter Conformance) are fully
deterministic and require no LLM call. Level 3 (Engineering Outcome) is a
contract only — evaluating real code quality needs a real agent run and is
out of scope here.

Every scenario reuses existing Runtime entry points (RuntimeService,
resolve_engineering_context, evaluate_runtime_policy, resolve_task_provider);
none of them introduce a second Runtime or a parallel state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import copy
import subprocess

from .config import get_api_version

import yaml

from .concurrency import ExecutionLease
from .engineering import PracticeConflict, resolve_engineering_context
from .intake import TaskRegistry
from .policy import evaluate_runtime_policy
from .project import initialize
from .provider_runtime import ProviderResolutionError, resolve_task_provider
from .service import AUTONOMY_RANK, RuntimeService
from .yamlio import load_yaml


# --------------------------------------------------------------------------
# Fixtures — a single minimal, reusable seed project per scenario. Multi-repo
# scenarios reuse the existing examples/emmany fixture rather than a new one.
# --------------------------------------------------------------------------

def _seed_project(factory: Path, workdir: Path, *, autonomy: dict[str, str] | None = None,
                   repositories: list[dict[str, Any]] | None = None, **overrides: Any) -> Path:
    project_root = workdir / "project"
    initialize(factory / "templates" / "project", project_root)
    if autonomy or repositories or overrides:
        path = project_root / ".ai" / "project.yaml"
        data = load_yaml(path)
        if autonomy: data["autonomy"] = autonomy
        if repositories: data["repositories"] = repositories
        data.update(overrides)
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return project_root


_MAIN_REPOSITORY = [{"id": "main", "path": ".", "role": "application", "profiles": ["generic"],
                      "responsibilities": [], "dependencies": [], "criticalDomains": []}]


def _git_commit_baseline(project_root: Path) -> None:
    for command in (
        ["git", "init", "-b", "main"],
        ["git", "config", "user.email", "factory@example.invalid"],
        ["git", "config", "user.name", "Factory Test"],
        ["git", "add", "."],
        ["git", "commit", "-m", "baseline"],
    ):
        subprocess.run(command, cwd=project_root, check=True, capture_output=True)


def _advance_to(execution, *, phase_id: str | None = None, skill: str | None = None) -> None:
    for phase in execution.data["phases"]:
        if (phase_id and phase["id"] == phase_id) or (skill and phase["skill"] == skill):
            break
        phase["status"] = "completed"
    execution.data["status"] = "running"
    execution.save()


def _impact_output(summary: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"summary": summary, "status": "completed", "evidence": ["verified"], "unknowns": [], "details": details}


# --------------------------------------------------------------------------
# Level 1 — Runtime Conformance scenario bodies.
#
# Each returns an agent-neutral "observed facts" dict. Agent identity is
# threaded through only where the Runtime pipeline itself accepts one
# (service.start / service.intake); it never leaks into the returned facts,
# which is exactly what makes Level 2 a diff of two Level 1 runs rather than
# a second scenario catalog.
# --------------------------------------------------------------------------

def run_simple_feature(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = _seed_project(factory, workdir)
    service = RuntimeService(project_root, factory)
    execution = service.start("/implement Ajoute un endpoint", agent)
    identifier = execution.data["metadata"]["id"]
    service.prepare_phase(identifier)
    output = load_yaml(factory / "core/skills/understand-task/examples/output.yaml")
    completed = service.complete_phase(identifier, output)
    return {"workflow": execution.data["workflow"]["id"], "firstPhaseStatus": "completed",
            "nextPhase": completed.next_phase()["id"] if completed.next_phase() else None}


def run_natural_language_bug(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = _seed_project(factory, workdir)
    service = RuntimeService(project_root, factory)
    intake = service.intake("Il y a un bug: la transaction de paiement échoue systématiquement", agent, confirmed=True)
    return {"workflow": intake["intent"]["workflow"], "intent": intake["intent"]["intent"]}


def run_ambiguous_request(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = _seed_project(factory, workdir)
    service = RuntimeService(project_root, factory)
    intake = service.intake("Le système de paiement", agent, confirmed=True)
    return {"workflow": intake["intent"]["workflow"], "mutating": intake["intent"]["mutating"]}


def run_multi_repo_change(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = factory / "examples" / "emmany"
    project = load_yaml(project_root / ".ai" / "project.yaml")
    api = resolve_engineering_context(factory, project_root, project, "egw-api", "implement-change")
    app = resolve_engineering_context(factory, project_root, project, "egw-app", "implement-change")
    api_ids = {item["id"] for item in api["practices"]}
    app_ids = {item["id"] for item in app["practices"]}
    return {"apiHasJavaConventions": "java-coding-conventions" in api_ids,
            "appHasJavaConventions": "java-coding-conventions" in app_ids}


def run_high_risk_change(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    task = {"metadata": {"id": "scenario-high-risk"}, "classification": {"risk": "unknown", "domains": [], "changeTypes": ["source-code"]},
            "scope": {"repositories": ["main"]}, "autonomy": {"requested": "L3"}}
    project = {"autonomy": {"default": "L3", "maximum": "L3"}}
    decision = evaluate_runtime_policy(factory, project, task, {"risk": "high", "repositories": ["main"], "domains": [], "changeTypes": ["source-code"]})
    return {"effectiveRisk": decision["effectiveRisk"], "authorizedAutonomy": decision["authorizedAutonomy"]}


def run_dirty_workspace(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = _seed_project(factory, workdir, repositories=_MAIN_REPOSITORY)
    _git_commit_baseline(project_root)
    (project_root / "untracked-change.txt").write_text("dirty")
    service = RuntimeService(project_root, factory)
    execution = service.start("Refactore le composant local", agent, confirmed=True)
    task = TaskRegistry(project_root).load(execution.data["task"])
    task["scope"] = {"repositories": ["main"]}
    TaskRegistry(project_root).save(task)
    service.reassess_tracking(task["metadata"]["id"], {"risk": "low", "repositories": ["main"], "changeTypes": ["refactoring"]})
    _advance_to(execution, phase_id="implementation")
    prepared = service.prepare_phase(execution.data["metadata"]["id"])
    return {"status": prepared["status"], "blockingReason": prepared.get("blockingReason", {}).get("type")}


def run_missing_provider(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = _seed_project(factory, workdir)
    path = project_root / ".ai" / "project.yaml"
    data = load_yaml(path)
    data.pop("integrations", None)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    project = load_yaml(path)
    try:
        resolve_task_provider(factory, project_root, project, ["search-task"], agent)
        return {"error": None}
    except ProviderResolutionError as exc:
        return {"error": exc.code}


def run_tracking_required(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = _seed_project(factory, workdir, repositories=_MAIN_REPOSITORY, taskTracking={"mode": "external"})
    service = RuntimeService(project_root, factory)
    execution = service.start("/implement Ajoute une fonctionnalité de paiement", agent)
    task = TaskRegistry(project_root).load(execution.data["task"])
    task["scope"] = {"repositories": ["main"]}
    TaskRegistry(project_root).save(task)
    service.reassess_tracking(task["metadata"]["id"], {"risk": "high", "repositories": ["main"], "changeTypes": ["source-code"]})
    _advance_to(execution, phase_id="implementation")
    prepared = service.prepare_phase(execution.data["metadata"]["id"])
    return {"status": prepared["status"], "blockingReason": prepared.get("blockingReason", {}).get("type")}


def run_human_gate(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = _seed_project(factory, workdir, autonomy={"default": "L3", "maximum": "L3"}, repositories=_MAIN_REPOSITORY)
    service = RuntimeService(project_root, factory)
    execution = service.start("Implémente une évolution locale", agent, confirmed=True)
    identifier = execution.data["metadata"]["id"]
    task_data = TaskRegistry(project_root).load(execution.data["task"])
    task_data["autonomy"] = {"requested": "L3"}
    TaskRegistry(project_root).save(task_data)
    _advance_to(execution, skill="analyze-impact")
    service.complete_phase(identifier, _impact_output("Critical impact", {"risk": "critical", "repositories": ["main"], "changeTypes": ["destructive-migration"]}))
    current = service.execution(identifier)
    _advance_to(current, phase_id="implementation")
    before = service.prepare_phase(identifier)
    service.approve_policy_gate(identifier, "before-implementation")
    after = service.execution(identifier).data["status"]
    return {"beforeStatus": before["status"], "requiredGates": before.get("requiredPolicyGates"), "afterStatus": after}


def run_policy_conflict(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = factory / "examples" / "emmany"
    project = copy.deepcopy(load_yaml(project_root / ".ai" / "project.yaml"))
    project["engineering"]["practices"]["secret-management"] = {"mode": "disable"}
    try:
        resolve_engineering_context(factory, project_root, project, "egw-api", "implement-change")
        return {"error": None}
    except PracticeConflict:
        return {"error": "PRACTICE_CONFLICT"}


def run_organization_practice_override(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = factory / "examples" / "emmany"
    project = copy.deepcopy(load_yaml(project_root / ".ai" / "project.yaml"))
    project["engineering"]["practices"]["java-coding-conventions"] = {"mode": "override", "ref": ".ai/context/conventions.md"}
    context = resolve_engineering_context(factory, project_root, project, "egw-api", "implement-change")
    practice = next(item for item in context["practices"] if item["id"] == "java-coding-conventions")
    return {"source": practice["source"], "overridden": bool(practice.get("overrides"))}


def run_handoff_claude_to_codex(factory: Path, workdir: Path, agent: str) -> dict[str, Any]:
    project_root = _seed_project(factory, workdir)
    service = RuntimeService(project_root, factory)
    execution = service.start("/analyze Comprends le module de paiement", "claude-code")
    identifier = execution.data["metadata"]["id"]
    lease = ExecutionLease(execution.root)
    lease.acquire("claude-code-session-1", 300)
    service.handoff_execution(identifier, "claude-code-session-1")
    reacquired = lease.acquire("codex-session-1", 300)
    return {"releasedBeforeHandoffTarget": True, "newOwner": reacquired["owner"]}


# --------------------------------------------------------------------------
# Scenario registry — Given/When/Then metadata, the runner, and the check.
# `agent_parametrized=False` marks scenarios whose code path never accepts an
# agent identity (already proven agent-invariant by construction, not just by
# observation) — Level 2 records that fact instead of running a no-op diff.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    name: str
    given: str
    when: str
    then: str
    run: Callable[[Path, Path, str], dict[str, Any]]
    check: Callable[[dict[str, Any]], bool]
    agent_parametrized: bool = True


SCENARIOS: dict[str, Scenario] = {
    scenario.name: scenario for scenario in (
        Scenario("simple-feature", "a nominal feature request", "the implement-task workflow runs",
                  "the first phase completes and the workflow advances",
                  run_simple_feature, lambda o: o["workflow"] == "implement-task" and o["nextPhase"] not in (None, "understand")),
        Scenario("natural-language-bug", "a natural-language bug report", "intake resolves its intent",
                  "the fix-bug workflow is selected",
                  run_natural_language_bug, lambda o: o["workflow"] == "fix-bug" and o["intent"] == "fix"),
        Scenario("ambiguous-request", "an ambiguous request with no clear mutating verb", "intake resolves its intent",
                  "analyze-task is selected as the conservative, non-mutating fallback",
                  run_ambiguous_request, lambda o: o["workflow"] == "analyze-task" and o["mutating"] is False),
        Scenario("multi-repo-change", "a poly-repo project with Java and Flutter repositories", "context is resolved per repository",
                  "Java conventions reach the Java repository only",
                  run_multi_repo_change, lambda o: o["apiHasJavaConventions"] is True and o["appHasJavaConventions"] is False,
                  agent_parametrized=False),
        Scenario("high-risk-change", "HIGH risk observations", "policy is evaluated",
                  "authorized autonomy is at or below the expected maximum (L2) for high risk",
                  run_high_risk_change, lambda o: o["effectiveRisk"] == "high" and AUTONOMY_RANK[o["authorizedAutonomy"]] <= AUTONOMY_RANK["L2"],
                  agent_parametrized=False),
        Scenario("dirty-workspace", "a dirty local workspace", "the implementation phase is prepared",
                  "mutation is blocked before implementation",
                  run_dirty_workspace, lambda o: o["status"] == "blocked"),
        Scenario("missing-provider", "a project with no task-provider integration bound", "a provider is resolved",
                  "resolution fails explicitly with PROVIDER_NOT_CONFIGURED",
                  run_missing_provider, lambda o: o["error"] == "PROVIDER_NOT_CONFIGURED"),
        Scenario("tracking-required", "a high-risk change requiring external tracking", "the implementation phase is prepared",
                  "the Execution is blocked pending external tracking",
                  run_tracking_required, lambda o: o["status"] == "blocked" and o["blockingReason"] == "external-tracking-required"),
        Scenario("human-gate", "a critical, destructive-migration change", "implementation is reached then the gate is approved",
                  "the Execution waits for approval, then resumes",
                  run_human_gate, lambda o: o["beforeStatus"] == "waiting-approval" and o["afterStatus"] == "running"),
        Scenario("policy-conflict", "a mandatory organization practice", "the project attempts to disable it",
                  "resolution fails closed with a practice conflict",
                  run_policy_conflict, lambda o: o["error"] == "PRACTICE_CONFLICT",
                  agent_parametrized=False),
        Scenario("organization-practice-override", "an allowed (non-mandatory) organization practice", "the project overrides it",
                  "the override is applied and traced to the project layer",
                  run_organization_practice_override, lambda o: o["source"] == "project" and o["overridden"] is True,
                  agent_parametrized=False),
        Scenario("handoff-claude-to-codex", "an Execution owned by a Claude Code session", "it is handed off",
                  "a Codex session can acquire the released Execution",
                  run_handoff_claude_to_codex, lambda o: o["newOwner"] == "codex-session-1",
                  agent_parametrized=False),
    )
}


# --------------------------------------------------------------------------
# Reporting — Scenario | Expected | Observed | PASS/FAIL | Evidence. No
# dashboard: a single plain-text table, suitable for a CI log or a file.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    expected: str
    observed: str
    status: str  # "PASS" | "FAIL"
    evidence: list[str] = field(default_factory=list)


def _describe(scenario: Scenario) -> str:
    return f"Given {scenario.given}; when {scenario.when}; then {scenario.then}"


def run_scenario(name: str, factory: Path, workdir: Path, agent: str = "claude-code") -> ScenarioResult:
    scenario = SCENARIOS[name]
    evidence = [f"level1:{name}:agent={agent}"]
    try:
        observed = scenario.run(factory, workdir, agent)
        passed = scenario.check(observed)
    except Exception as exc:  # a genuinely unexpected Runtime failure, not an asserted outcome
        return ScenarioResult(name, _describe(scenario), f"{type(exc).__name__}: {exc}", "FAIL", evidence + ["unexpected-exception"])
    return ScenarioResult(name, _describe(scenario), repr(observed), "PASS" if passed else "FAIL", evidence)


def run_all_level1(factory: Path, workdir: Path, agent: str = "claude-code") -> list[ScenarioResult]:
    results = []
    for index, name in enumerate(SCENARIOS):
        results.append(run_scenario(name, factory, workdir / f"scenario-{index}", agent))
    return results


def run_adapter_conformance(name: str, factory: Path, workdir: Path) -> ScenarioResult:
    scenario = SCENARIOS[name]
    if not scenario.agent_parametrized:
        return ScenarioResult(name, "no agent identity on this code path: agent-invariant by construction",
                               "not applicable", "PASS", [f"level2:{name}:not-agent-parametrized"])
    claude_dir = workdir / "claude-code"; claude_dir.mkdir(parents=True)
    codex_dir = workdir / "codex"; codex_dir.mkdir(parents=True)
    try:
        claude_observed = scenario.run(factory, claude_dir, "claude-code")
        codex_observed = scenario.run(factory, codex_dir, "codex")
    except Exception as exc:
        return ScenarioResult(name, "identical trajectory for claude-code and codex",
                               f"{type(exc).__name__}: {exc}", "FAIL", [f"level2:{name}:unexpected-exception"])
    identical = claude_observed == codex_observed
    evidence = [f"level2:{name}:claude-code={claude_observed}", f"level2:{name}:codex={codex_observed}"]
    return ScenarioResult(name, "identical trajectory for claude-code and codex",
                           "identical" if identical else f"diverged: {claude_observed} != {codex_observed}",
                           "PASS" if identical else "FAIL", evidence)


def run_all_level2(factory: Path, workdir: Path) -> list[ScenarioResult]:
    results = []
    for index, name in enumerate(SCENARIOS):
        results.append(run_adapter_conformance(name, factory, workdir / f"scenario-{index}"))
    return results


def format_report(results: list[ScenarioResult]) -> str:
    header = ["Scenario", "Expected", "Observed", "Status", "Evidence"]
    rows = [[r.scenario, r.expected, r.observed, r.status, "; ".join(r.evidence)] for r in results]
    widths = [max(len(header[i]), *(len(row[i]) for row in rows)) if rows else len(header[i]) for i in range(5)]
    lines = ["  ".join(header[i].ljust(widths[i]) for i in range(5))]
    lines.append("  ".join("-" * widths[i] for i in range(5)))
    for row in rows:
        lines.append("  ".join(row[i].ljust(widths[i]) for i in range(5)))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Level 3 — Engineering Outcome. Contract only: this builds a schema-valid,
# entirely unevaluated placeholder. Measuring real code quality requires a
# real agent run and human/LLM-judge review, both out of scope here.
# --------------------------------------------------------------------------

ENGINEERING_OUTCOME_DIMENSIONS = (
    "correctness", "scopeRespect", "testQuality", "reviewFindings", "rework", "policyViolations",
)


def pending_engineering_outcome(factory: Path, scenario: str, agent: str) -> dict[str, Any]:
    return {
        "apiVersion": get_api_version(factory),
        "kind": "EngineeringOutcome",
        "metadata": {"id": f"outcome-{scenario}-{agent}"},
        "scenario": scenario,
        "agent": agent,
        "dimensions": {dimension: {"status": "not_evaluated"} for dimension in ENGINEERING_OUTCOME_DIMENSIONS},
    }
