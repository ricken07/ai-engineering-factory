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
