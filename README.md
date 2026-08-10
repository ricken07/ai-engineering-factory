# AI Engineering Factory

**Version:** 1.14.0
**Status:** Stable

AI Engineering Factory is an agent-agnostic framework for industrializing
AI-assisted software engineering while keeping engineering rules, project
context, traceability and approval gates under human control.

Its intended progression is:

```text
Augmented developer → Augmented team → Augmented delivery → Augmented engineering organization
```

Version 1.11 resolves a minimal, task-aware and fingerprinted engineering context for every repository and Skill. See [Effective Engineering Context](docs/21-effective-engineering-context.md).

Version 1.12 introduced version-pinned organization catalogs as governed
Practices, with profile inheritance and explicit repository-role activation.
The repository includes one organization-specific catalog as an example; it is
not a Factory default.

Version 1.13 makes organization knowledge project-selectable. Technical
Profiles no longer impose any organization’s conventions; versioned
`OrganizationCatalog` contracts provide inheritance and Profile bindings.

Version 1.14 adds a Backlog Import Runtime: a documentation corpus can be
turned into many external tickets through a previewable, organization-rules-driven,
autonomy-gated `aief backlog import|preview|apply`, reusing the Task Tracking
Runtime's `ExternalTaskProposal`/`ExternalOperation` contracts.

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

Organization knowledge is optional and explicitly selected by each project.
The shipped organization-specific catalog and examples illustrate the model;
they are not normative defaults. Start a new catalog from
`templates/organization/` and keep its practices versioned independently.

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
4. `docs/00-factory-reference-architecture.md`
5. `docs/04-runtime-model.md`
6. `docs/05-policy-resolution.md`
7. `docs/06-context-and-memory.md`
8. `docs/07-extension-model.md`
9. `docs/08-project-adoption.md`
10. `docs/13-agent-adapters-and-mcp.md`
11. `docs/14-universal-runtime.md`
12. `docs/15-profile-runtime.md`
13. `docs/16-organization-engineering-context.md`
14. `docs/17-task-tracking-provider-runtime.md`
15. `docs/22-project-installation-guide.md`
16. `docs/23-first-steps.md`
17. `docs/24-organization-knowledge-catalog.md`
18. `docs/25-agent-permissions.md`
19. `docs/26-task-execution-log.md`
20. `docs/27-codex-usage.md`
21. `docs/28-gitlab-issues-and-board.md`
22. `docs/29-evidence-chain-and-replay.md`
23. `docs/30-backlog-import-runtime.md`

## Executable Runtime

The `aief` CLI provides the shared deterministic path used by agent adapters. Explicit commands and natural language are normalized identically:

```bash
aief run "Implémente EGW-142" --agent codex --intent implement --expect-workflow implement-task --project . --factory /path/to/factory/1.13.0
aief run "Corrige le bug EGW-327" --agent claude-code --project . --factory /path/to/factory/1.7.0
```

Dans l'interface Codex, l'entrée native correspondante est `$implement
EGW-142`. `/implement` est réservé à l'adapter Claude Code. Voir
[`docs/27-codex-usage.md`](docs/27-codex-usage.md).

See `docs/14-universal-runtime.md` for task intake, execution, gates, handoff and complete examples.

## Project adoption

A project does **not** clone the Factory into its repositories. The Factory is installed once on the developer workstation, for example:

```text
~/.gad/ai-engineering-factory/0.1.0/
```

The project clones only `templates/project/`, then adapts `.ai/project.yaml`, `.ai/repository-map.yaml` and its context.

See `examples/emmany/` for a poly-repository example.

For a complete, commented installation procedure covering clone, CLI, adapters,
project configuration, validation and optional MCP activation, see
`docs/22-project-installation-guide.md`.

## Stability

`v1alpha1` means the contracts are explicit and usable for pilots, but may still evolve before a stable `v1` contract.
