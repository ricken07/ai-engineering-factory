# 23 — First Steps in a Factory Project

This guide begins after the installation described in
[`22-project-installation-guide.md`](22-project-installation-guide.md).
Expected permission prompts and project templates are detailed in
[`25-agent-permissions.md`](25-agent-permissions.md).

## 1. What the Developer Launches

The developer starts Claude Code or Codex from the root containing
`.ai/project.yaml`:

```bash
cd "<PROJECT_ROOT>"

# A Codex session
codex

# Or a Claude Code session
claude
```

They do not run `aief run`. The installed adapter does it automatically and drives
the Runtime loop on behalf of the agent.

## 2. Native Command or Free Text

Native commands make intent explicit:

| Intent | Codex | Claude Code |
| --- | --- | --- |
| Analyze | `$analyze TASK-123` | `/analyze TASK-123` |
| Implement | `$implement TASK-123` | `/implement TASK-123` |
| Fix | `$fix TASK-123` | `/fix TASK-123` |
| Refactor | `$refactor ComponentName` | `/refactor ComponentName` |
| Test | `$test TASK-123` | `/test TASK-123` |
| Review | `$review CHANGE-123` | `/review CHANGE-123` |
| Document | `$document TASK-123` | `/document TASK-123` |

Free text is equivalent:

```text
Implement TASK-123.
Fix the bug where a FAILED transaction remains PENDING.
Refactor PaymentOrchestrator without changing its behavior.
Analyze learning continuity without modifying the code.
```

The adapter preserves the complete request. The Runtime determines intent, creates
a local Task or resolves the external reference, then selects the workflow.

For a native Skill, the adapter also transmits the intent and expected workflow
with `--intent` and `--expect-workflow`. Before any detailed analysis or
modification, the session must display a real Runtime receipt containing at least:

```yaml
runtimeReceipt: created
execution: <execution-id>
intent: implement
workflow:
  id: implement-task
nextPhase: understand
taskLog: <workspace>/.ai/runtime/tasks/<task-id>/events.jsonl
```

`Successfully loaded skill` only means the agent has loaded its
instructions. A phrase like `Task normalized` without receipt or Execution is
not a Factory execution and must trigger a clean shutdown.

The log can be consulted during or after execution:

```bash
aief task log <task-id> \
  --project "$PROJECT_ROOT" \
  --factory "$GAD_AI_FACTORY_HOME"
```

It allows verification of the actual persisted trajectory: intent,
workflow, phases, artifacts, policy decisions, gates, workspace and
validations. See [`26-task-execution-log.md`](26-task-execution-log.md).

## 3. What Happens Automatically

```text
User request
  ↓
Agent skill/intent
  ↓
aief run (internal call)
  ↓
Task + Execution persisted in .ai/runtime
  ↓
execution next
  ↓
Core Skill + effective engineering context
  ↓
Claude/Codex performs agentic work
  ↓
structured artifact + complete-phase
  ↓
next phase, gate, or completion
```

The adapter does not choose phase order, autonomy, or validation commands.
These decisions belong to the common Runtime.

## 4. First Recommended Scenario: Analysis Only

In Codex:

```text
$analyze Analyze the current architecture, verify documents against code
and tests, and modify no files.
```

In Claude Code:

```text
/analyze Analyze the current architecture, verify documents against code
and tests, and modify no files.
```

Or, in either agent:

```text
Analyze the current architecture, verify documents against code and
tests, and modify no files.
```

Expected result: a local Task, an `analyze-task` Execution, structured artifacts
and no code modifications.

## 5. Second Scenario: Small Local Modification

After validating the previous scenario:

```text
Add missing tests for <specific behavior>. Do not change functional
behavior and stop before any commit.
```

With maximum autonomy `L2`, the agent can analyze, modify locally and
test. It cannot push, open an MR or create an external task.

## 6. Scenario Without MCP

Explicitly configure the project so that local Factory traceability is
the reference system:

```yaml
integrations: {}
taskTracking:
  mode: local
```

Without `task-provider`, do not provide a reference requiring
external lookup. Provide the complete request or a local document reference:

```text
Analyze the priorities described in docs/AUDIT.md and verify their actual state in
the code. Modify no files.
```

The Factory creates a local Task. Even if risk or repository count
makes the tracking level `required`, the Task, Execution, artifacts and
log `.ai/runtime/tasks/<task-id>/events.jsonl` satisfy that requirement.
No provider is resolved.

With `taskTracking.mode: external`, behavior remains strict: a `required`
requirement blocks until an external reference is linked. The Runtime never
automatically switches between modes.

## 7. Gates and User Questions

When the Runtime requires human validation, the agent must:

1. stop Execution progression;
2. present the phase, action, and risk involved;
3. ask for an explicit decision;
4. record approval or rejection;
5. resume the same Execution, without creating a new one.

Responding in natural language is sufficient. The developer does not call
`aief execution approve` themselves: the adapter translates their decision.

## 8. Resumption by Another Agent

If Claude Code is interrupted:

```bash
cd "<PROJECT_ROOT>"
codex
```

Then:

```text
Resume the active task using the persisted Factory state.
```

Codex must read `.ai/runtime/`, verify Git state and resume the next
phase declared by the Runtime. The Claude conversation is never a necessary
source of truth for this resumption.

## 9. Resuming After a Factory Upgrade

A session that has already loaded a Skill may retain its old
instructions. After a Runtime, protocol, or Skill upgrade:

1. stop current action before any new modification;
2. exit Claude Code or Codex completely;
3. verify the CLI exposes new options;
4. verify the installed Skill points to the expected Factory;
5. relaunch the agent from the workspace root;
6. invoke intent again and check the Runtime receipt.

```bash
aief run --help | grep -- ‘--expect-workflow’
aief task --help | grep log

test -f "$HOME/.claude/skills/implement/SKILL.md"
# or: test -f "$HOME/.agents/skills/implement/SKILL.md"

cd "$PROJECT_ROOT"
claude
# or: codex
```

In the new session, use agent-specific syntax:

```text
Codex      $implement Feature 1.1 — Fix the three broken contracts
Claude     /implement Feature 1.1 — Fix the three broken contracts
```

The receipt must contain `execution`, `intent`, `workflow`, `nextPhase` and
`taskLog`. If the agent only displays `Successfully loaded skill` or claims
the Task is normalized without a receipt, stop execution.

Commands shown in permission requests must contain literal absolute paths. This
command intentionally triggers a prompt because Claude cannot parse it statically:

```bash
aief execution complete-phase <id> \
  --project "$(pwd)" \
  --factory "${GAD_AI_FACTORY_HOME}"
```

The correct form is:

```bash
aief execution complete-phase <id> \
  --output "/absolute/project/.ai/runtime/executions/<id>/phase-output.yaml" \
  --project "/absolute/project" \
  --factory "/absolute/factory" \
  --json
```

The detailed Codex journey, including `$implement` diagnostics, is described
in [`27-codex-usage.md`](27-codex-usage.md).

If Claude still proposes `$(pwd)` or `${...}`, deny permission, stop
the session and relaunch it after Skill upgrade.

If the agent indicates the Factory is not configured, check in its own
session:

```bash
printenv GAD_AI_FACTORY_HOME
test -f "$GAD_AI_FACTORY_HOME/factory.yaml"
```

The presence of the export in `.zshrc` does not prove a process launched from
an IDE, graphical application, or old session inherited it. Exit the agent,
reload the environment in the terminal, then relaunch from that
same terminal. See the section "Making the Factory Visible to the Agent Process"
in the [installation guide](22-project-installation-guide.md).

### Workspace Already Modified by Old Session

Do not delete, stash, or automatically incorporate the affected files.
Keep them as unattributed local modifications, relaunch the new
Execution and let Workspace Safety detect them. The Runtime must block
before `implement-change` and request an explicit decision. A native
Claude/Codex confirmation does not count as approval of a Factory gate.

## 10. When to Use `aief` Directly

Only for administration or diagnostics:

```bash
aief validate . --factory "$GAD_AI_FACTORY_HOME"
aief doctor .
aief integrations doctor . --factory "$GAD_AI_FACTORY_HOME"
aief execution inspect <execution-id> --project . --factory "$GAD_AI_FACTORY_HOME"
```

`aief run` remains a low-level interface for adapters, integration
tests and Runtime diagnostics.

## 11. Quick Checklist

Before the first mutating task:

- [ ] the agent was launched from the root containing `.ai/project.yaml`;
- [ ] the skill adapter is installed;
- [ ] `GAD_AI_FACTORY_HOME` resolves the pinned version;
- [ ] the request is passed automatically to the Runtime;
- [ ] an Execution appears in `.ai/runtime/`;
- [ ] the receipt contains `taskLog` and the log begins with `task.normalized`;
- [ ] the agent respects gates and autonomy level;
- [ ] pre-existing developer changes remain intact.
