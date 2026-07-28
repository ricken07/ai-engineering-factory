# Effective Engineering Context Resolver

Version 1.11.0 completes the existing resolver rather than introducing another context service.

## Resolution chain

For each impacted repository and active Skill, the Runtime computes:

```text
Organization mandatory/default practices
  + Project-selected organization catalogs
  + inherited and selected Profiles
  + Project practices and context documents
  + Repository selections and overrides
  + Task-local constraints and authorized specializations
  -> EffectiveEngineeringContext
```

The most local layer wins only when the referenced practice allows it. A mandatory practice cannot be disabled or overridden by Project, Repository or Task.

## Progressive loading

Each Core Skill declares the categories it consumes:

```yaml
engineeringContext:
  requires: [architecture, convention, security, testing]
```

Examples:

- `understand-task`: no engineering practices;
- `analyze-impact`: architecture and security;
- `create-plan`: architecture, conventions, security and testing;
- `implement-change`: architecture, conventions, security and testing;
- `validate-change`: testing and security;
- `review-change`: architecture, conventions, security, testing and review.

The Runtime does not load unrelated Java, Spring, Flutter, review or testing documents merely because they exist.

## Task-specific context

A normalized Task may add explicit constraints and engineering selections:

```yaml
constraints:
  - Do not expose provider-specific error messages.

engineering:
  practices:
    java-coding-conventions:
      mode: override
      ref: .ai/context/task-java-conventions.md
```

Task overrides remain confined to the project workspace and are rejected when the organization practice is mandatory or protected.

## Provenance and fingerprint

Every resolved profile records its ID, version, manifest source and inheritance. Every practice records:

```yaml
contentHash: <sha256>
provenance:
  source: organization | project | repository | task
  document: <resolved path>
  manifest: <organization manifest when applicable>
```

The final context has a stable `fingerprint`. It changes when a selected profile version, practice version, document content, Task constraint or relevant category changes. Absolute installation paths are excluded, so identical Factory content remains comparable across developer machines. Claude Code and Codex can therefore verify that a resumed execution is using the same engineering context without sharing conversation memory.

Every selected organization catalog also records its ID, version, manifest,
inheritance and profile bindings. Catalog identity is part of the fingerprint.

## Runtime usage

For an active Execution, context is materialized automatically by `aief execution next` when the phase declares `engineeringContext`.

It may also be inspected explicitly:

```bash
aief engineering-context egw-api implement-change \
  --task EGW-142 \
  --project . \
  --factory /factory/1.11.0 \
  --json
```

In a poly-repo task, the Runtime creates one effective context per repository. `egw-api` can receive Java/Spring/Maven practices while `egw-app` receives Flutter practices for the same Task and phase.
