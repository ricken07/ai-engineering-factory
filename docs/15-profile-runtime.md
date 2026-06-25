# 15 — Profile-driven validation runtime

## Contract

The Core Skill `validate-change` asks for validation without naming a technology. Each impacted repository selects reusable profiles in `.ai/project.yaml`; the shared Runtime resolves those profiles and executes only commands whose discovery files exist in that repository.

```text
validate-change phase
  → impacted repository IDs
  → project repository declarations
  → ordered profile inheritance
  → discovery checks
  → argv validation plan
  → autonomy/gate check
  → shell-free process execution
  → schema-valid ValidationReport
```

Remote CI is optional. It is resolved through the `continuous-integration` capability only when configured and relevant; it is not a prerequisite for local profile validation.

## Secure command representation

Profile commands are argument arrays, never shell programs:

```yaml
commands:
  build: [./mvnw, verify]
  test: [./mvnw, test]
```

The executor calls the process with `shell: false`. Shell metacharacters, substitutions and redirections are therefore not interpreted. A missing executable is recorded as exit code `127` rather than silently ignored.

## Repository resolution

The Runtime obtains impacted repository IDs in this order:

1. the Execution repository list;
2. the normalized Task scope;
3. the structured `analyze-impact` artifact.

It fails closed when impact is unknown, a repository ID is absent from `project.yaml`, a path escapes the workspace, the directory is missing, a profile is unknown, or no applicable command can be resolved.

## Governance

Planning is side-effect free:

```bash
aief execution profile-validation <execution-id> --project . --factory /factory/1.7.0
```

Execution is explicit:

```bash
aief execution profile-validation <execution-id> --execute --project . --factory /factory/1.7.0
```

The Runtime executes commands only when:

- the current phase uses `validate-change`;
- the Execution is not waiting, blocked, failed or cancelled;
- preceding workflow gates have been satisfied;
- effective task/project autonomy is at least `L2`.

## Poly-repository example

For an Emmany change affecting `egw-api` and `egw-app`:

```text
egw-api [java, spring, maven]
  → ./mvnw verify
  → ./mvnw test

egw-app [flutter]
  → flutter test
  → flutter analyze
```

Commands execute from their repository root. The resulting report records repository, profile, operation, argv, working directory, exit code, stdout and stderr for every command.

Any non-zero exit code makes the report and Execution `failed`. Successful validation advances to the next workflow phase. In both cases, `validation.yaml` remains available for review, traceability and multi-agent handoff.
