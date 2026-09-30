# 08 — Project Adoption

## 1. Install/pin the Factory

The Factory itself carries no organization- or project-specific content —
cloning it installs only `core/`, `profiles/`, `adapters/` and
`integrations/`. The organization's single reference is a published Git tag,
pinned once for every team member and every project (see
[`09-governance.md`](09-governance.md#versioning)); for example:

```text
~/.aief/ai-engineering-factory/0.1.0/
```

If the organization also maintains its own engineering practices, it defines
and hosts that catalog separately, in its own repository — never committed
into the Factory itself. See [`organization/README.md`](../organization/README.md).

## 2. Copy the project template

Copy `templates/project/` into the project workspace root.

## 3. Configure `.ai/project.yaml`

Declare:

- project identity,
- Factory version,
- mono/poly-repo strategy,
- repository list,
- enabled profiles,
- capability integrations,
- Task tracking mode (`local` or `external`),
- default/maximum autonomy.

For a project without a task manager or MCP, declare:

```yaml
integrations: {}
taskTracking:
  mode: local
```

For provider-backed tracking, declare `mode: external` and bind
`integrations.task-provider`. The Runtime never infers or changes this choice.

## 4. Configure `.ai/repository-map.yaml`

Describe repository responsibilities and relationships. This is essential for poly-repo impact analysis.

## 5. Fill project context

Complete:

```text
.ai/context/project.md
.ai/context/architecture.md
.ai/context/domain.md
.ai/context/conventions.md
```

## 6. Initialize knowledge and runtime

Initialize `.ai/memory/` without speculative project facts. Keep `.ai/runtime/` ignored by Git and configure retention in `.ai/project.yaml`. Knowledge learned during work must pass through `promote-knowledge`; never copy task or session notes directly into durable project files.

The durable part of `.ai/` is committed with the project. This includes `.ai/project.yaml`, the repository map, approved context, decisions, validated memory and the integration lock. `.ai/runtime/` and local credentials remain ignored.

If a merge conflicts in durable `.ai/` content, resolve it explicitly with project owners, then run the project validation and integration checks before continuing. A Runtime conflict should not normally occur because `.ai/runtime/` is local and ignored.

## 7. Bootstrap agents

`AGENTS.md` and `CLAUDE.md` must remain thin bootstraps. They point to the Factory and project context; they must not duplicate the full Factory rules.

## 8. Start work from workspace root

Examples:

```text
Codex: $implement TASK-123
Claude Code: /implement TASK-123
Natural language: Implémente TASK-123.
```

Exact slash-command syntax is adapter-specific; the Factory workflow identity remains stable.

## 9. Resolve integrations

Generate and review `.ai/integration-lock.yaml`, diagnose both agent runtimes, then preview and explicitly execute MCP synchronization for the chosen scope. Keep endpoints and credentials in local environment, keychain, secret manager or managed enterprise configuration.
