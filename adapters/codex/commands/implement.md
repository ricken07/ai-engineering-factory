# `$implement` — Codex

`/implement` is not a native Codex command. The `/` prefix is reserved for
the client's built-in commands; the Factory Skill is invoked with
`$implement` or with an equivalent natural-language request.

Execute `aief run` with `--intent implement --expect-workflow implement-task`
and use the returned execution ID. The user's input remains the active task.

Resolve the current Factory project, respect every policy and gate, and do not bypass workflow phases.
Do not inspect implementation code or modify files before the Runtime reaches
the `implement-change` Skill.
