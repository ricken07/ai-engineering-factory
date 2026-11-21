---
name: approve
description: Record the human's approval of the AI Engineering Factory gate an execution is waiting for. Use only when the human invokes /approve; never on your own initiative.
---

# Approve

The human typed `/approve [<execution-id>] [<gate>]`. The approval is the human's
decision: you never approve a gate yourself.

1. When your context contains a line starting with `AIEF: the human approved`,
   the Claude Code approval hook already delivered this message to the Runtime,
   which recorded the approval. Run no approval command; continue the
   execution protocol with `aief execution next <execution-id>`.
2. Otherwise the hook is not active in this project, so the Runtime did not
   see the message. Relay the approval with `aief execution approve-policy
   <execution-id> <gate> --owner "<your lease owner>"` (or `aief execution
   approve` for a phase approval), never with your own identity as
   `--approver`. The Runtime records it as `DECLARED`.
3. When the Runtime refuses a relayed approval (a `critical` risk execution
   requires an `OBSERVED` one), show the human the refusal and the exact
   command to run in their own terminal:
   `aief execution approve-policy <execution-id> <gate> --approver <name>`.
   Wait for them; do not retry.

See `$AI_FACTORY_HOME/docs/34-human-approval.md`.
