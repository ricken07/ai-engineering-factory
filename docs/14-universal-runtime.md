# 14 — Universal Factory Runtime

## Purpose

The Runtime is a deterministic coordination layer, not a new coding agent. Claude Code, Codex and future agents retain responsibility for semantic reasoning and source changes. The Runtime gives every adapter the same intake, contracts, workflow order, persisted state and gates.

Commands are shortcuts. Natural-language requests enter the same pipeline:

```text
User request
  → Request
  → IntentResolution
  → Task
  → compiled Workflow
  → Execution
  → validated phase Artifacts
  → gates / handoff
```

## Deterministic boundary

The executable boundary is exposed by `aief` and `aief.service.RuntimeService`:

- discover the project;
- persist the original request;
- resolve explicit commands and conservative language signals;
- normalize an external or local Task;
- compile workflow phases and Core Skill contracts;
- create and resume schema-conformant Execution state;
- validate every submitted phase result against the Skill output schema;
- persist an artifact before entering a post-phase approval gate;
- create an agent-neutral Handoff.

Understanding business meaning, inspecting code, choosing a coherent implementation and semantic review remain agentic operations. Ambiguous input falls back to non-mutating `analyze-task`; the Runtime never guesses permission to modify code.

## Files produced in a project

```text
.ai/runtime/
├── tasks/<task-id>/
│   ├── request.yaml
│   ├── intent.yaml
│   ├── task.yaml
│   └── state.yaml
└── executions/<execution-id>/
    ├── execution.yaml
    ├── <phase-id>.yaml
    └── handoff.yaml
```

These files are local runtime state by default. Durable traceability is promoted through configured integrations and governed workflows.

## Adapter protocol

An adapter must not implement intent rules or workflow logic. It must:

1. pass the complete user request and its adapter identity to `aief run`;
2. inspect `aief execution next`;
3. execute the referenced Core Skill using its resolved `SKILL.md`;
4. submit structured output with `aief execution complete-phase`;
5. stop when the state is `waiting-approval`, `blocked` or `failed`;
6. resume only through the same persisted Execution.

Claude `/implement` and Codex `$implement` are therefore different native entry points to the same Runtime.

## CLI examples

Create only the normalized task:

```bash
aief intake "Corrige le bug EGW-327" --project . --factory /opt/factory/1.7.0 --json
```

Create an execution from a command shortcut:

```bash
aief run "/implement EGW-142" --agent codex --project . --factory /opt/factory/1.7.0
```

Create the same workflow from natural language:

```bash
aief run "Implémente EGW-142" --agent claude-code --project . --factory /opt/factory/1.7.0
```

Inspect the next phase and submit its schema-valid result:

```bash
aief execution next <execution-id> --project . --factory /opt/factory/1.7.0
aief execution complete-phase <execution-id> --output understanding.yaml --project . --factory /opt/factory/1.7.0
```

Approve a waiting gate and create a handoff:

```bash
aief execution approve <execution-id> --project . --factory /opt/factory/1.7.0
aief execution handoff <execution-id> --project . --factory /opt/factory/1.7.0
```

Re-evaluate tracking after impact analysis reveals new scope or risk:

```bash
aief task assess-tracking <task-id> --impact impact.yaml --project . --factory /opt/factory/1.7.0
```

This operation can upgrade a local task from `recommended` to `required`. A required result blocks implementation until the adapter completes duplicate search, obtains the human gate and calls the configured provider's `create-task` capability. It never silently falls back to another provider.

## Use cases

| Request | Normalized intent | Workflow | Task kind |
| --- | --- | --- | --- |
| `/implement EGW-142` | implement | implement-task | external |
| `Implémente EGW-142` | implement | implement-task | external |
| `Les callbacks FAILED restent PENDING, corrige ce bug` | fix | fix-bug | local |
| `Refactore PaymentOrchestrator sans changer son comportement` | refactor | refactor-code | local |
| `$test EGW-142` | test | add-tests | external |
| `/review !214` | review | review-change | external |
| `Explique la gestion des webhooks` | analyze | analyze-task | local informational |
| `Regarde PaymentOrchestrator` | analyze, ambiguous | analyze-task | local informational |

External task retrieval and local-task promotion remain capability-driven. The Task contract already carries tracking and canonical-reference fields; provider search/create/link and deterministic tracking policy are the next Runtime increment.
