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
