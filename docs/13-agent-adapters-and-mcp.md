# 13 — Agent Adapters and MCP Bindings

## Responsibility

An adapter translates Factory contracts into one agent runtime. It does not own workflows, engineering methods, project knowledge, provider semantics or policy decisions.

```text
Core             what must happen
Project .ai/     project context and provider selection
Integration      provider capabilities and operations
Adapter          agent-native invocation, tools and gates
MCP server       concrete external operation
```

## Lifecycle

### Onboarding

Install thin user-level adapter skills once:

```bash
aief setup-adapter codex --factory /factory/1.2.0
aief setup-adapter codex --factory /factory/1.2.0 --execute

aief setup-adapter claude-code --factory /factory/1.2.0
aief setup-adapter claude-code --factory /factory/1.2.0 --execute
```

The default dry run shows every planned link. Installation refuses to overwrite unrelated paths. Codex skills target `~/.agents/skills`; Claude Code skills target `~/.claude/skills`. A version upgrade repoints the centrally managed links; projects do not copy these skills.

### Session bootstrap

`AGENTS.md` is the concise shared bootstrap. `CLAUDE.md` imports it and adds only the Claude adapter bridge. Both resolve `.ai/project.yaml`; neither duplicates Core procedures or provider configuration.

### Task execution

Codex uses `$implement TASK-123`; Claude Code uses `/implement TASK-123`. The adapter skill resolves the same `implement-task` workflow, creates or resumes the same task runtime state and enforces the same PolicyDecision.

## MCP resolution

The Core requests an abstract capability such as `task-provider`. The project selects a provider:

```yaml
integrations:
  source-control:
    provider: github
  task-provider:
    provider: jira
  knowledge-base:
    provider: confluence
```

The central catalog keeps capability contracts under `integrations/contracts/`. Each provider declares supported operations in `integration.yaml` and technical MCP requirements in `mcp.yaml`. The adapter resolves environment-specific endpoint configuration and exposes only operations that are both declared and authorized.

```text
skill requires task-provider
→ project selects jira
→ Jira integration declares get-task/search-task/...
→ Jira MCP binding resolves endpoint
→ adapter maps available MCP tools
→ PolicyDecision authorizes or denies the operation
```

Resolution occurs per capability and operation when a Skill needs it. Setup and diagnosis are separate:

```bash
aief integrations lock /workspace/project --factory /factory/1.3.0
aief integrations doctor /workspace/project --factory /factory/1.3.0

aief integrations sync codex /workspace/project --factory /factory/1.3.0
aief integrations sync codex /workspace/project --factory /factory/1.3.0 --scope project --execute

aief integrations sync claude-code /workspace/project --factory /factory/1.3.0
```

`sync` is a dry run unless `--execute` is supplied. Project scope targets `.codex/config.toml` for Codex and `.mcp.json` for Claude Code. User scope targets their user-native configuration. Codex updates only an AIEF-managed TOML block; Claude merges only `mcpServers`. Other native settings are preserved and conflicting unmanaged provider entries fail closed.

Required endpoint variables are provider-specific: `GITHUB_MCP_URL`, `GITLAB_MCP_URL`, `JIRA_MCP_URL`, and `CONFLUENCE_MCP_URL`. Credentials remain in the environment or the agent/provider authentication store; never commit them to `.ai/`.

## Integration lock

`.ai/integration-lock.yaml` is generated from the pinned Factory catalog. It records provider version, selected capabilities, MCP identity, transport and a content hash. It contains no endpoint or credential. A changed catalog definition makes the lock stale and is reported by `integrations doctor`.

## Scope selection

- Use `user` for organization-wide GitHub, GitLab, Jira or Confluence services shared across projects.
- Use `project` for a project-specific MCP that teammates intentionally share.
- Keep experimental personal MCPs outside project declarations and locks.

The project selects providers, never native agent files, commands, endpoints or secrets.

## Gates and least privilege

Before an MCP side effect, the adapter rechecks:

1. the project selected the provider for the capability;
2. the integration declares the requested operation;
3. the MCP binding is available;
4. the effective PolicyDecision allows the action;
5. every required human gate is satisfied.

Discovery does not grant permission. A configured MCP tool remains unusable when policy denies its action.

## Failure behavior

Fail closed when the Factory version, adapter, provider binding, endpoint or required capability cannot be resolved. Record the failure in task runtime, use bounded recovery for configuration errors, and ask a precise user question when credentials, endpoint selection or authority must be supplied externally.

## Native runtime references

- Codex skills: <https://developers.openai.com/codex/build-skills>
- Codex project instructions: <https://developers.openai.com/codex/agent-configuration/agents-md>
- Claude Code skills: <https://docs.anthropic.com/en/docs/claude-code/skills>
- Claude Code project memory/imports: <https://docs.anthropic.com/en/docs/claude-code/memory>

Native locations and configuration formats can evolve. Keep those details in adapters and their tests, never in Core or project knowledge contracts.
