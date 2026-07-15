# AI Engineering Factory

**Version:** 1.11.0
**Status:** Stable

AI Engineering Factory is an organization-level framework for industrializing AI-assisted software engineering with coding agents while keeping engineering rules, project context, traceability and approval gates under human control.

Version 1.11 resolves a minimal, task-aware and fingerprinted engineering context for every repository and Skill. See [Effective Engineering Context](docs/21-effective-engineering-context.md).

The Factory is intentionally split into an **agnostic Core** and optional extensions:

```text
ai-engineering-factory/
├── core/          # stack-, provider- and agent-agnostic
├── profiles/      # reusable technology/practice knowledge
├── integrations/  # mappings to GitLab, GitHub, Jira, Confluence, ...
├── adapters/      # mappings to Claude Code, Codex, ...
├── templates/     # project adoption template
├── examples/      # reference examples
└── docs/          # architecture and operating model
```

## Design statement

The Factory standardizes **how engineering work is performed**, not the implementation technology of a project.

- The **Factory** defines standards, policies, workflows and skill contracts.
- A **Project** defines its architecture, repositories, domain context, conventions and enabled extensions.
- A **Task** defines the unit of work.
- A **Workflow** defines the controlled process applied to the task.
- An **Agent Adapter** translates Factory semantics to a specific coding agent.
- **Integrations** provide capabilities such as source control, task management and knowledge access.

## Core invariants

1. The Core must not depend on Java, Spring, Flutter, React, Node or any other stack.
2. The Core must not depend on GitLab, GitHub, Jira, Confluence or any provider.
3. Core workflows must not contain Claude Code or Codex-specific instructions.
4. Project context belongs to the project, not to an agent session.
5. Durable decisions must not live only in chat history.
6. Autonomy is bounded by risk and policy resolution.
7. The most restrictive applicable permission wins.
8. Every meaningful change must be traceable to a task and execution.
9. Context is loaded progressively.
10. Protected/critical actions require explicit gates.

## Start here

Read in this order:

1. `docs/01-principles.md`
2. `docs/02-conceptual-model.md`
3. `docs/03-architecture.md`
4. `docs/04-runtime-model.md`
5. `docs/05-policy-resolution.md`
6. `docs/06-context-and-memory.md`
7. `docs/07-extension-model.md`
8. `docs/08-project-adoption.md`
9. `docs/13-agent-adapters-and-mcp.md`
10. `docs/14-universal-runtime.md`
11. `docs/15-profile-runtime.md`
12. `docs/16-organization-engineering-context.md`
13. `docs/17-task-tracking-provider-runtime.md`

## Executable Runtime

The `aief` CLI provides the shared deterministic path used by agent adapters. Explicit commands and natural language are normalized identically:

```bash
aief run "/implement EGW-142" --agent codex --project . --factory /path/to/factory/1.7.0
aief run "Corrige le bug EGW-327" --agent claude-code --project . --factory /path/to/factory/1.7.0
```

See `docs/14-universal-runtime.md` for task intake, execution, gates, handoff and complete examples.

## Project adoption

A project does **not** clone the Factory into its repositories. The Factory is installed once on the developer workstation, for example:

```text
~/.gad/ai-engineering-factory/0.1.0/
```

The project clones only `templates/project/`, then adapts `.ai/project.yaml`, `.ai/repository-map.yaml` and its context.

See `examples/emmany/` for a poly-repository example.

## Stability

`v1alpha1` means the contracts are explicit and usable for pilots, but may still evolve before a stable `v1` contract.
