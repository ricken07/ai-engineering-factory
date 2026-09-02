# claude-code Adapter Bootstrap

When operating in a Factory-enabled project:

1. Read `.ai/project.yaml`.
2. Resolve `activation.mode` (default `auto`) to decide whether this request
   executes `adapters/claude-code/runtime-protocol.md`:
   - a native command (`/implement`, `/fix`, ...) always executes it, for
     this execution, regardless of `mode`;
   - free text under `mode: auto` executes it only after asking the
     developer and receiving an explicit yes; otherwise handle the request
     directly, without the Factory;
   - free text under `mode: manual` never executes it; always handle the
     request directly.
   Do not require the developer to invoke `aief` manually.
3. Resolve the pinned Factory version from `$GAD_AI_FACTORY_HOME` (or organization equivalent).
4. Load the requested Core workflow, applicable policies and required skills.
5. Load `.ai/repository-map.yaml` and mandatory project context.
6. Retrieve/understand the active task.
7. Perform impact analysis before loading broad repository context.
8. Resolve risk, autonomy and required gates into a PolicyDecision.
9. After impact analysis, use the Runtime tracking operations; map only the prepared abstract operation to the configured MCP and submit its result without choosing another provider.
10. Stop at tracking gates and let the human select a duplicate or approve creation when required.
11. Execute only actions authorized by the PolicyDecision.
12. Resolve `aief execution engineering-context` for every impacted repository and active Skill; use only that effective subset and never resolve organization inheritance in the adapter.
13. When the active Core Skill is `validate-change`, delegate repository/profile planning and execution to `aief execution profile-validation`; do not reconstruct commands in the adapter.
14. Produce evidence-backed validation, review and traceability artifacts.
15. Promote durable knowledge only under the memory policy.

This adapter does not redefine Core workflow semantics.
