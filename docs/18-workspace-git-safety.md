# Workspace & Git Safety Runtime

Version 1.8.0 introduces a deterministic safety boundary before every `implementation` phase. It does not rely on Claude Code or Codex remembering Git precautions.

## Impact scope precondition

The `analyze-impact` artifact is the authoritative source of the initial Git
scope. It must contain `details.repositories` with identifiers declared in
`.ai/project.yaml`. For any workflow containing `implement-change`, the Runtime
rejects an empty list, an unknown identifier, or a malformed artifact before it
completes the impact phase.

The Runtime then persists the normalized list in both
`Task.scope.repositories` and `Execution.repositories`. Workspace safety reads
only this persisted state. An adapter must never repair
`workspace-safety-unresolved` by editing Runtime YAML directly.

All persisted Factory YAML is loaded with duplicate-key detection. A document
containing two `scope` mappings, for example, fails explicitly instead of
silently accepting the last value.

## Safety invariant

The Runtime never resets, cleans, stashes, overwrites, commits, or incorporates pre-existing developer changes. A dirty repository is blocked in `require-clean` mode and isolated in `worktree` mode.

## Project metadata and merge conflicts

`.ai/project.yaml` and the other durable `.ai/` files are shared project metadata. They are versioned and reviewed like source code. A conflict in them must be resolved before the workflow continues, especially when it changes repositories, base branches, providers, workspace safety or autonomy.

`.ai/runtime/` is generated local state and must remain ignored, so it should not be merged. After resolving durable metadata, validate the project and inspect the configured workspace again; never repair a conflict by editing Runtime artifacts manually.

## Project configuration

```yaml
workspaceSafety:
  mode: require-clean # or worktree
  baseBranch: main
  taskBranchPrefix: aief

repositories:
  - id: api
    path: ./api
    role: backend
    git:
      baseBranch: main
```

`require-clean` requires every impacted repository to be clean. Preparation then creates a task branch only after explicit execution. `worktree` preserves the original repository and creates execution-owned worktrees under `.ai/runtime/worktrees/<execution-id>/`.

## Runtime sequence

```text
implementation phase
  -> resolve impacted repositories
  -> inspect Git roots, HEAD, branch, status and conflicts
  -> persist workspace.yaml
  -> block if unsafe or not prepared
  -> explicit workspace preparation
  -> verify branch and conflict invariants
  -> resume implementation
```

## Commands

```bash
aief workspace inspect <execution-id> --project . --factory /factory/1.8.0
aief workspace prepare <execution-id> --project . --factory /factory/1.8.0
aief workspace prepare <execution-id> --execute --project . --factory /factory/1.8.0
aief workspace verify <execution-id> --project . --factory /factory/1.8.0
aief workspace status <execution-id> --project . --factory /factory/1.8.0
aief workspace rollback <execution-id> --project . --factory /factory/1.8.0
aief workspace rollback <execution-id> --execute --project . --factory /factory/1.8.0
```

Without `--execute`, `prepare` is a plan and has no Git side effect.

## Typical cases

### Clean monorepo

Inspection returns `branch-required`. The planned command is structured (`git switch -c aief/<task>`). Explicit preparation creates the branch, persists `ready`, and resumes the blocked execution.

### Dirty developer repository

In `require-clean` mode, the decision is `blocked` with `unrelated-local-changes`. The Runtime does not stash or modify those files. The developer chooses how to preserve their work.

### Dirty poly-repo workspace

Each impacted repository is inspected independently. One dirty repository blocks the complete mutation boundary, preventing a partial multi-repository implementation.

### Isolated execution

In `worktree` mode, the Runtime plans one worktree per impacted repository from its recorded base commit. Explicit execution creates task branches in isolated directories while original branches and local files remain untouched.

### Interruption or drift

`workspace.yaml` records the base commit, original branch, task branch, paths and decision. On resume, `verify` detects branch drift and unmerged conflicts before the agent continues. Conversation memory is not used as evidence.

## Conservative rollback

Rollback is planned by default. With `--execute`, it only removes a worktree owned and recorded by the execution, or switches a clean strict-mode workspace back to its configured base branch. It refuses dirty execution workspaces, never deletes the task branch, and never resets files.

## Forbidden operations

The structured Git boundary rejects force push (including force-with-lease), hard reset, clean, branch deletion and discard-changes. Rollback cannot reset a developer workspace or discard agent changes.
