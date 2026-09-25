# 30 — Backlog Import Runtime

## Purpose

Backlog import turns a documentation corpus into external tracker tickets —
epics, features, tasks, bugs — without ever creating anything until a human
(or an autonomy-authorized agent) explicitly applies a previewed plan. It
reuses the Task Tracking & Provider Resolution Runtime's contracts
(`docs/17-task-tracking-provider-runtime.md`) rather than introducing a
parallel mechanism: the same `ExternalTaskProposal` is the neutral candidate
model, the same `ExternalOperation` idempotence and autonomy gate apply to
every create/link, and the same Core/adapter/provider boundary holds — Core
never learns a Jira/GitLab/GitHub field name.

```text
Source documents + organization-rules config
  → Runtime discovers allowed source files
  → draft-backlog-candidates (Skill): neutral candidates + open questions
  → Runtime prepares a duplicate-search query per candidate
  → assess-backlog-duplicates (Skill): matches per candidate
  → Runtime decision per candidate (create / link-existing / skip)
  → preview (deterministic, read-only)
  → apply: one idempotent, autonomy-gated create-task/link-task operation per candidate,
    parents created before children
  → canonical external references
```

Unlike the workflows under `core/workflows/`, `import-backlog` is not driven
by the generic Task/Execution engine: that engine assumes one
repository-scoped Task per Execution with one YAML output per phase, which
does not fit "N independently searched, approved and created candidates".
Its two Skills document the agentic contract; a dedicated
`BacklogImportManager` (`aief/backlog.py`) drives the state machine directly,
exactly as Task Tracking drives external task creation without going through
a Workflow.

## Organization-rules configuration

`BacklogImportConfig` (`core/schemas/backlog-import-config.schema.json`) is a
standalone document, supplied with `--config`, answering the organization
questions a backlog import must resolve before drafting starts:

```yaml
apiVersion: aief.dev/v1alpha1
kind: BacklogImportConfig
metadata: {id: specifications-import}
granularity: task
hierarchyLevels: [epic, feature, task, bug]
groupBy: domain
labelingRules:
  defaultLabels: [imported]
duplicatePolicy: always-review
dependencyInference: explicit-only
allowedSourceExtensions: [.md, .feature]
```

Omitting `--config` uses built-in defaults (`granularity: task`,
`duplicatePolicy: always-review`, no grouping, `.md`/`.yaml`/`.yml`/`.feature`
source files). This is intentionally a standalone document rather than a new
`Project` field: organization rules are a per-import decision, not a
per-project one.

## Neutral candidate model

Each candidate is an `ExternalTaskProposal` (`core/schemas/external-task-proposal.schema.json`),
extended with `type` (`epic|feature|task|bug`), `parent` and `dependsOn`
(both referencing another candidate's `metadata.id` within the same import),
and `sourceImport` in place of `sourceTask`. Core produces only this shape —
`type`, `title`, `description`, `acceptanceCriteria`, `parent`, `dependsOn`,
`labels` — and never a provider-specific field; the provider mapping happens
only when a `create-task`/`link-task` `ExternalOperation` is actually
executed, exactly as described in [Adapter/MCP boundary](17-task-tracking-provider-runtime.md#adaptermcp-boundary).

## Duplicate assessment and decision

Runtime-prepared queries (summary + keywords, same shape as
[Duplicate search](17-task-tracking-provider-runtime.md#duplicate-search))
are searched by the agent through the resolved `task-provider`. Each
candidate's decision follows deterministically from the configured
`duplicatePolicy`:

- `always-review` (default): every candidate defaults to `create`; a human sees the recorded matches before approving the resulting operation.
- `auto-link-high-confidence`: a `high`-confidence `link-existing` match pre-resolves the candidate to `link-existing`.

Either way, the per-item autonomy gate on `apply` still applies — a
duplicate policy only decides *which* operation is queued, never whether it
needs approval.

## Apply: parents before children

`apply` topologically sorts candidates by `parent`/`dependsOn` (a cycle is a
hard error) and, for each, prepares an idempotent `create-task` or
`link-task` operation — identical stable-key and retry semantics to
[Idempotence and failure](17-task-tracking-provider-runtime.md#idempotence-and-failure).
A child whose parent has not yet resolved to an external reference (parent
not `skip`ped, not yet applied) is left for a later `apply` call instead of
being created without its parent link; once the parent's operation
completes, re-running `apply` picks the child back up.

Below autonomy L3, every operation waits for explicit approval, backed by
the existing `external-action-policy` rule `task-provider-write` — no bulk
approval that skips duplicate search or the gate.

## Main backlog commands

```bash
aief backlog import --source ./docs/specifications --provider jira --config rules.yaml
aief backlog complete-draft <import-id> --result candidates.yaml
aief backlog complete-duplicate-search <import-id> --result matches.yaml
aief backlog preview <import-id>
aief backlog apply <import-id> --approve
aief backlog operation-approval <import-id> <operation-id> approve|reject
aief backlog complete-operation <import-id> <operation-id> --result result.yaml
aief backlog inspect <import-id>
```

`import` only discovers source files and drafts the plan; it never talks to
a provider. Only `apply` performs external writes. Re-running `import` with
the same `--source`/`--provider` resolves to the same import id instead of
starting a second plan.
