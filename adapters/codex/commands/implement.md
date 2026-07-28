# `$implement` — Codex

`/implement` n'est pas une commande native Codex. Le préfixe `/` est réservé
aux commandes intégrées du client ; le Skill Factory s'invoque avec
`$implement` ou par une demande équivalente en langage naturel.

Execute `aief run` with `--intent implement --expect-workflow implement-task`
and use the returned execution ID. The user's input remains the active task.

Resolve the current Factory project, respect every policy and gate, and do not bypass workflow phases.
Do not inspect implementation code or modify files before the Runtime reaches
the `implement-change` Skill.
