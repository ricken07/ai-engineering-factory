# Codex Runtime Protocol

This protocol is mandatory for every Factory engineering request, whether the
user invokes `$implement`, `$fix`, another native Skill, or uses natural
language. The adapter must not simulate workflow orchestration in conversation.

## Start or resume

1. Locate the nearest `.ai/project.yaml` from the current working directory.
2. Resolve `factory.homeEnv`, then verify that the referenced Factory contains
   the exact `factory.version` requested by the project.
3. Preserve the user's complete request without rewriting it into a command.
4. Start the shared Runtime boundary:

   ```bash
   aief run "<complete-user-request>" \
     --agent codex \
     --project "<workspace-root>" \
     --factory "<resolved-factory-home>"
   ```

5. If compatible active state already exists, inspect it and resume through its
   persisted Execution; never infer progress from chat history.

## Execute the phase loop

For the returned execution ID:

1. Call `aief execution next <execution-id> --project <workspace-root>
   --factory <resolved-factory-home> --json`.
2. Stop immediately when the Runtime reports `waiting-approval`, `blocked`,
   `failed`, `cancelled` or `completed`.
3. For a runnable phase, resolve and follow the referenced Core Skill contract,
   instructions, schemas, policies and effective engineering context.
4. Use Codex for only the agentic work required by that Skill.
5. Write the structured phase artifact under the current task/execution runtime
   directory and submit it with `aief execution complete-phase`.
6. Repeat from `execution next`; never skip or reorder a phase locally.

For `validate-change`, use `aief execution profile-validation`; do not construct
stack commands in the adapter. For governed actions, wait for the Runtime gate
and use `aief execution approve` only after explicit human approval.

All CLI arguments derived from user input must be passed as discrete, safely
quoted arguments. Do not use `eval`, shell concatenation or `shell=True`.

