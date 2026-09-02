# Project AI Engineering Configuration

This directory contains project-owned configuration and knowledge consumed by the centrally installed AI Engineering Factory. It does not contain a copy of the Factory Core or agent adapters.

## Entry points

- `project.yaml`: project identity, Factory version, repositories, profiles, integrations, autonomy and runtime retention.
- `integration-lock.yaml`: generated, secret-free resolution of provider and MCP versions; normally committed after review.
- `repository-map.yaml`: repository responsibilities, exposed/consumed contracts and relationships.
- `context/`: authoritative project, architecture, domain and convention documents.
- `decisions/`: approved durable decision records.
- `memory/`: approved reusable patterns, constraints and lessons.
- `runtime/`: gitignored, agent-neutral task and execution state.
- `.claude/settings.json` and `.codex/`: project-level native permissions that
  enforce the Factory least-privilege baseline; they do not replace policies.

`project.yaml` explicitly selects `taskTracking.mode`. Use `local` when the
Task, Execution, artifacts and logs under `.ai/runtime/` are the tracking system
and no external task manager is configured. Use `external` only when required
Tasks must be linked through a configured `task-provider`.

`project.yaml` also selects `activation.mode` (`auto` by default). A native
command always activates the Factory for its own execution. Under `auto`,
free text activates it only after the agent asks the developer and receives
an explicit yes; under `manual`, free text never activates it.

## Responsibility boundaries

```text
Factory Core       what engineering process must be followed
Project .ai/       where and under which project constraints to work
Agent adapter      how the concrete agent invokes and executes the process
Integration/MCP    how an abstract external capability is provided
```

## Knowledge authority

Approved decisions and official context outrank project memory, task runtime and session observations. A newer task may request a change to authoritative knowledge; record the conflict and obtain the required approval instead of resolving it silently.

## Editing

Replace template placeholders only with verified project facts. Do not commit `.ai/runtime/`. Promote learned knowledge through `promote-knowledge`, which separates proposal, approval and durable recording.

Select providers in `project.yaml`; do not place MCP transports, native agent configuration or credentials there. Run `aief integrations lock`, `doctor` and `sync` during onboarding.
