# 04 — Runtime Model

## Developer entry point

The developer starts the coding agent from the project workspace:

```text
~/workspace/emmany/
```

not from the Factory repository.

## Bootstrap sequence

```text
Agent starts
  ↓
Detect project `.ai/project.yaml`
  ↓
Resolve requested Factory version
  ↓
Load Core policies + selected workflow
  ↓
Load project + active task
  ↓
Resolve repository impact
  ↓
Load relevant context/profiles
  ↓
Resolve effective policies
  ↓
Create PolicyDecision
  ↓
Execute workflow within authorized actions
  ↓
Persist artifacts / traceability
```

## Factory installation model

Recommended workstation layout:

```text
~/.gad/ai-engineering-factory/
├── 0.1.0/
├── 0.2.0/
└── 1.0.0/

~/workspace/
└── emmany/
    ├── .ai/
    ├── AGENTS.md
    ├── CLAUDE.md
    ├── egw-api/.git/
    └── egw-app/.git/
```

The project pins a Factory version. Multiple projects may use different Factory versions concurrently.

## Runtime state

Generated task and execution state is stored under `.ai/runtime/tasks/` and `.ai/runtime/executions/`. It is gitignored by default and retained according to project configuration. Durable traceability belongs in task systems, commits, change requests, approved context, decision records and validated project memory.

## What a project commits

The project configuration, repository map, approved context, decisions, validated memory and integration lock belong in Git. In particular, `.ai/project.yaml` is part of the project contract and must be versioned.

`.ai/runtime/` remains local and must stay ignored. It contains generated Tasks, Executions, leases and phase artifacts; it is not a replacement for durable project documentation or the external change record.

Runtime state is agent-neutral. An adapter identity may be recorded for audit, but resuming an execution must not require the original agent or its conversation history.

Knowledge learned during execution remains task-local until the `promote-knowledge` workflow proposes a `MemoryCandidate`, obtains explicit approval and records a content-bound `KnowledgePromotion`.

## Universal intake and executable commands

Commands are optional intent shortcuts. `aief run` normalizes commands and natural language through the same Request, IntentResolution, Task and Execution contracts. Phase results are schema-validated before persistence, and runtime state can be resumed by a different adapter.

See `docs/14-universal-runtime.md` for the executable protocol and use cases.
