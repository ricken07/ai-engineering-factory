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
Review
  ↓
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

A task may span multiple repositories while remaining one functional task. Each repository may have independent branches, commits and change requests linked back to the same task/execution.
