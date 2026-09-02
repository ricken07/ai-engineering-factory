# Codex Runtime Protocol

This protocol is mandatory for every request the Activation Gate in
`bootstrap.md` routes to the Factory: a native Skill (`$implement`, `$fix`,
...) always routes here; natural language routes here only after the
`activation.mode` check has been satisfied (explicit human confirmation under
`auto`, or declared inapplicable and handled directly under `manual`). The
adapter must not simulate workflow orchestration in conversation.

## Start or resume

1. Locate the nearest `.ai/project.yaml` from the current working directory.
2. Resolve `factory.homeEnv`, then verify that the referenced Factory contains
   the exact `factory.version` requested by the project.
   Resolve the environment variable once, validate the resulting absolute path,
   then place that literal path in later commands.
3. Preserve the user's complete request. For a native Skill, also pass its
   canonical Factory intent and expected workflow as separate deterministic
   arguments; never rely on the natural-language title to recover the intent.
4. Start the shared Runtime boundary:

   ```bash
   aief run "<complete-user-request>" \
     --agent codex \
     --intent "<canonical-intent>" \
     --expect-workflow "<expected-workflow>" \
     --project "<workspace-root>" \
     --factory "<resolved-factory-home>"
   ```

   For a free-text request routed here under `activation.mode: auto`, add
   `--activation-confirmed` — only once the developer has given an explicit
   yes to the Activation Gate question. Never pass it speculatively, and
   never pass it for `activation.mode: manual` (free text never reaches this
   protocol under that mode). A native Skill never needs this flag.

5. Treat the command as successful only when stdout contains a concrete
   `runtimeReceipt`, `execution`, `intent`, `workflow` and `nextPhase`. Verify
   that `intent` and `workflow.id` exactly match the native Skill. A textual
   statement such as “Task normalized” is never a Runtime receipt.
6. If compatible active state already exists, inspect it and resume through its
   persisted Execution; never infer progress from chat history.

Before this receipt exists, do not inspect implementation code beyond the
minimum project/bootstrap files and do not invoke `Write`, `Edit`, notebook
mutation or a source-changing shell command. Fail closed when `aief run` is not
executed, fails, or returns a different workflow.

## Execute the phase loop

For the returned execution ID:

1. Call `aief execution next <execution-id> --project <workspace-root>
   --factory <resolved-factory-home> --json`.
2. Stop immediately when the Runtime reports `waiting-approval`, `blocked`,
   `failed`, `cancelled` or `completed`.
3. For a runnable phase, verify that the returned phase is the only operation
   being performed. Source mutation is forbidden unless the returned Skill is
   `implement-change` and the Runtime status is runnable.
4. Read the exact `skillContract.manifest`, `skillContract.instructions` and
   `skillContract.outputSchema` paths returned by the Runtime. Core Skills are
   contracts and must never be invoked through an agent-native Skill mechanism.
   In particular, do not invoke native `understand`, `analyze-impact` or
   `create-plan` Skills.
5. Use Codex for only the agentic work required by that Skill.
6. Write the structured phase artifact under the current task/execution runtime
   directory and submit it with the exact deterministic form:

   ```bash
   aief execution complete-phase "<execution-id>" \
     --output "<absolute-artifact-path>" \
     --project "<absolute-workspace-root>" \
     --factory "<absolute-factory-home>" \
     --json
   ```

   `--output` is mandatory. Do not pass artifact content through shell
   redirection, interpolation or a heredoc.
7. Repeat from `execution next`; never skip or reorder a phase locally.

For `analyze-impact`, persist every impacted project repository in
`details.repositories` using the exact identifiers from `.ai/project.yaml`.
Mutating workflows cannot leave this list empty. Never add repositories by
editing `task.yaml`, `execution.yaml` or a completed artifact: correct the
current phase output before submitting it to `complete-phase`.

Never claim that a Task, Execution, phase, plan or approval exists unless its
persisted Runtime identifier or artifact path was returned by `aief`.

Every subsequent `aief` command must include both `--project
"<workspace-root>"` and `--factory "<resolved-factory-home>"`. A missing
Factory manifest is a fatal configuration error. Never repair it by copying,
linking or generating `factory.yaml` inside the project workspace.

Commands must contain literal, already-resolved arguments. Never embed `$(pwd)`,
`${GAD_AI_FACTORY_HOME}`, `${VAR:-fallback}`, `cd &&`, environment assignment
prefixes, command substitutions, pipes or redirections in an `aief` invocation.
Do not probe `aief --help` during the workflow: the exact syntax is defined by
this protocol.

For `validate-change`, use `aief execution profile-validation`; do not construct
stack commands in the adapter. For governed actions, wait for the Runtime gate
and use `aief execution approve` only after explicit human approval.

All CLI arguments derived from user input must be passed as discrete, safely
quoted arguments. Do not use `eval`, shell concatenation or `shell=True`.
