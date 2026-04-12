# 02 — Conceptual Model

```text
Factory
├── Standard
├── Policy
├── Workflow
├── Skill
├── Profile
├── Integration
└── Agent Adapter
        │
        ▼
      Project
        │
        ▼
     Workspace
        │
    ┌───┴──────┐
Repository  Repository
    │            │
    └─────┬──────┘
          ▼
        Context
          │
          ▼
         Task
          │
      ┌───┴────┐
      │        │
     Risk   Autonomy
      │        │
      └───┬────┘
          ▼
       Workflow
          │
       Execution
          │
 ┌────────┼──────────┐
Skill    Gate      Artifact
          │
          ▼
     Traceability
```

## Core concepts

### Factory
A versioned organizational engineering framework.

### Project
Declares which Factory version is used, workspace strategy, repositories, context locations, enabled profiles and integration capability mappings.

### Workspace
The local system view from which the coding agent operates. A workspace may contain one Git repository or several independent repositories.

### Repository
A source/versioning unit. In a poly-repo project, each repository remains independently versioned.

### Context
Project information required to perform work: project overview, architecture, domain, conventions, decisions and bounded memory.

### Task
A single unit of engineering work, potentially spanning multiple repositories.

### Risk
Effective risk after classification and policy resolution.

### Autonomy
Maximum set of actions the agent may perform for an execution.

### Standard
Quality expectations for an engineering activity.

### Policy
Rules that constrain or require behavior.

### Workflow
Ordered orchestration of skills, gates and outputs.

### Skill
Reusable capability with explicit inputs, outputs, side-effect mode and required external capabilities.

### Execution
Concrete instance of a workflow for one task.

### Gate
A checkpoint that must be satisfied before proceeding.

### Artifact
A structured or textual output produced during execution.

### Handoff
Portable state used when one agent/session hands work to another.

### Profile
Reusable stack/practice knowledge that extends the Core without changing it.

### Integration
Maps abstract Factory capabilities to an external provider or MCP.

### Adapter
Maps Factory workflow/skill semantics to an agent runtime such as Claude Code or Codex.
