# AI Engineering Factory Project

This project is governed by the AI Engineering Factory.

## Bootstrap

Before engineering work:

1. Read `.ai/project.yaml` and `.ai/repository-map.yaml`.
2. Resolve the pinned Factory version from the configured Factory home.
3. Use its adapter for the active agent and its Core workflow for the user intent.
4. Resolve policies before side effects and stop at unmet gates.
5. Load project context, decisions and memory progressively after impact analysis.
6. Resolve abstract capabilities through project-selected integrations and available MCP bindings.
7. Create or resume agent-neutral state under `.ai/runtime/`.
8. Never treat session observations as authoritative project knowledge.
9. Preserve task evidence, bounded recovery and handoff state.
10. Promote durable knowledge only through the approved Factory workflow.

See `.ai/README.md` for the project AI configuration. Do not duplicate Factory workflows, profiles, provider instructions or stack commands here.

Supported intents: `analyze`, `implement`, `fix`, `refactor`, `test`, `review`, `document`, `promote`.
