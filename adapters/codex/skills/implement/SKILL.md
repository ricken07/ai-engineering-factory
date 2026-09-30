---
name: implement
description: Execute the AI Engineering Factory implement-task workflow for the current project. Use when the user requests implement work or invokes $implement.
---

# Implement

Before reading implementation code or changing files, execute the mandatory
Codex Runtime Protocol at `$AI_FACTORY_HOME/adapters/codex/runtime-protocol.md`
with:

```bash
aief run "<complete-user-request>" --agent codex \
  --agent-session "codex:<session-id>" \
  --intent implement --expect-workflow implement-task \
  --project "<workspace-root>" --factory "<resolved-factory-home>"
```

Do not continue without the real Runtime receipt and execution ID. Never replace
this command with a conversational claim that the Task was normalized.
Replace every placeholder with a previously resolved literal absolute path.
Do not send `$(pwd)`, `${AI_FACTORY_HOME}` or a shell fallback to the shell.

1. Locate the nearest workspace `.ai/project.yaml`.
2. Resolve its pinned Factory version; fail closed if unavailable or incompatible.
3. Load Factory workflow `implement-task`, referenced policies, standards and Core Skills.
4. Normalize the user input as the active task without inventing requirements.
5. Resolve project profiles, provider integrations and available MCP bindings.
6. Create or resume agent-neutral task and execution state under the configured runtime root.
7. Execute mandatory phases in order through `aief execution next`; source
   mutation is forbidden until it returns the `implement-change` Skill.
8. Persist structured evidence and use bounded recovery without expanding task scope.

Do not duplicate or reinterpret Core procedures. Project truth comes from the project `.ai/` sources, not this adapter skill or session memory.
