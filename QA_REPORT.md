# QA Report

Package: `ai-engineering-factory`
Version: `1.5.0`

Checks completed successfully:

- All packaged JSON Schemas, including task memory and knowledge promotion contracts, are valid Draft 2020-12 schemas.
- All YAML files parse successfully.
- Factory manifest validates against `factory.schema.json`.
- Project template validates against `project.schema.json`.
- Emmany poly-repo example validates against `project.schema.json`.
- Reference Task, PolicyDecision and Handoff validate against their schemas.
- All Core policies, standards, skills and workflows validate against their schemas.
- All workflow skill references resolve to existing Core skills.
- All provided profiles, integrations and adapters validate against their contracts.
- Emmany integration provider IDs resolve to packaged integrations.
- Every Core workflow and skill references bounded recovery.
- Core agnosticity is tested against project, stack, provider and agent leakage.
- Skill output examples validate against their output schemas.
- Knowledge approval is cryptographically bound to candidate content and target.
- Codex and Claude Code expose the same eight Factory intents through thin user-level skills.
- MCP resolution is tested from project capability selection through provider binding and native agent configuration.
- Adapter installation is dry-run by default, refuses unrelated overwrites and is idempotent for managed links.
- Provider operations validate against abstract integration contracts.
- Integration locks are deterministic, content-addressed and secret-free.
- MCP synchronization is dry-run by default, preserves unmanaged native configuration and rejects conflicting provider entries.
- Request, IntentResolution, normalized Task, Execution and Handoff documents validate against their contracts.
- Explicit commands and equivalent natural-language requests converge on the same workflow.
- Ambiguous requests conservatively fall back to non-mutating analysis.
- Workflow compilation resolves Core Skills, output schemas and required capabilities without adapter duplication.
- Skill outputs are schema-validated before execution state advances.
- Gate evidence is persisted before approval is requested, and premature approval is rejected.
- Tracking is deterministically re-evaluated when risk, scope or change type changes.
- Local-task promotion plans require duplicate search, a human gate and provider-neutral task-provider operations.
- Profile validation resolves only impacted project repositories and composes inherited profiles deterministically.
- Profile commands are argv arrays executed with `shell=False`; missing executables are recorded as failures.
- Validation requires an active `validate-change` phase and autonomy L2 or greater.
- Successful validation advances the workflow; any command failure persists evidence and fails the Execution.

This QA checks structural consistency, not the behavior of a specific coding agent or provider MCP.
