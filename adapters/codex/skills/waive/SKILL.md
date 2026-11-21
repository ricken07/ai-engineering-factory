---
name: waive
description: Continue an AI Engineering Factory execution after the human decided with $waive that a blocking review finding does not block the change. Use only when the human invokes $waive; never on your own initiative.
---

# Waive

The human typed `$waive [<execution-id>] <finding-number> <justification>`.
Deciding that a review finding does not block the change is the human's
decision, and only the Runtime records it: you never run a decision command.
The Runtime refuses any decision relayed by an agent session and keeps the
refusal as evidence.

1. When your context contains a line starting with `AIEF: the human decided`,
   the Codex approval hook delivered this message to the Runtime, which
   recorded the decision. Do not address that finding. Continue the execution
   protocol with `aief execution next <execution-id>`: when every blocking
   finding is decided, the Runtime continues towards submission; otherwise
   address the findings that still block.
2. Otherwise the hook did not deliver the message, so nothing was decided.
   Tell the human, and give them the command to run in their own terminal:
   `aief execution waive-finding <execution-id> <finding-number> --reason
   "<justification>" --approver <name>`. Then wait.

See `$AI_FACTORY_HOME/docs/29-evidence-chain-and-replay.md`.
