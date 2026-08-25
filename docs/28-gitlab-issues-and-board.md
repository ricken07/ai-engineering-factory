# 28 — GitLab Issues and Issue Board

## Goal

GitLab Issues can carry durable Tasks while an Issue Board provides a
governance view. The Core knows neither GitLab nor its tool names: it
requests only the `task-provider` capability.

```text
Local Task or GitLab reference
  → task-provider
  → Integration Resolver
  → verified operation mapping
  → GitLab MCP
  → GitLab Issue
  → workflow labels
  → Issue Board
```

## Native GitLab MCP Scope

The central catalog maps only currently verified operations:

| Factory | GitLab MCP Tool |
| --- | --- |
| `get-task` | `get_issue` |
| `search-task` | `search` |
| `create-task` | `create_issue` |
| `comment-task` | `create_workitem_note` |
| `link-task` | `link_work_items` |
| `link-change` | `link_work_items` |

`update-task` is not announced by the native provider. Attempting to
resolve it returns `CAPABILITY_UNSUPPORTED`. There is no silent REST fallback.

To support `update-task` later, the organization must provide a
governed MCP provider/gateway that explicitly implements the operation. Core
Skills remain unchanged.

## Project Configuration

The project activates only capabilities and its Task model:

```yaml
integrations:
  source-control: {provider: gitlab}
  continuous-integration: {provider: gitlab}
  task-provider: {provider: gitlab}

taskTracking:
  mode: external
  namespace: example-organization/emmany
  referenceFormat: container-iid
  workflowStates:
    - workflow::backlog
    - workflow::ready
    - workflow::doing
    - workflow::review
    - workflow::done
  defaultLabels:
    - workflow::backlog
```

`namespace`, labels and reference format are project context. URL,
transport and MCP authentication remain in the organization catalog and
adapters.

## Polyrepo References

A `#42` reference is ambiguous in a polyrepo workspace. Use:

```text
example-organization/emmany/egw-api#42
```

or the full URL:

```text
https://gitlab.com/example-organization/emmany/egw-api/-/issues/42
```

The Runtime preserves the complete reference as canonical identity.

## Creation and Board

An `ExternalTaskProposal` can select the target GitLab project and labels:

```yaml
kind: ExternalTaskProposal
sourceTask: local-...
title: Fix the Homework contract
description: ...
acceptanceCriteria: [...]
repositories: [egw-api, egw-app]
risk: high
target:
  container: app
labels:
  - type::bug
  - component::backend
```

The Runtime adds the namespace and `defaultLabels`. Creation remains
forbidden before duplicate search and human gate. An Issue created with
`workflow::backlog` appears in the corresponding board list.

## Authentication

The official GitLab MCP uses OAuth. Claude Code can use the native HTTP
transport directly. With certain Codex CLI versions, `codex mcp login gitlab`
fails with `Authorization server issuer mismatch`.

In that case, use the OAuth STDIO bridge `mcp-remote`:

```toml
[mcp_servers.gitlab]
command = "npx"
args = ["-y", "mcp-remote@0.1.26", "https://gitlab.com/api/v4/mcp", "--static-oauth-client-metadata", '{"scope":"mcp"}']
```

The version is deliberately pinned to prevent implicit updates to a third-party
dependency on the authentication path. The browser opens at Codex startup;
`codex mcp login gitlab` is not needed with this configuration.

There must be only one `mcp_servers.gitlab` definition. Never mix
`url`/`bearer_token_env_var` (HTTP Bearer) and `command`/`args` (STDIO) in
the same block. A user configuration in `~/.codex/config.toml` and a
project configuration in `.codex/config.toml` with the same name can also be
merged by Codex.

After modification, verify from the project root:

```bash
codex mcp list
codex
```

The GitLab token is not written to the project. With OAuth `mcp-remote`, it is
kept in the MCP bridge's local authentication cache.

## Validation

```bash
aief integrations lock "$PROJECT_ROOT" --factory "$AIEF_HOME"
aief integrations doctor "$PROJECT_ROOT" --factory "$AIEF_HOME"
aief validate "$PROJECT_ROOT" --factory "$AIEF_HOME"
```

Before the first mutation, verify read-only the MCP version, an existing Issue,
work item search and namespace labels.
