# Agent Adapter Model

Adapters translate Factory semantics into an agent runtime. They must not fork or redefine Core workflows.

Required adapter responsibilities:

1. locate `.ai/project.yaml`,
2. resolve the pinned Factory version,
3. load the selected workflow and policies,
4. apply progressive context loading,
5. respect PolicyDecision permissions/gates,
6. produce Factory-compatible artifacts/handoffs,
7. avoid treating session memory as project truth.

Adapters have three surfaces: user-level skill installation during onboarding, project bootstrap at session start, and capability/tool translation during task execution. See `docs/13-agent-adapters-and-mcp.md`.

Adapter-native skills are intentionally thin. They resolve a pinned Core workflow and must never copy its phases or Core Skill instructions.

Since v1.4.0 every adapter enters the same executable boundary through `aief run`. The adapter supplies the untouched user request and its identity, then follows `aief execution next` and submits schema-valid phase results. Intent normalization, workflow compilation, state, gates and handoff must never be reimplemented in an agent plug-in.

For `validate-change`, adapters must call the shared profile-validation operation. Repository selection, profile inheritance, command construction, authorization and result persistence belong to the Runtime, ensuring identical behavior across agents.
