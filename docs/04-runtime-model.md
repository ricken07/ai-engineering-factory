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

Generated execution state SHOULD be stored outside durable project knowledge, for example `.ai/runtime/`, and SHOULD normally be gitignored unless an organization explicitly decides otherwise. Durable traceability belongs in task systems, commits, change requests, approved ADRs and durable project memory.
