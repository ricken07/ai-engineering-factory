# Changelog

## Unreleased

- Fixed `aief setup-adapter --execute` crashing with `AttributeError: 'Namespace' object has no attribute 'path'` after a successful install; the command now exits 0 in both dry-run and execute modes.

## 1.0.0 — First release

- Established an agent-agnostic core based on contracts, schemas and deterministic policies.
- Added reusable workflows, skills, technology profiles and agent adapters.
- Added request intake, task registry and resumable execution runtime.
- Added capability, integration, provider and MCP binding resolution.
- Added profile-driven validation with structured reports and blocking checks.
- Added inherited engineering contexts, mandatory practices and traceability.
- Added task tracking, duplicate detection and controlled external operations.
- Added workspace and Git safety, including drift detection and protection against destructive operations.
- Added idempotence, execution leases, controlled recovery and handoff between agents.
- Added dynamic policy re-evaluation and the most-restrictive-constraint rule.
- Added runtime governance, replayable evidence, observability and scenario evaluation.
- Added backlog import with dependencies, parent-child relationships and idempotent operations.
- Added task ordering and the `ready`, `blocked`, `active` and `done` readiness states.
- Added documentation, consistency checks, tests and the associated CLI commands.
