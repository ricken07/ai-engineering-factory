---
name: revise
description: Continue an AI Engineering Factory execution after the human asked with /revise for changes to the plan waiting at its gate. Use only when the human invokes /revise; never on your own initiative.
---

# Revise

The human typed `/revise [<execution-id>] <changes to make to the plan>`.
Asking for changes to a plan at its gate is the human's decision, and only
the Runtime records it: you never run a decision command. The Runtime refuses
any decision relayed by an agent session and keeps the refusal as evidence.

1. When your context contains a line starting with `AIEF: the human asked`,
   the Claude Code approval hook delivered this message to the Runtime, which
   recorded the decision and reopened the planning phase. Continue the
   execution protocol with `aief execution next <execution-id>`: the phase
   brief has a **Plan revision** section with the changes to make. Write the
   revised plan, complete the phase, and tell the human the revised plan
   waits for them at the same gate.
2. Otherwise the hook did not deliver the message, so nothing was decided and
   the plan still waits. Tell the human, and give them the command to run in
   their own terminal: `aief execution revise-plan <execution-id> --feedback
   "<changes>" --approver <name>`. Then wait.

Discussing the plan with the human before they decide is fine: answer their
questions and explain trade-offs, but do not rewrite the plan until the
Runtime reopened the planning phase. See
`$AI_FACTORY_HOME/docs/34-human-approval.md`.
