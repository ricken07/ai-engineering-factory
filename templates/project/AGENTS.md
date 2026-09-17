# AI Engineering Factory Project

This project is governed by the AI Engineering Factory.

## Bootstrap

Before engineering work:

1. Route every native command (`/implement`, `$implement`, ...) through the
   installed Factory adapter and its mandatory Runtime protocol; it always
   activates the Factory for its own execution. Do not ask the developer to
   invoke `aief run`.
2. For free text, first resolve `activation.mode` from `.ai/project.yaml`:
   - `auto` (default): ask the developer whether this request should be
     routed through the Factory, and only route it — through the same
     mandatory protocol — after an explicit yes. Otherwise handle the
     request directly, without the Factory.
   - `manual`: never route free text through the Factory. Only a native
     command activates it, and only for that execution. Handle every other
     request directly.
3. Do not claim that a Task or Execution exists without a concrete Runtime
   receipt and execution ID. Do not modify source files until `execution next`
   returns the `implement-change` Skill.
4. Read `.ai/project.yaml` and `.ai/repository-map.yaml`.
5. Resolve the pinned Factory version from the configured Factory home.
6. Consume Core Skills only through the `skillContract` paths returned by
   `aief execution next`; never invoke them as native agent skills and never
   create a project-local `factory.yaml`.
7. Invoke `aief` with literal absolute `--project` and `--factory` values. Do
   not submit `$(pwd)`, `${...}`, fallbacks, pipes or chained shell commands.
8. Use its adapter for the active agent and its Core workflow for the user intent.
9. Resolve policies before side effects and stop at unmet gates.
10. Load project context, decisions and memory progressively after impact analysis.
11. Resolve abstract capabilities through project-selected integrations and available MCP bindings.
12. Create or resume agent-neutral state under `.ai/runtime/`.
13. Pass an adapter session identifier, acquire the Execution lease with the
    same owner before mutation, and pass that owner to mutating transitions;
    the session label alone is not trusted.
14. Never treat session observations as authoritative project knowledge.
15. Preserve task evidence, bounded recovery and handoff state.
16. Promote durable knowledge only through the approved Factory workflow.

See `.ai/README.md` for the project AI configuration. Do not duplicate Factory workflows, profiles, provider instructions or stack commands here.

Supported intents: `analyze`, `implement`, `fix`, `refactor`, `test`, `review`, `document`, `promote`.

Daily entry point: start Codex or Claude Code from this workspace root, then use
an agent-native intent (`$implement` or `/implement`) or natural language.
