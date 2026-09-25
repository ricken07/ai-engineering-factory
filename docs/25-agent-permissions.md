# 25 — Agent Permissions for Claude Code and Codex

Native permission files make Factory daily execution smooth without disabling human control. They are provided by the project
template:

```text
.claude/settings.json
.codex/config.toml
.codex/rules/factory.rules
```

They never replace Factory policies. An action is possible only if all three layers authorize it:

```text
Factory PolicyDecision
        ∩
native Claude/Codex permission
        ∩
sandbox and system rights
        ↓
action actually authorized
```

A native permission can thus prevent an action authorized by the Factory,
but it must never expand the autonomy calculated by the Factory.

## 1. Common Classification

| Class | Examples | Behavior |
| --- | --- | --- |
| Allowed | read, `aief validate`, Execution inspection, Git state | without repetitive confirmation |
| Confirmation | gate, external ticket creation, commit/push, branch/worktree mutation, validation outside sandbox | ask human |
| Forbidden | force-push, hard reset, destructive git clean, secret read | block |

The shared model is deliberately conservative. An MCP provider's permissions are
configured separately and remain subject to the same policies.

The baseline authorizes `Bash(aief *)` so ordinary Runtime operations
do not request permission at each phase. Specific `ask` rules for approvals, external writes, synchronizations and Git mutations are
evaluated before this general rule and remain interactive. Destructive prohibitions remain priority.

## 2. Claude Code

Claude Code loads shared configuration from
`.claude/settings.json`. The template uses `acceptEdits` to avoid confirmation at each local modification, then frames Bash commands
with `allow`, `ask` and `deny`.

The local file `.claude/settings.local.json` is ignored by Git. It serves workstation-specific adjustments, never to bypass organizational rules.
It can also provide `GAD_AI_FACTORY_HOME` to Claude when the client is
launched from an IDE or application that does not inherit the shell:

```json
{
  "env": {
    "GAD_AI_FACTORY_HOME": "<ABSOLUTE_FACTORY_INSTALLATION>"
  }
}
```

Merge this key with existing local permissions and never
commit this file.

Verification from Claude Code:

```text
/permissions
```

Verify that project rules are loaded, then start with `/analyze`.
Do not use `bypassPermissions` or `--dangerously-skip-permissions` for normal Factory operation.

Factory commands must be simple and literal:

```bash
aief execution next 20260816T120000Z-example \
  --project "/absolute/project" \
  --factory "/absolute/factory"
```

Mutating phase submissions also carry the active lease owner:

```bash
aief execution complete-phase 20260816T120000Z-example \
  --output "/absolute/project/.ai/runtime/executions/20260816T120000Z-example/output.yaml" \
  --owner "claude-code:<session-id>" \
  --project "/absolute/project" \
  --factory "/absolute/factory"
```

The initial `--agent-session` label is only `OBSERVED`. The owner becomes a
`TRUSTED` Runtime session only while the matching Execution lease is active.

Avoid in the command submitted to Bash:

```bash
$(pwd)
${GAD_AI_FACTORY_HOME}
${GAD_AI_FACTORY_HOME:-.}
cd ... && aief ...
```

The adapter first resolves paths, then reuses their literal absolute values.
Substitutions and compound commands are harder to validate by native permissions and cause additional prompts.

## 3. Codex

Codex loads `.codex/config.toml` and `.codex/rules/` only after the
repository has been declared trusted. The template requires:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false
```

Code and `.ai/runtime/` remain modifiable in the workspace. A command
requiring out-of-sandbox access triggers the rules in
`.codex/rules/factory.rules`. `forbidden` rules override `prompt`,
which overrides `allow`.

Test rules before adoption:

```bash
codex execpolicy check --pretty \
  --rules .codex/rules/factory.rules \
  -- git reset --hard HEAD

codex execpolicy check --pretty \
  --rules .codex/rules/factory.rules \
  -- aief execution approve exec-example
```

The first result should be `forbidden`, the second `prompt`.

## 4. Add Project-Specific Commands

The generic template assumes no stack. After Profile activation,
the project can add only the validations truly needed.

Claude Code, Maven example:

```json
"Bash(./mvnw verify *)"
```

Claude Code, Flutter example:

```json
"Bash(flutter analyze *)",
"Bash(flutter test *)"
```

Codex, Maven example to add in a
`.codex/rules/project-validations.rules` file:

```python
prefix_rule(
    pattern = ["./mvnw", "verify"],
    decision = "allow",
    justification = "Maven validation declared by repository Profile",
    match = ["./mvnw verify"],
)
```

Before authorizing a command:

1. verify it comes from a Profile or validated project convention;
2. use a specific prefix, never `Bash` or `npm` globally;
3. do not authorize destructive or publishing options;
4. add a test example in the Codex rule;
5. have the change reviewed like a security modification.

## 5. Actions That Must Remain Interactive

Even with project autonomy L3 or L4, shared native files must not
auto-approve:

- a Factory human gate;
- external task creation or linking;
- commit, push, merge or rebase;
- workspace preparation or rollback;
- adding an MCP or elevating its permissions;
- any command requiring network or out-of-workspace access not documented.

Policy can refuse the action after native confirmation. The reverse is not true:
confirming a Claude/Codex window does not validate a Factory gate.

Likewise, native configuration is not automatically `ENFORCED` evidence. A
known capability may be `ENFORCEABLE`; an assumed external configuration is
`UNVERIFIED`; absence is `UNAVAILABLE`. Only execution-bound verification can
promote the applicable Runtime path to `ENFORCED`.

Adapter labels are recorded as `OBSERVED`. A session becomes `TRUSTED` for
review-independence comparison only through an active matching Runtime lease.
Text written in `review.yaml` remains artifact-declared and cannot authenticate
the reviewer.

## Git Identity and Commit Messages

The Factory does not sign commits on behalf of the agent. When a commit is
authorized, Claude or Codex can prepare the message per organizational conventions,
but Git must use the profile already configured by the developer:

```bash
git config user.name
git config user.email
git config --get commit.gpgsign
git config --get user.signingkey
```

The agent must not use `--author`, `--reset-author`, `GIT_AUTHOR_*`,
`GIT_COMMITTER_*`, or replace the signing key. It must not automatically add
a signature or `Co-authored-by` mention representing the agent. Identity and
signing state are recorded before commit; missing or different identity from the developer
profile blocks the `before-commit` gate.

## 6. Installation and Control

`aief init` copies files with the rest of the template. For an already-configured
project, copy and review them without overwriting existing settings:

```bash
mkdir -p .claude .codex/rules
cp "<FACTORY_HOME>/templates/project/.claude/settings.json" .claude/settings.json
cp "<FACTORY_HOME>/templates/project/.codex/config.toml" .codex/config.toml
cp "<FACTORY_HOME>/templates/project/.codex/rules/factory.rules" .codex/rules/factory.rules
```

Then:

```bash
aief validate . --factory "<FACTORY_HOME>"
git diff -- .claude .codex .gitignore
```

Restart Claude Code or Codex: both clients discover their
project configuration at startup. Start with a non-mutating analysis, then
a small local modification with maximum autonomy L2.

## 7. Native Sources

- Claude Code — settings and scopes: <https://code.claude.com/docs/en/settings>
- Codex — configuration: <https://developers.openai.com/codex/config-reference>
- Codex — command rules: <https://developers.openai.com/codex/rules>
