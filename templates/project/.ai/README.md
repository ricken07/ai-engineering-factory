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
