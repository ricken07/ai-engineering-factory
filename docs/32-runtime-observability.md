# 32 — Lightweight Runtime Observability

AIEF is not an observability platform: no proprietary dashboard, no central
server, no message broker, no dedicated database. What the Runtime offers is
a structured, minimal event, stored locally, for each transition it already
transits — never a second state machine parallel to `Execution`.

## Event Envelope

Each event follows a single, agent-neutral contract:

```yaml
event:
  id: event-abc123def456
  type: phase.completed
  timestamp: 2026-09-02T10:00:00+00:00
factory:
  version: 1.15.0
project:
  id: emmany
task:
  id: EGW-142
execution:      # absent for request.created and intent.resolved,
  id: exec-142  # which precede Execution creation
payload: {}     # event-specific data, redacted (see Security)
```

The contract is described by `core/schemas/runtime-event.schema.json`. `event.type`
is a closed enumeration — an unlisted type is rejected by `TaskEventLog.append`
to prevent naming drift.

## Storage

One append-only JSONL file per Task, agent-neutral, already in place before
this increment:

```text
.ai/runtime/tasks/<task-id>/events.jsonl
```

This is the only required backend. Nothing else is needed to use AIEF.

## Minimal Events

```text
request.created
intent.resolved
task.normalized
workflow.started

phase.started
phase.completed
phase.failed

policy.evaluated
policy.reclassified

gate.requested
gate.approved
gate.rejected

workspace.prepared
workspace.blocked

integration.resolved
integration.failed

execution.completed
execution.failed
execution.cancelled
```

Each reuses an existing Runtime transition — none added by creating a parallel
mechanism:

| Event | Reused Runtime Transition |
|---|---|
| `request.created`, `intent.resolved`, `task.normalized` | `RuntimeService.intake` (Request → IntentResolution → Task) |
| `workflow.started` | `Execution.create` |
| `phase.started` | `RuntimeService.prepare_phase` (Skill contract / engineering context materialization) |
| `phase.completed` | `Execution.advance` on success |
| `phase.failed` | `Execution.fail_phase` |
| `policy.evaluated` / `policy.reclassified` | `RuntimeService.reassess_policy`; `reclassified` only if effective risk or authorized autonomy actually change from prior `PolicyDecision`, else `evaluated` |
| `gate.requested` | a `policyGates` entry or external tracking operation moves to `pending` |
| `gate.approved` / `gate.rejected` | `approve_execution`, `approve_policy_gate`, `TaskTrackingManager.approve` |
| `workspace.prepared` / `workspace.blocked` | `RuntimeService.workspace` and workspace safety blocks in `prepare_phase` — replaces old dynamic naming `workspace.<action>` |
| `integration.resolved` / `integration.failed` | `TaskTrackingManager.resolve_provider` (MCP/provider resolution) |
| `execution.completed` | `Execution.advance` when `next_phase()` becomes `None` |
| `execution.failed` | `Execution.fail_phase` (any current Execution fails with its phase) |
| `execution.cancelled` | `Execution.cancel` — completes a `cancelled` status already present in `common.schema.json#/$defs/executionStatus` and already verified everywhere (`readiness.py`, `service.py`) but never reached until now; not a new state machine, just the missing transition to an already-declared state |

`run_profile_validation` does not emit a dedicated `validation.*` event: its
transitions pass through `complete_phase`/`fail_phase`, which already emit
`phase.completed`/`phase.failed`/`execution.*` with `payload.phase ==
"validation"`. A separate `validation.*` event would duplicate exactly the
same fact under a second name — removed during consolidation review (see
`docs/34-release-readiness.md`).

## Export

- **By default**: structured events locally (`events.jsonl`). Always
  active, never disabled — it is the sole required source of truth.
- **Optional**: OpenTelemetry export, enabled only by the
  `AIEF_OBSERVABILITY_OTEL=1` environment variable. Without it, `opentelemetry`
  is not even imported. With it but no package installed (or any other export
  error), the failure is silently absorbed: a normal Execution is never blocked
  by exporter unavailability. AIEF depends on no external backend to function.

## Security

`TaskEventLog.append` redacts `payload` before writing:

- any key named `secret(s)`, `token(s)`, `password(s)`, `apikey`/`api_key`,
  `authorization`, `credential(s)`, `private(_)key` → value replaced by
  `[REDACTED]`;
- any value matching a known secret pattern (AWS key, GitHub token, Slack token,
  PEM private key, JWT) → `[REDACTED]`, wherever it appears;
- any key named `content`, `prompt(s)` or `body` → `[OMITTED:opt-in
  required]` by default. A caller with an explicit reason to include this
  content must pass `allow_content=True` — never the default behavior.

No complete prompt, no arbitrary source content, and no private project
context content (e.g., resolved engineering practice text) is logged without
explicit decision at the call site.

## What It Is Not

- Not a replacement for state documents (`Task`, `Execution`,
  `PolicyDecision`, ...), which remain the structured, schema-validated
  source of truth.
- Not a Claude/Codex behavioral conformance system by itself: events verify that
  a trajectory occurred, not that two agents produce the same trajectory — see
  future scenario harness for that proof.
- Not a regulatory audit log: it lives under `.ai/runtime/`, gitignored,
  and is not reconstructed retroactively for Tasks predating its
  introduction.
