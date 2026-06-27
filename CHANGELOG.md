# Changelog

## 1.7.0 — Task Tracking & Provider Resolution Runtime

- Interpreted the Core task-tracking policy deterministically with most-restrictive-wins semantics.
- Added TaskTrackingDecision, IntegrationResolution, ExternalTaskSearch, ExternalTaskProposal and ExternalOperation contracts.
- Added strict provider, operation, MCP endpoint, adapter and authentication resolution without fallback.
- Added duplicate-search preparation and structured hybrid duplicate assessment.
- Added human-gated existing-task linking and autonomy-gated external-task creation.
- Added stable operation IDs, completed-result reuse and same-key retry after transient failures.
- Added canonical external references while preserving local Task identity.
- Automatically re-evaluated tracking after impact analysis and blocked before implementation when unresolved.
- Automatically resumed blocked Executions after successful link/create.
- Added deterministic CLI primitives and agent adapter protocol documentation.

## 1.6.0 — Organization engineering context

- Added a versioned organization catalog of standards and practices outside the agnostic Core.
- Added Practice and EffectiveEngineeringContext contracts.
- Evolved profiles into assemblers through version-aware `practiceRefs`.
- Added project and repository `inherit`, `enable`, `disable` and `override` configuration.
- Added mandatory/default/optional enforcement and fail-closed conflict detection.
- Added deterministic hierarchy resolution with project/repository document path protection.
- Added per-Skill category filtering and direct document content delivery.
- Persisted effective contexts as agent-neutral Execution artifacts.
- Integrated effective testing/security context into profile-driven validation.
- Added CLI inspection, semantic project validation, examples and documentation.

## 1.5.0 — Profile-driven Runtime validation

- Connected `validate-change` phases to impacted repositories and their configured profiles.
- Added deterministic profile validation planning for mono- and poly-repository workspaces.
- Replaced shell command strings with argv arrays and `shell=False` execution.
- Added fail-closed workspace, repository, profile, phase and autonomy checks.
- Added structured ValidationReport evidence with per-command stdout, stderr and exit code.
- Made remote continuous integration optional rather than a mandatory local-validation capability.
- Added CLI planning and explicit execution for profile validation.
- Added missing-executable handling and stopped workflow execution on validation failure.

## 1.4.0 — Universal Runtime foundation

- Added agent-neutral Request and IntentResolution contracts.
- Added command and natural-language intake with conservative non-mutating fallback.
- Added normalized local/external Tasks and a persistent Task registry.
- Added deterministic Workflow/Skill compilation and capability discovery.
- Aligned Execution and Handoff persistence with their JSON Schemas.
- Added schema validation for every phase output before state advancement.
- Fixed approval gates so phase evidence is persisted before waiting.
- Added runtime CLI commands for intake, start, inspection, phase completion, approval and handoff.
- Added deterministic task-tracking evaluation and provider-neutral search/create/link promotion contracts.
- Documented the shared adapter protocol and representative use cases.

## 0.1.0 — Initial foundation

- Agnostic Core contracts and schemas.
- Policy model and policy resolution rules.
- Engineering standards.
- Reusable workflows and skills.
- Technology profiles as extensions.
- Integration capability contracts and provider mappings.
- Claude Code and Codex adapters.
- Project bootstrap template.
- Emmany poly-repository example.
# 1.3.0

- Split integration contracts, provider manifests and technical MCP definitions.
- Added explicit and shorthand-compatible project provider bindings.
- Added on-demand capability/operation resolution.
- Added deterministic, secret-free `integration-lock.yaml` generation.
- Added `integrations doctor`, `lock` and safe dry-run `sync` commands.
- Added project/user MCP scopes and strict native configuration overwrite protection.

# 1.2.0

- Added user-level Codex and Claude Code adapter skills with native invocation conventions.
- Added safe adapter installation planning and symlink/copy execution.
- Added provider-neutral MCP binding contracts and GitHub, GitLab, Jira and Confluence bindings.
- Added native Codex TOML and Claude JSON MCP configuration rendering.
- Stabilized project bootstraps and added `.ai/README.md` to the project template.
- Documented onboarding, session bootstrap, task execution, gates and MCP least privilege.

# 1.1.0

- Added explicit task-memory, memory-candidate and knowledge-promotion contracts.
- Added controlled `promote-knowledge` workflow with approval-bound durable writes.
- Added agent-neutral task runtime state and multi-agent handoff foundations.
- Expanded the project template with structured memory, runtime and retention configuration.
- Documented knowledge authority, freshness conflicts, progressive loading and retention.

# 1.0.0

- Added installable CLI, exhaustive contract validation, tests and CI.
- Added deterministic policy resolution and resumable workflow execution.
- Added executable profile/integration capability resolution.
- Added conformant Codex and Claude Code command adapters.
- Stabilized Core Skills with agent instructions, output schemas and examples.
