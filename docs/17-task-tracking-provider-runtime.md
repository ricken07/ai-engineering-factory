# 17 — Task Tracking & Provider Resolution Runtime

## Purpose

This increment turns a local Task into governed, provider-backed traceability without embedding Jira, GitLab, GitHub or MCP names in Core workflows.

```text
Local Task
  → deterministic tracking decision
  → configured task-provider
  → duplicate search operation
  → assessed candidates
  → human link selection OR external proposal
  → autonomy/human gate
  → idempotent provider operation
  → canonical reference
  → blocked Execution resumes
```

## Deterministic tracking policy

`core/policies/task-tracking-policy.yaml` is interpreted by the Runtime. Applicable rules are combined using `required > recommended > optional`; only reasons producing the effective level are recorded.

The decision is persisted as:

```text
.ai/runtime/tasks/<task-id>/tracking.yaml
```

High/critical risk and cross-repository impact require tracking before implementation. Meaningful functional/source changes recommend it. Informational work, documentation-only work and small low-risk refactoring remain optional.

Completion of `analyze-impact` automatically re-evaluates risk observations, Task scope and tracking. Before an `implementation` phase, unresolved required tracking changes the Execution to:

```yaml
status: blocked
blockingReason:
  type: external-tracking-required
  requiredBefore: implementation
```

## Provider resolution

The Runtime resolves only the project binding:

```yaml
integrations:
  task-provider:
    provider: jira
```

It verifies catalog presence, `task-provider`, requested operations, MCP capability, endpoint, credentials and optionally the current adapter configuration. It never falls back to another provider.

Explicit failure codes include:

- `PROVIDER_NOT_CONFIGURED`;
- `PROVIDER_UNAVAILABLE`;
- `CAPABILITY_UNSUPPORTED`;
- `MCP_NOT_CONFIGURED`;
- `MCP_UNAVAILABLE`;
- `AUTHENTICATION_REQUIRED`.

## Adapter/MCP boundary

The Python Runtime does not impersonate an agent MCP client. It writes an `ExternalOperation` containing provider, abstract operation, input, approval state and stable `operationId`. Claude/Codex executes that operation using its configured MCP and returns the structured result:

```text
Runtime prepare
  → ExternalOperation
  → Adapter maps operation to available MCP tool
  → MCP calls provider
  → Adapter submits result
  → Runtime validates, persists and advances
```

## Duplicate search

```bash
aief task search-external <task-id> --project . --factory /factory/1.7.0
```

The query contains summary, deterministic keywords, domains and repositories. The adapter submits assessed matches:

```yaml
matches:
  - reference: EMM-441
    title: Incorrect MTN callback status mapping
    confidence: high
    rationale: [same component, same behavior]
    recommendation: link-existing
```

```bash
aief task complete-search <task-id> --result matches.yaml --project . --factory /factory/1.7.0
```

The provider call and persistence are deterministic; semantic confidence/rationale are agentic. A human still chooses the reference to link.

## Link existing

```bash
aief task link <task-id> EMM-441 --project . --factory /factory/1.7.0
aief task operation-approval <task-id> link-task-<task-id>-EMM-441 approve --project . --factory /factory/1.7.0
```

After the adapter performs the operation, it submits:

```bash
aief task complete-operation <task-id> <operation-id> --result provider-result.yaml --project . --factory /factory/1.7.0
```

The local Task retains its ID and gains `tracking.canonicalReference: EMM-441`.

## Create external

Creation is forbidden until duplicate search completes. The agent first produces a schema-valid `ExternalTaskProposal`, then:

```bash
aief task propose-external <task-id> --proposal proposal.yaml --project . --factory /factory/1.7.0
aief task create-external <task-id> --project . --factory /factory/1.7.0
```

Below autonomy L3, creation waits for explicit approval. L3+ may execute directly unless a stronger policy requires a gate. A rejected operation remains failed and cannot be silently retried.

## Idempotence and failure

Create uses the stable key:

```text
create-task-<local-task-id>
```

Every retry carries this key to the provider adapter. A completed operation returns its persisted result without another call. A transient failure may retry the same operation ID. This lets providers/MCP adapters apply their own idempotency facility and prevents Runtime-generated duplicate IDs.

`MCP_UNAVAILABLE` or another execution error is persisted on the operation. The Runtime does not change provider or continue the workflow.

## Minimal synchronization

This release links identity and canonical reference. Existing abstract operations support later updates for important blocks, change-request links, summaries and completion. It intentionally does not implement full bidirectional issue replication.

## Main task commands

```bash
aief task tracking <task-id>
aief task resolve-provider <task-id>
aief task search-external <task-id>
aief task complete-search <task-id> --result matches.yaml
aief task link <task-id> <external-reference>
aief task propose-external <task-id> --proposal proposal.yaml
aief task create-external <task-id>
aief task operation-approval <task-id> <operation-id> approve|reject
aief task complete-operation <task-id> <operation-id> --result result.yaml
```

These commands are deterministic adapter primitives. Normal developers should experience a concise question to link or create, then see the original workflow resume.
