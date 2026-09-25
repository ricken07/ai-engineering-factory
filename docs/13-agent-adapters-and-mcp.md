# 13 — Agent Adapters and MCP Bindings

## Responsibility

An adapter translates Factory contracts into one agent runtime. It does not own workflows, engineering methods, project knowledge, provider semantics or policy decisions.

```text
Core                    capability contracts and policy semantics
Integration catalog     provider capabilities and technical MCP binding
Organization            allowed/default providers and custom-MCP policy
Project .ai/            capability activation and project context
Adapter                 generated agent-native configuration and gates
MCP server              concrete external operation
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

Both adapters must pass a stable `--agent-session`, then acquire the returned
Execution lease with the same `--owner` before mutation. The session argument
alone is `OBSERVED`, not trusted. Only an active matching lease makes producer
or reviewer activity `TRUSTED`; artifact-only identity is `UNVERIFIED`.
Handoff releases the current lease and the receiving adapter acquires the same
Execution with a new owner. The complete command sequence is normative in each
adapter's `runtime-protocol.md`.

## Governance and sources of truth

Provider knowledge must not enter `core/`. The Core knows abstractions such as
`source-control`, `task-provider`, `knowledge-base` and
`continuous-integration`; it never knows GitLab, GitHub, Jira, Confluence, an
endpoint, a token or an agent-native configuration format.

The effective integration configuration is resolved in this order:

```text
Core capability contract
        ↓
Factory integration catalog
        ↓
Organization governance
        ↓
Project capability binding
        ↓
Integration Resolver
        ↓
Claude/Codex generated configuration
```

Responsibilities are deliberately separated:

| Level | Owns | Must not own |
| --- | --- | --- |
| Core | Capability contracts, policies and gates | Concrete providers or MCP details |
| `integrations/` | Provider operations, transport requirements and authentication contract | Secret values or project business rules |
| Organization | Provider allow-list, defaults, managed endpoints, permitted scopes and custom-MCP policy | Project selection or developer credentials |
| Project | Capability-to-provider selection and optional authorized project extension | Tokens, headers, commands or duplicated provider definitions |
| Adapter | Materialization into `.mcp.json`, Codex TOML or future native formats | Core workflow or provider policy |
| Developer/enterprise runtime | Credentials and authenticated session | Versioned project knowledge |

The source of truth is therefore the installed and versioned Factory catalog,
composed with organization governance and project activation. `.mcp.json` and
`.codex/config.toml` are generated adapter artifacts: they may be regenerated
and must never become the place where provider policy is maintained manually.

## MCP resolution

The Core requests an abstract capability such as `task-provider`. The project
activates a provider already supplied and authorized by the organization:

```yaml
taskTracking:
  mode: external

integrations:
  source-control:
    provider: github
  task-provider:
    provider: jira
  knowledge-base:
    provider: confluence
```

This declaration is intentionally limited to logical bindings. The project
must not add `url`, `transport`, `command`, `headers` or a credential value. For
example, an organization can centrally define GitLab once; a project only binds
`source-control` and `continuous-integration` to the `gitlab` catalog entry.
Organization-specific catalogs in this repository are examples, not defaults.

When `taskTracking.mode` is `local`, the Runtime does not resolve
`task-provider`; local Task/Execution artifacts satisfy the tracking policy.
Provider resolution below applies only to explicit `external` mode or to another
Skill that independently requires the capability.

The central catalog keeps capability contracts under `integrations/contracts/`.
Each provider declares supported operations in `integration.yaml` and technical
MCP requirements in `mcp.yaml`. Organization governance filters that catalog
before project resolution. The adapter resolves the resulting endpoint and
authentication contract and exposes only operations that are both declared and
authorized.

```text
skill requires task-provider
→ organization allows/configures jira
→ project selects jira
→ Jira integration declares get-task/search-task/...
→ Jira MCP binding resolves endpoint
→ adapter maps available MCP tools
→ PolicyDecision authorizes or denies the operation
```

Resolution occurs per capability and operation when a Skill needs it. Setup and diagnosis are separate:

```bash
aief integrations lock /workspace/project --factory /factory/1.7.0
aief integrations doctor /workspace/project --factory /factory/1.7.0

aief integrations sync codex /workspace/project --factory /factory/1.7.0
aief integrations sync codex /workspace/project --factory /factory/1.7.0 --scope project --execute

aief integrations sync claude-code /workspace/project --factory /factory/1.7.0
```

`sync` is a dry run unless `--execute` is supplied. Project scope targets `.codex/config.toml` for Codex and `.mcp.json` for Claude Code. User scope targets their user-native configuration. Codex updates only an AIEF-managed TOML block; Claude merges only `mcpServers`. Other native settings are preserved and conflicting unmanaged provider entries fail closed.

Required endpoint variables are provider-specific: `GITHUB_MCP_URL`,
`GITLAB_MCP_URL`, `JIRA_MCP_URL`, and `CONFLUENCE_MCP_URL`. In a managed
organization these values can be injected centrally. Credentials remain in the
OS keychain, secret manager, managed agent authentication store or process
environment; never commit them to `.ai/`, `.mcp.json` or Codex TOML.

## Integration lock

`.ai/integration-lock.yaml` is generated from the pinned Factory catalog. It records provider version, selected capabilities, MCP identity, transport and a content hash. It contains no endpoint or credential. A changed catalog definition makes the lock stale and is reported by `integrations doctor`.

## Scope selection

- Use `user` for organization-wide GitHub, GitLab, Jira or Confluence services shared across projects.
- Use `project` for a project-specific MCP that teammates intentionally share.
- Keep experimental personal MCPs outside project declarations and locks.

The project selects providers, never native agent files, commands, endpoints or secrets.

## Project-specific MCPs

A project-specific MCP is an exception, not an implicit escape hatch. Its
admission follows this decision path:

```text
Project requests custom MCP
→ organization policy allows custom providers?
→ requested scope and transport are allowed?
→ definition passes schema and security validation?
→ required human approval is recorded?
→ provider enters the resolved catalog
→ adapter materializes native configuration
```

Fail closed when any decision is absent. A project-specific MCP must declare
the same capability contracts as a centrally managed provider and remains
subject to autonomy, external-action and human-gate policies. It cannot weaken
a mandatory organization rule.

The current executable contract resolves providers installed under
`integrations/` and selected per capability in `.ai/project.yaml`. Direct
project-local provider manifests are not accepted until the organization-policy
contract and its validator are implemented; do not bypass this by manually
editing generated native files.

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
