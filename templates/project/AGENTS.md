# AI Engineering Factory Project

This project is governed by the AI Engineering Factory.

## Bootstrap

Before engineering work:

1. Route every engineering request, including free text, through the installed
   Factory adapter and its mandatory Runtime protocol. Do not ask the developer
   to invoke `aief run`.
2. Do not claim that a Task or Execution exists without a concrete Runtime
   receipt and execution ID. Do not modify source files until `execution next`
   returns the `implement-change` Skill.
3. Read `.ai/project.yaml` and `.ai/repository-map.yaml`.
4. Resolve the pinned Factory version from the configured Factory home.
5. Consume Core Skills only through the `skillContract` paths returned by
   `aief execution next`; never invoke them as native agent skills and never
   create a project-local `factory.yaml`.
6. Invoke `aief` with literal absolute `--project` and `--factory` values. Do
   not submit `$(pwd)`, `${...}`, fallbacks, pipes or chained shell commands.
7. Use its adapter for the active agent and its Core workflow for the user intent.
8. Resolve policies before side effects and stop at unmet gates.
9. Load project context, decisions and memory progressively after impact analysis.
10. Resolve abstract capabilities through project-selected integrations and available MCP bindings.
11. Create or resume agent-neutral state under `.ai/runtime/`.
12. Never treat session observations as authoritative project knowledge.
13. Preserve task evidence, bounded recovery and handoff state.
14. Promote durable knowledge only through the approved Factory workflow.

See `.ai/README.md` for the project AI configuration. Do not duplicate Factory workflows, profiles, provider instructions or stack commands here.

Supported intents: `analyze`, `implement`, `fix`, `refactor`, `test`, `review`, `document`, `promote`.

Daily entry point: start Codex or Claude Code from this workspace root, then use
an agent-native intent (`$implement` or `/implement`) or natural language.
