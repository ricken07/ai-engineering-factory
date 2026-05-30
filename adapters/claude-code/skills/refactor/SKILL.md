---
name: refactor
description: Execute the AI Engineering Factory refactor-code workflow for the current project. Use when the user requests refactor work or invokes /refactor.
---

# Refactor

1. Locate the nearest workspace `.ai/project.yaml`.
2. Resolve its pinned Factory version; fail closed if unavailable or incompatible.
3. Load Factory workflow `refactor-code`, referenced policies, standards and Core Skills.
4. Normalize the user input as the active task without inventing requirements.
5. Resolve project profiles, provider integrations and available MCP bindings.
6. Create or resume agent-neutral task and execution state under the configured runtime root.
7. Execute mandatory phases in order, enforce PolicyDecision and stop at unmet gates.
8. Persist structured evidence and use bounded recovery without expanding task scope.

Do not duplicate or reinterpret Core procedures. Project truth comes from the project `.ai/` sources, not this adapter skill or session memory.
