# codex Adapter Bootstrap

When operating in a Factory-enabled project:

1. Read `.ai/project.yaml`.
2. Resolve the pinned Factory version from `$GAD_AI_FACTORY_HOME` (or organization equivalent).
3. Load the requested Core workflow, applicable policies and required skills.
4. Load `.ai/repository-map.yaml` and mandatory project context.
5. Retrieve/understand the active task.
6. Perform impact analysis before loading broad repository context.
7. Resolve risk, autonomy and required gates into a PolicyDecision.
8. Execute only actions authorized by that PolicyDecision.
9. When the active Core Skill is `validate-change`, delegate repository/profile planning and execution to `aief execution profile-validation`; do not reconstruct commands in the adapter.
10. Produce evidence-backed validation, review and traceability artifacts.
11. Promote durable knowledge only under the memory policy.

This adapter does not redefine Core workflow semantics.
