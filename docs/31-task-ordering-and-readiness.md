# 31 — Task Ordering and Derived Readiness

## Goal

Until 1.14.0, the Factory had no primitive for task ordering.
`aief intake` normalizes one request at a time, `aief execution next` advances a
phase *within* an already-chosen execution, and the only topological function
in the Runtime (`aief backlog apply`) ordered the *creation* of external tickets,
never their execution. The declared dependency on an `ExternalTaskProposal`
disappeared from state as soon as the issue was created: it survived in the
tracker, nowhere in `.ai/runtime`.

Consequence: order could only live in a pilot file read by the agent, applied
by discipline not constraint — outside schema, outside `aief validate`, outside
event log. This is exactly the class of guarantee the Factory exists to
eliminate.

Version 1.15.0 fills this gap without introducing a scheduler: dependency is
**declared** on the Task and governed by schema; order and availability are
**derived** from state, never declared.

## What the Project Declares

`task.schema.json` accepts two additional fields:

```yaml
kind: Task
metadata: {id: EGW-142}
parent: EGW-100          # hierarchy — does not order or block
dependsOn: [EGW-141]     # sequence — orders and blocks
objective: {summary: ...}
```

The distinction is intentional. `parent` attaches a Task to its epic; an epic
need not complete before its children. `dependsOn` expresses real precedence:
while a dependency is unfinished, the Task is not ready to take.

These fields live in `.ai/runtime/tasks/<id>/task.yaml`, so within the scope
scanned by `aief validate`: a malformed `dependsOn` breaks project validation
instead of passing silently.

## What the Runtime Derives

The Runtime stores no Task status. It recalculates it:

```text
Task state     = status of its most recent Execution
                 (no Execution → pending)
readiness      = function of (state, unsatisfied dependencies)
```

Execution identifiers carry a UTC timestamp, so "most recent" resolves by
lexicographic sort, without reading a clock.

| readiness | meaning |
| --- | --- |
| `done` | a `completed` Execution exists |
| `blocked` | at least one declared dependency is unfinished, or unknown |
| `active` | an Execution already owns the Task, including still `pending` |
| `ready` | nothing prevents opening an Execution |

Three explicit decisions:

- An Execution owns its Task on creation, before even its first phase.
  A `pending` Execution makes the Task `active`: without this, an agent
  could open a second one on the same work.
- A `failed` or `cancelled` Execution leaves the Task `ready`: failure is
  replayable, not terminal.
- A `dependsOn` reference that matches no registered Task
  **blocks** and is reported in `unknownDependsOn`. No silent fallback:
  a dependency we cannot resolve is not a satisfied dependency.
- A dependency cycle is an error, as with `backlog apply`. The
  Runtime refuses to produce an order rather than produce a false one.

A Task showing `readiness: blocked` with `state: running` signals an
**order violation**: an execution started on work whose preconditions are
unsatisfied. The two fields are exposed separately to make this visible.

## The Command

```bash
aief task list --project . --factory "$AI_FACTORY_HOME"
aief task list --ready --project . --factory "$AI_FACTORY_HOME"
```

The output is a `TaskBacklog` artifact validated against
`core/schemas/task-backlog.schema.json`:

```yaml
kind: TaskBacklog
project: emmany-gateway
filter: ready
tasks:
  - task: EGW-141
    position: 1
    state: pending
    readiness: ready
    summary: Expose the Homework contract
    workflow: implement-task
    intent: implement
```

`--ready` keeps only ready-to-take Tasks and renumbers positions. Tasks are
sorted topologically by `dependsOn`, order between independent Tasks stabilized
by identifier.

The projection is **calculated on read, never persisted**. There is no order to
resynchronize: Runtime state is the sole source.

## Acknowledged Limit

`aief task list` is a **read**, not a gate. The Factory does not today forbid
opening an Execution on a `blocked` Task — it makes this visible and auditable.
Hard enforcement of precedence (blocking via `blockingReason`, like
`external-tracking-required`) remains an open choice, to decide when usage
shows whether visibility suffices.

Per `docs/19-idempotence-execution-leases.md`, no scheduler, daemon,
database or distributed lock is introduced.
