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

1. resolve `activation.mode` from `.ai/project.yaml` and apply the
   Activation Gate: a native command always proceeds; free text proceeds
   under `auto` only after explicit human confirmation, and never under
   `manual` — see below;
2. pass the complete user request and its adapter identity to `aief run`;
3. inspect `aief execution next`;
4. execute the referenced Core Skill using its resolved `SKILL.md`;
5. submit structured output with `aief execution complete-phase`;
6. stop when the state is `waiting-approval`, `blocked` or `failed`;
7. resume only through the same persisted Execution.

Claude `/implement` and Codex `$implement` are therefore different native entry points to the same Runtime.

Native adapters must pin the canonical intent independently from the request
title. For example, `/implement Feature 1.1` invokes:

```bash
aief run "Feature 1.1" --agent claude-code \
  --intent implement --expect-workflow implement-task \
  --project "$PROJECT_ROOT" --factory "$FACTORY_HOME"
```

The Runtime returns a receipt containing the concrete Execution ID, resolved
intent, workflow and next phase. A model statement such as “Task normalized” is
not evidence. An adapter must fail closed when the receipt is absent or the
workflow differs, and source mutation is forbidden until `execution next`
returns the `implement-change` Skill.

### Activation gate

`activation.mode` in `.ai/project.yaml` (`auto` by default, or `manual`)
governs whether a request may reach `aief run`/`aief intake` at all, based on
the resolved `IntentResolution.source`:

- `source: explicit-command` — a native command such as `/implement` or
  `$implement` — always activates the Factory for that execution, regardless
  of `mode`.
- Any other source is natural language, gated by `mode`:
  - `auto`: the adapter must ask the developer whether to route the request
    through the Factory and pass `--activation-confirmed` only after an
    explicit yes; otherwise it handles the request directly, without the
    Factory.
  - `manual`: the adapter never routes free text through the Factory and
    never passes `--activation-confirmed` for it; it always handles the
    request directly.

`RuntimeService.intake` enforces this itself — shared by `aief intake` and
`aief run` — raising `ActivationRequired` (unconfirmed, `auto`) or
`ActivationDeclined` (`manual`) before any Task is persisted. This is a
Runtime guarantee, not adapter-side discipline: a request the gate refuses
never reaches the pipeline above.

## CLI examples

Create only the normalized task:

```bash
aief intake "Corrige le bug EGW-327" --project . --factory /opt/factory/1.7.0 --json
```

List the registered tasks in dependency order, or only the ones nothing prevents starting:

```bash
aief task list --project . --factory /opt/factory/1.7.0
aief task list --ready --project . --factory /opt/factory/1.7.0
```

Order is derived from `dependsOn`, never declared in a side file. See
`docs/31-task-ordering-and-readiness.md`.

Create an execution from a command shortcut:

```bash
aief run "/implement EGW-142" --agent codex --project . --factory /opt/factory/1.7.0
```

Create the same workflow from natural language, once the developer has
explicitly agreed to route it through the Factory (`activation.mode: auto`,
the default):

```bash
aief run "Implémente EGW-142" --agent claude-code --activation-confirmed --project . --factory /opt/factory/1.7.0
```

Without `--activation-confirmed`, the same command fails closed with
`ActivationRequired` and persists nothing. Under `activation.mode: manual`,
it always fails closed with `ActivationDeclined`, confirmed or not — only a
native command (`/implement`, `$implement`, ...) activates the Factory in
that mode.

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
