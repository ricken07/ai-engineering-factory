# 26 — Task Execution Log

Each normalized request has a local append-only log:

```text
.ai/runtime/tasks/<task-id>/events.jsonl
```

The log describes the observable journey of the request independent of
Claude/Codex conversation. The complete event envelope contract, type list,
and security guarantees (redaction, opt-in) are described in
[`32-runtime-observability.md`](32-runtime-observability.md); this document
focuses on operational querying of a Task’s log.

Each event carries an `event.id`/`event.type`/`event.timestamp`, the
`project`, `task`, and `execution` ids when an Execution already exists. Decisions
are traced by their result, stated reasons and produced artifact in `payload`.
The log contains no private reasoning, secrets, or complete conversation transcripts.

Example:

```json
{"event":{"id":"event-abc123","type":"policy.reclassified","timestamp":"2026-09-02T10:00:00Z"},"factory":{"version":"1.15.0"},"project":{"id":"emmany"},"task":{"id":"EGW-142"},"execution":{"id":"exec-142"},"payload":{"status":"decided","risk":"high","authorizedAutonomy":"L2","requiredGates":["before-implementation"]}}
```

Query:

```bash
aief task log <task-id> --project . --factory "$GAD_AI_FACTORY_HOME"
aief task log <task-id> --project . --factory "$GAD_AI_FACTORY_HOME" --json
```

The `.ai/runtime/` folder remains gitignored. For durable traceability, the
`record-traceability` workflow publishes only the validated summary to the
configured provider. The local log facilitates diagnostics, resumption and handoff, but does not
replace GitLab, GitHub or Jira as a delivery system.

## Verifying an `/implement` Execution

A conforming execution must begin with at least:

```text
request.created
intent.resolved
task.normalized
workflow.started
phase.started (understand)
```

Then each phase must produce an observable trajectory:

```text
phase.started
phase.completed
```

Before the first source modification, the log must show preceding phases completed
and `implement-change` preparation. If a file is modified while the last event is
`workflow.started`, or if the workflow is `analyze-task`, the modification cannot be
attributed to a conforming Factory Execution.

## After an Upgrade

Logs are not reconstructed retroactively. A Task created before this feature
was introduced may return an empty list. New Tasks are logged starting at
`task.normalized`.

After modifying a Skill or the Runtime, exit the agent session completely and
open a new one. Then verify the `runtimeReceipt` and `taskLog` field before
letting the agent continue. The detailed procedure is in
[`23-first-steps.md`](23-first-steps.md).

## Core Skill Resolution

`aief execution next` returns a resolved contract:

```yaml
skillContract:
  id: understand-task
  invocation: core-contract
  manifest: <factory>/core/skills/understand-task/skill.yaml
  instructions: <factory>/core/skills/understand-task/SKILL.md
  outputSchema: <factory>/core/skills/understand-task/output.schema.json
```

Claude/Codex reads these files then produces the expected artifact. It must not
call a hypothetical `Skill(understand)`: only the public entry points
`implement`, `fix`, `review`, etc. are native Adapter Skills.

For `analyze-impact`, the `phase.completed` event must appear only after
`details.repositories` validation. This list is automatically propagated to the
Task and Execution. Manual correction of `task.yaml`, `execution.yaml` or a
completed artifact invalidates traceability and must be rejected.

All following commands explicitly preserve `--project` and
`--factory`. A `Factory manifest not found` error triggers a clean shutdown;
it must never be worked around with a link or copy of `factory.yaml` in the
project workspace.
