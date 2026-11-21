# Changelog

## Unreleased

- Added comparator evidence for every study gate: `plan-criteria` (plan gate without bound plan), `governed-plan` (`before-implementation`), `proposal` (`apply-proposal`) and `submission-evidence` (`before-commit`, `before-submission`, submission gate), computed before the decision changes the execution and shown by `aief execution gate-check`.
- Made the gate decision rule verifiable: `humanGates.decisionRule` is a rule document hashed (optionally pinned by `decisionRuleSha256`) and copied into each execution, and plan gate decisions store the `bound-plan-hashes` comparator evidence (expected frozen hashes from `--expect-plan-sha256` / `--expect-verification-sha256`, bound hashes, file integrity, planning reference); `aief execution gate-check` shows the approver the same evidence.
- Added the human gate protocol: `humanGates` (approvers, response limit, decision rule) is snapshotted per execution. Every gate decision is recorded in `gateDecisions`, a gate past its response limit expires and cancels the execution, and `aief execution reject` lets a human refuse a gate with a rationale through an `OBSERVED` channel.
- Added the payload ledger: each phase preparation records what the agent received (phase brief and `execution next` snapshots, Core Skill files, bound plan files) with SHA-256 and a classification per item and brief section; `aief execution payload-ledger` reports it and fails on any gap.
- Added bound plans: `aief run --bound-plan --bound-verification` fixes the task plan and verification before the execution starts; the Runtime records the `planning` phase from them, unchanged and verified by SHA-256, and refuses an agent-written plan.
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
