# Project Runtime

This directory contains ephemeral task and execution state. It is ignored by Git by default.

Expected layout:

```text
tasks/<task-id>/
  request.yaml
  intent.yaml
  task.yaml
  state.yaml
  events.jsonl

executions/<execution-id>/
  execution.yaml
  policy-decision-<revision>.yaml
  governed-execution-plan-<revision>.yaml
  enforcement-*.yaml
  workspace.yaml
  validation.yaml
  validation-replay.yaml
  review.yaml
  evidence-bundle.yaml
  lease.yaml
  operations/<operation-id>.yaml
  <phase-artifacts>.yaml
  handoff.yaml

worktrees/<execution-id>/<repository-id>/
  <execution workspace; not Runtime state>
```

Timing, actor identities, review independence and reproducibility metadata are
stored in `execution.yaml`; experimental metrics are exported from that state.
Files listed above are conditional on the executed Workflow and controls.

Linked Git worktrees resolve this canonical Project Runtime directory from the
main checkout. A worktree is an Execution Workspace, not a Project, Task,
Execution, memory store or source of truth. Deleting an execution-owned
worktree must not delete its sibling Execution state or EvidenceBundle.

Publish durable task summaries to the configured task/change system. Never promote runtime content directly into project knowledge without the `promote-knowledge` workflow.

Each Task also owns an append-only `tasks/<task-id>/events.jsonl` journal. It
records the observable execution trajectory: intent, workflow, phases,
artifacts, policy decisions, gates, workspace operations and validation
outcomes. It never stores private chain-of-thought. Inspect it with:

```bash
aief task log <task-id> --project . --factory "$AI_FACTORY_HOME"
```
