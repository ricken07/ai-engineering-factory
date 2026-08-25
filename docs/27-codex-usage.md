# 27 — Using Factory with Codex

This guide describes the complete Codex journey, from adapter installation
to execution diagnosis. The general installation guide is still
[`22-project-installation-guide.md`](22-project-installation-guide.md).

## 1. Syntax to Remember

Codex and Claude Code do not use the same native syntax:

```text
Codex       $implement Feature 1.2 — Distinguish answered/evaluated/correct
Claude      /implement Feature 1.2 — Distinguish answered/evaluated/correct
```

In Codex, `/implement` is invalid. The `/` prefix is reserved for commands
built into the Codex interface. Factory Skills are invoked with
`$`, or simply in natural language:

```text
$fix Fix the status mapping.

Implement Feature 1.2 respecting the Factory workflow.
```

Both formulations must produce the same
`Task → Workflow → Execution`. The native command only clarifies the intent.

## 2. Prepare the Workstation

Define the absolute path to the Factory in the shell profile:

```bash
export GAD_AI_FACTORY_HOME="/absolute/path/to/ai-engineering-factory"
```

Then verify the CLI and the Factory:

```bash
printenv GAD_AI_FACTORY_HOME
aief --help
test -f "$GAD_AI_FACTORY_HOME/factory.yaml"
```

Shell configuration serves onboarding and initial resolution.
During a workflow, the adapter must resolve this value once then provide
`aief` commands with a literal absolute path.

## 3. Install the Codex Adapter

First preview the installation:

```bash
aief setup-adapter codex --factory "$GAD_AI_FACTORY_HOME"
```

Then create the links managed by the Factory:

```bash
aief setup-adapter codex \
  --factory "$GAD_AI_FACTORY_HOME" \
  --execute
```

Skills are exposed in `~/.agents/skills/`. Verify at minimum:

```bash
test -f "$HOME/.agents/skills/implement/SKILL.md"
ls -la "$HOME/.agents/skills/implement"
```

The link must target
`<FACTORY_HOME>/adapters/codex/skills/implement`. Projects do not copy
Skills and adapters do not recopy Core workflows.

Codex discovers Skills at startup. After installation or update,
close the current session completely then open a new one.

## 4. Prepare the Project

From the root containing `.ai/project.yaml`, verify the following files:

```text
AGENTS.md
.ai/project.yaml
.ai/repository-map.yaml
.codex/config.toml
.codex/rules/factory.rules
```

For a project that does not yet have Codex files:

```bash
mkdir -p .codex/rules
cp "$GAD_AI_FACTORY_HOME/templates/project/.codex/config.toml" \
  .codex/config.toml
cp "$GAD_AI_FACTORY_HOME/templates/project/.codex/rules/factory.rules" \
  .codex/rules/factory.rules
```

Review and commit these files with project configuration. Never
place tokens, passwords or secret endpoints in them.

For a project without task manager or MCP, also verify:

```yaml
integrations: {}
taskTracking:
  mode: local
```

`local` keeps all traceability requirements in `.ai/runtime`, even
when policy calculates `required`. `external` instead requires a
`task-provider` and a linked reference. Codex must never decide on its own to
change this mode.

Codex loads a project's `.codex/` configuration only after establishing
trust for that repository. Accept this trust only after
inspecting the repository, `AGENTS.md`, `.codex/config.toml` and the rules.

## 5. Start Codex

Always start from the root of the Factory workspace:

```bash
cd "/absolute/path/to/project"
codex
```

In the session, browse available Skills with `/skills`, then launch
a first non-mutating analysis:

```text
$analyze Analyze the current architecture without modifying the code.
```

Available intents are:

| Intent | Codex invocation | Factory workflow |
| --- | --- | --- |
| Analysis | `$analyze ...` | `analyze-task` |
| Implementation | `$implement ...` | `implement-task` |
| Fix | `$fix ...` | `fix-bug` |
| Refactoring | `$refactor ...` | `refactor-code` |
| Tests | `$test ...` | `add-tests` |
| Review | `$review ...` | `review-change` |
| Documentation | `$document ...` | `update-documentation` |
| Capitalization | `$promote ...` | `promote-knowledge` |

## 6. What the Adapter Must Do

For `$implement`, the Codex Skill calls the common Runtime with the intent and
expected workflow:

```text
$implement <request>
  ↓
Codex Skill implement
  ↓
aief run --agent codex --intent implement
         --expect-workflow implement-task
  ↓
persistent Runtime receipt
  ↓
execution next / complete-phase loop
```

Before any deep code reading or modification, the output must
contain a real receipt similar to:

```yaml
runtimeReceipt: created
execution: <execution-id>
intent: implement
workflow:
  id: implement-task
nextPhase: understand
taskLog: <project>/.ai/runtime/tasks/<task-id>/events.jsonl
```

`Successfully loaded skill` only indicates that Codex loaded the
`SKILL.md` file. This message does not prove the Task or Execution exists. Without
a Runtime receipt, the agent must stop before modifying code.

The Core's internal Skills are not Codex native Skills. The adapter must
never attempt `$understand`, `$analyze-impact` or `$create-plan`. It
reads the contracts returned by `aief execution next`.

## 7. Codex Permissions

The project baseline uses:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false
```

The rules in `.codex/rules/factory.rules` authorize deterministic inspections,
request confirmation for governed actions and forbid destructive Git commands. Verify decisions before
adoption:

```bash
codex execpolicy check --pretty \
  --rules .codex/rules/factory.rules \
  -- git reset --hard HEAD

codex execpolicy check --pretty \
  --rules .codex/rules/factory.rules \
  -- aief execution approve exec-example
```

The expected result is `forbidden` then `prompt` respectively. A
native Codex approval never replaces a Factory human gate.

Runtime calls generated by the adapter must contain literal arguments:

```bash
aief execution next <execution-id> \
  --project "/absolute/path/to/project" \
  --factory "/absolute/path/to/factory" \
  --json
```

Do not use `$(pwd)`, `${GAD_AI_FACTORY_HOME}`, `cd ... &&`, a
redirection or a pipe in these commands. These constructions prevent
reliable static analysis and cause unnecessary permission requests.

## 8. Verify Execution

In another terminal, inspect the persistent state:

```bash
aief task log <task-id> \
  --project "/absolute/path/to/project" \
  --factory "/absolute/path/to/factory"

aief execution inspect <execution-id> \
  --project "/absolute/path/to/project" \
  --factory "/absolute/path/to/factory"
```

The journal under `.ai/runtime/tasks/<task-id>/events.jsonl` must show
intent, workflow, phases, policy decisions, gates and
validations. The Codex conversation is not the source of truth.

## 9. Troubleshooting

### `Unrecognized command '/implement'`

This behavior is normal in Codex: use `$implement`, not
`/implement`.

### `$implement` is not offered or loaded

Verify:

```bash
test -f "$HOME/.agents/skills/implement/SKILL.md"
ls -la "$HOME/.agents/skills/implement"
test -f "$GAD_AI_FACTORY_HOME/adapters/codex/runtime-protocol.md"
```

If necessary, reinstall the adapter with `setup-adapter ... --execute`, close
Codex, then restart a new session from the project root.

### The Skill is loaded but no Execution exists

Stop any modification. Verify `aief`, `GAD_AI_FACTORY_HOME`,
`.ai/project.yaml` and the requested Factory version. The Skill must obtain a
`runtimeReceipt`; a conversational assertion is not enough.

### The `.codex/` configuration appears to be ignored

Verify that Codex declared the repository as trusted, that the session was
started at the correct root and that it was restarted after configuration
modification.

### Codex requests permission for every Factory command

Verify project rules, then confirm that the adapter uses literal
absolute paths. A command containing `$(pwd)` or `${...}` does not
match deterministic rules properly.

### `PROVIDER_NOT_CONFIGURED` when no task manager is desired

Verify `.ai/project.yaml`. The expected configuration is:

```yaml
taskTracking:
  mode: local
integrations: {}
```

After review and modification, ask Codex to resume the same Execution.
The adapter calls `aief execution next`; the Runtime reevaluates the local decision
and removes the old blockage. Never manually modify files under
`.ai/runtime`.

If the next blockage becomes `workspace-preparation-required`, the
tracking configuration is correct: Codex must now prepare the
worktree via `aief workspace prepare ... --execute`, after the
expected native authorization.

### `url is not supported for stdio`

The `gitlab` block probably contains both an old
HTTP configuration (`url`) and a STDIO configuration (`command`). Remove the duplicate and
keep a single `mcp_servers.gitlab` definition. Codex can merge user (` ~/.codex/config.toml`) and project (`.codex/config.toml`) configurations bearing the
same name, producing this error.

For GitLab OAuth authentication with Codex versions affected by
`Authorization server issuer mismatch`, the expected block is:

```toml
[mcp_servers.gitlab]
command = "npx"
args = ["-y", "mcp-remote@0.1.26", "https://gitlab.com/api/v4/mcp", "--static-oauth-client-metadata", '{"scope":"mcp"}']
```

The `mcp-remote` version is frozen to make startup reproducible. With
this transport, do not run `codex mcp login gitlab`: the OAuth browser is
opened by the bridge at Codex startup.

### `404 Not Found` with GitLab MCP

The URL `https://gitlab.com/api/v4/mcp` is the official URL. On GitLab.com, a
`404` after authentication usually indicates that the MCP server is
not enabled for a root group the user belongs to. An Owner must
enable GitLab Duo, beta/experimental features and MCP access on
the root group. Enabling in a subgroup alone is not sufficient.

### Stale OAuth MCP Cache

If old authorization is being reused, clean only the bridge's
cache then restart Codex:

```bash
rm -rf ~/.mcp-auth/mcp-remote*
```

## 10. Minimal Checklist

- [ ] `GAD_AI_FACTORY_HOME` points to the expected version.
- [ ] `aief` is available in `PATH`.
- [ ] `~/.agents/skills/implement/SKILL.md` exists.
- [ ] Codex session was restarted after Skill installation.
- [ ] Codex is launched from the root containing `.ai/project.yaml`.
- [ ] `taskTracking.mode` matches the traceability system actually desired.
- [ ] In `external` mode, a `task-provider` is configured; in `local` mode,
      `.ai/runtime` is available and ignored by Git.
- [ ] Repository and its `.codex/` configuration have been inspected then
      declared as trusted.
- [ ] `$analyze` creates a Runtime receipt and does not modify code.
- [ ] `$implement` resolves `implement-task` and begins with `understand`.
- [ ] Logs appear in `.ai/runtime/tasks/<task-id>/events.jsonl`.
- [ ] `/implement` is never used in Codex.

## 11. Official OpenAI References

- Codex Skills: <https://developers.openai.com/codex/skills>
- Codex Configuration: <https://developers.openai.com/codex/config-basic>
- Command Rules: <https://developers.openai.com/codex/rules>
- `AGENTS.md` Instructions: <https://developers.openai.com/codex/guides/agents-md>
