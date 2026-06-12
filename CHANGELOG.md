# Changelog

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
