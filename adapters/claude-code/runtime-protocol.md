# Claude Code Runtime Protocol

This protocol is mandatory for every request the Activation Gate in
`bootstrap.md` routes to the Factory: a native Skill (`/implement`, `/fix`,
...) always routes here; natural language routes here only after the
`activation.mode` check has been satisfied (explicit human confirmation under
`auto`, or declared inapplicable and handled directly under `manual`). The
adapter must not simulate workflow orchestration in conversation.

## Start or resume

**Resuming an existing Execution always starts with `aief execution next
<execution-id>`.** The Execution may have changed since this session last
acted on it: a review may have returned it to implementation (rework), a
human may have approved a gate, another session may have taken it over or
handed it back. Never infer the next phase, the lease owner or the gate
status from the conversation; act only on what `execution next` returns, and
acquire the lease again with your owner before mutating the Execution.

1. Locate the nearest `.ai/project.yaml` from the current working directory.
2. Resolve `factory.homeEnv`, then verify that the referenced Factory contains
   the exact `factory.version` requested by the project.
   Resolve the environment variable once with `printenv <homeEnv>`, validate the
   resulting absolute path, then place that literal path in later commands.
3. Preserve the user's complete request. For a native Skill, also pass its
   canonical Factory intent and expected workflow as separate deterministic
   arguments; never rely on the natural-language title to recover the intent.
4. Start the shared Runtime boundary:

   ```bash
   aief run "<complete-user-request>" \
     --agent claude-code \
     --agent-session "claude-code:<session-id>" \
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

   `--agent-session` is adapter-observed and does not establish trust. After
   the receipt, acquire the Execution lease with the same owner before any
   mutating phase:

   ```bash
   aief execution lease acquire "<execution-id>" \
     --owner "claude-code:<session-id>" --ttl 300 \
     --project "<workspace-root>" --factory "<resolved-factory-home>"
   ```

   Only an active matching lease binds later producer/reviewer activity to a
   `TRUSTED` session. A free identifier is `OBSERVED`; an artifact-only
   identity is `UNVERIFIED`.

5. Treat the command as successful only when stdout contains a concrete
   `runtimeReceipt`, `execution`, `intent`, `workflow` and `nextPhase`. Verify
   that `intent` and `workflow.id` exactly match the native Skill. A textual
   statement such as “Task normalized” is never a Runtime receipt.
6. If compatible active state already exists, inspect it and resume through its
   persisted Execution; never infer progress from chat history.

Before this receipt exists, do not inspect implementation code beyond the
minimum project/bootstrap files and do not invoke `Write`, `Edit`, notebook
mutation or a source-changing Bash command. Fail closed when `aief run` is not
executed, fails, or returns a different workflow.

## Execute the phase loop

For the returned execution ID:

1. Call `aief execution next <execution-id> --project <workspace-root>
   --factory <resolved-factory-home> --json`.
2. Stop immediately when the Runtime reports `waiting-approval`, `blocked`,
   `failed`, `cancelled` or `completed`.
3. For a runnable phase, verify that the returned phase is the only operation
   being performed. `Write` and `Edit` are forbidden unless the returned Skill
   is `implement-change` and the Runtime status is runnable. When the
   returned phase has `action: propose-change`, the workspace must not change
   either: write the change as patches inside the execution directory, as the
   phase brief describes, check them with `aief execution check-proposal
   <execution-id> --output <draft-output> --owner "claude-code:<session-id>"` until it
   passes, and stop at the `apply-proposal` gate.
4. Read the file at `phaseBrief.path` completely, with no offset or line
   limit, before any other work on the phase. It holds the applicable
   practices and project context documents, each once, for every
   repository of the phase; `engineeringContexts` only lists their
   identifiers. Follow every practice it contains.
5. Read the exact `skillContract.manifest`, `skillContract.instructions` and
   `skillContract.outputSchema` paths returned by the Runtime. When
   `skillContract.outputContracts` is not empty, read each `schema` too: a
   completed output must satisfy every one of them, and the Runtime rejects
   it otherwise. Core Skills are
   contracts and must never be invoked through Claude's native `Skill(...)`
   mechanism. In particular, do not call `Skill(understand)`,
   `Skill(analyze-impact)` or `Skill(create-plan)`.
6. Use Claude Code for only the agentic work required by that Skill.
7. Write the structured phase artifact under the current task/execution runtime
   directory and submit it with the exact deterministic form:

   ```bash
   aief execution complete-phase "<execution-id>" \
     --output "<absolute-artifact-path>" \
     --owner "claude-code:<session-id>" \
     --project "<absolute-workspace-root>" \
     --factory "<absolute-factory-home>" \
     --json
   ```

   `--output` is mandatory. Do not pass artifact content through shell
   redirection, interpolation or a heredoc.
8. Repeat from `execution next`; never skip or reorder a phase locally, and
   never decide the next phase from memory of the conversation.

For handoff, call `aief execution handoff <execution-id> --owner
"claude-code:<session-id>"`; this persists the handoff and releases the lease.
The receiving session acquires the same Execution with its own owner. A review
is `INDEPENDENT` only when another session reviews after the producer's
handoff; the same session under a new owner name yields `UNVERIFIED`, and
the same owner yields `NOT_INDEPENDENT`. When independent review is required,
`complete-phase` refuses any other review: hand off and stop, never take a
new owner name in the same session to review your own change.

When a review does not approve the change, the Runtime reopens the
implementation phase: the reviewer completes its review phase and stops. The
next `execution next` returns the implementation phase whose brief has a
**Rework** section listing the blocking findings; the producer addresses every
one of them, then validation and an independent review run again. Never
change the acceptance criteria to fit the implementation; ask the human when
a criterion itself is wrong.

For research runs, the initial command also supplies
`--experiment-condition L0|L1|L2|L3`, `--repeat-index`,
`--environment-identifier` and, when observable, `--model-identifier`.
Experimental condition is explicit and is never inferred from autonomy or the
Workflow.

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

Commands submitted to Bash must contain literal, already-resolved arguments.
Never use `$(pwd)`, `${AI_FACTORY_HOME}`, `${VAR:-fallback}`, `cd &&`, an
environment assignment prefix, command substitution, pipes or redirections in
an `aief` invocation. These forms are harder for native permission rules to
validate and cause avoidable approval prompts. Do not probe `aief --help` during
the workflow: the exact syntax is defined by this protocol.

For `validate-change`, run `aief execution profile-validation <execution-id>
--execute --owner "claude-code:<session-id>"` with the project and Factory arguments: the
Runtime executes the commands and writes the validation report itself. Never
submit a `validate-change` output with `complete-phase`; the Runtime refuses
it. Do not construct
stack commands in the adapter. For governed actions, wait for the Runtime gate
and never approve a gate yourself: never run `aief execution approve` or
`aief execution approve-policy`. The Runtime refuses an approval relayed by an
agent session at every risk level and records the refusal. Tell the human
which execution and gate wait, and that they approve by typing `/approve` in this
session. When your context then contains `AIEF: the human approved ...`, the
approval hook recorded it: continue with `aief execution next`. Without that
line nothing was approved: give the human the exact `aief execution
approve-policy` (or `aief execution approve`) command to run in their own
terminal, and wait. See `docs/34-human-approval.md`.

When `execution next` reports `blocked` because the current phase's
`recovery.status` is `waiting-user`, do not resolve the question in
conversation alone: read `recovery.question`, present it to the human in this
session, and once answered, submit it with the exact deterministic form:

```bash
aief execution answer-question "<execution-id>" \
  --answer "<the human's exact answer>" \
  --owner "claude-code:<session-id>" \
  --project "<absolute-workspace-root>" \
  --factory "<absolute-factory-home>" \
  --json
```

Resume the phase loop from `execution next` only after this call returns
`running`. Raise such a question yourself with `aief execution ask-user
--question "<precise-question>" [--requires-authority]`; omit
`--requires-authority` only once the phase's recorded attempts satisfy
`recovery.minimumAttempts`. To abandon an Execution instead of continuing it,
call `aief execution cancel "<execution-id>" --reason "<reason>"`; this is a
terminal transition and cannot be undone.

All CLI arguments derived from user input must be passed as discrete, safely
quoted arguments. Do not use `eval`, shell concatenation or `shell=True`.
