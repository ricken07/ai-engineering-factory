# QA Report

Package: `ai-engineering-factory`
Version: `1.11.0`

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
- Organization practices, documents and profile references validate as contracts.
- Mandatory practices reject disable and override attempts during validation and Runtime resolution.
- Effective contexts are filtered by repository profiles and Skill categories.
- Project and repository overrides are path-confined, explicit and traceable.
- Profile validation persists its resolved testing/security engineering context.
- Tracking policy rules are interpreted from Core policy data with most-restrictive-wins semantics.
- Provider resolution fails explicitly for missing provider, unsupported capability, missing MCP and missing authentication.
- Duplicate search precedes creation; linking and L2 creation require approval.
- Completed external operations are idempotent and transient retries preserve the operation ID.
- Required unresolved tracking blocks before implementation and successful canonical linking resumes the Execution.
- Git inspection uses structured argv commands with `shell=False` and persists a schema-valid workspace snapshot.
- Dirty repositories, wrong base branches, unmerged conflicts and workspace drift block mutation.
- Poly-repo preparation is preflighted before branch creation; worktree mode starts from the configured base commit.
- Force push, hard reset, clean, branch deletion and change-discard operations are rejected deterministically.
- Conservative rollback only touches clean, execution-owned worktrees or clean task branches and never deletes branches.
- Execution leases are atomically acquired, renewed and released; a different owner cannot mutate an active Execution.
- Runtime transitions use stable operation IDs and content fingerprints to prevent duplicate phase completion and approval.
- Identical operation replay returns the persisted result; conflicting replay and concurrent running operations fail closed.
- Handoff releases ownership explicitly, allowing another agent session to acquire the Execution.
- Execution state writes use atomic file replacement, and lease/operation artifacts validate against Factory schemas.
- Dynamic policy evaluation derives effective risk from domains, change types, repository count and repository critical domains.
- Risk, scope and constraints cannot silently decrease during an Execution; the most restrictive observation wins.
- Project autonomy ceilings combine deterministically with Factory risk limits.
- Re-evaluation occurs automatically after impact analysis and planning and persists versioned PolicyDecision artifacts.
- Dynamic pre-phase gates prevent implementation or submission before required human approval.
- Policy approval resumes the Execution without completing or skipping the protected phase.
- Tracking consumes the governed effective risk, including repository-derived criticality, rather than a lower raw agent observation.
- Effective engineering context resolves Organization, Profile, Project, Repository and Task layers in deterministic order.
- Task-local overrides are path-confined and cannot weaken mandatory or protected organization practices.
- Skill category declarations progressively exclude unrelated engineering knowledge.
- Profile IDs, versions, sources and inheritance are included in context provenance.
- Practice contents carry SHA-256 hashes and explicit organization/project/repository/task provenance.
- Stable context fingerprints detect relevant profile, document or Task changes across agent handoffs.
- Impact and risk phases now receive architecture/security context without loading review or testing material.
- The complete automated suite passes with 95 tests.

This QA checks structural consistency, not the behavior of a specific coding agent or provider MCP.
