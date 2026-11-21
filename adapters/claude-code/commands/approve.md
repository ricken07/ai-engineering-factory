# /approve

Record the human's approval of the gate an AI Engineering Factory execution is waiting for.

The human invokes it; the agent never approves on its own. With the approval hook installed in `.claude/settings.json`, the coding agent harness delivers the message to the Runtime before the agent sees it.
