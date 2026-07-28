# Project Runtime

This directory contains ephemeral task and execution state. It is ignored by Git by default.

Expected layout:

```text
tasks/<task-id>/
  task.yaml
  understanding.yaml
  context.yaml
  impact.yaml
  risk.yaml
  policy-decision.yaml
  plan.yaml
  decisions.yaml
  validation.yaml
  review.yaml
  handoff.yaml

executions/<execution-id>/
  execution.yaml
  <phase-artifacts>.yaml
```

Publish durable task summaries to the configured task/change system. Never promote runtime content directly into project knowledge without the `promote-knowledge` workflow.

Each Task also owns an append-only `tasks/<task-id>/events.jsonl` journal. It
records the observable execution trajectory: intent, workflow, phases,
artifacts, policy decisions, gates, workspace operations and validation
outcomes. It never stores private chain-of-thought. Inspect it with:

```bash
aief task log <task-id> --project . --factory "$GAD_AI_FACTORY_HOME"
```
