# 11 — Task Lifecycle

Reference lifecycle:

```text
Task intake
  ↓
Understand
  ↓
Resolve context
  ↓
Impact analysis
  ↓
Risk assessment
  ↓
Policy decision
  ↓
Governed execution plan
  ↓
Enforcement point / gate (if required)
  ↓
Implement
  ↓
Validate
  ↓
Review ── changes requested ──▶ back to Implement (bounded rework)
  ↓ approved
Trace
  ↓
Submit
  ↓
Human/CI gates
  ↓
Evidence bundle
  ↓
Merge or handoff
```

Execution and phase timers begin and end on these persisted transitions. Human
gate intervals are accumulated separately from Runtime and validation time;
overlapping open gates count as one waiting interval rather than double-counted
human attention time.

A policy gate is requested when a policy requires it (`requestedAt`) but waits
only from the moment it holds the Execution (`blockedAt`). When an Execution
ends with a policy gate still `pending`, the gate is closed (`closedAt`):
`not-triggered` if it never held the Execution, with a measured zero wait, and
`withdrawn` if the Execution ended while it was waiting. Neither status is an
approval, and no gate wait remains open after termination.

A task may span multiple repositories while remaining one functional task. Each repository may have independent branches, commits and change requests linked back to the same task/execution.

The Project owns one canonical Execution State Store. Each repository used by
an Execution has a `WorkspaceBinding` to a checkout or worktree. Handoff changes
session ownership, not Task/Execution identity or workspace binding. A missing
recorded workspace blocks resume; it is never replaced by the caller's current
directory.
