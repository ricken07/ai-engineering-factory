---
name: approve
description: Continue an AI Engineering Factory execution after the human approved its gate with $approve. Use only when the human invokes $approve; never on your own initiative.
---

# Approve

The human typed `$approve [<execution-id>] [<gate>]`. The approval is the human's
decision, and only the Runtime records it: you never run an approval command.
The Runtime refuses any approval relayed by an agent session and keeps the
refusal as evidence.

1. When your context contains a line starting with `AIEF: the human approved`,
   the Codex approval hook delivered this message to the Runtime, which
   recorded the approval. Continue the execution protocol with
   `aief execution next <execution-id>`.
2. Otherwise the hook did not deliver the message, so nothing was approved.
   Tell the human, and give them both ways to approve:
   - make the hook active, then type `$approve` again: `aief setup-adapter
     codex --execute` (the command), `aief approval install-hook --agent
     codex --project .` (the hook in `.codex/hooks.json`), and trust the hook with /hooks;
   - or run, in their own terminal:
     `aief execution approve-policy <execution-id> <gate> --approver <name>`
     (`aief execution approve <execution-id> --approver <name>` for a phase
     approval).
   Then wait.

See `$AI_FACTORY_HOME/docs/34-human-approval.md`.
