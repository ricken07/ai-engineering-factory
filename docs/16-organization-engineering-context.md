# 16 — Organization engineering context

## Purpose

The organization catalog capitalizes engineering knowledge once and distributes only the applicable subset to each agent operation. It is an extension of the Factory, not project knowledge and not a dependency of the agnostic Core.

```text
Core contracts
  → organization standards/practices
  → profile references
  → project selection/override
  → repository specialization
  → Skill category requirements
  → EffectiveEngineeringContext
```

## Practice contract

Each practice consists of a YAML manifest and a Markdown document:

```yaml
apiVersion: factory.gaddigital.io/v1alpha1
kind: Practice
metadata: {id: java-coding-conventions, version: 1.0.0}
category: convention
enforcement: default
appliesTo:
  profiles: [java]
  skills: [implement-change, review-change]
document: {path: java-coding-conventions.md}
inheritance: {strategy: merge}
override: {allowed: true}
```

Enforcement has deterministic meaning:

- `mandatory`: automatically inherited when applicable; never disabled or overridden;
- `default`: inherited through profile references and replaceable only when allowed;
- `optional`: inactive until a project or repository explicitly enables it.

## Profile as assembler

Profiles select organization knowledge by ID:

```yaml
metadata: {id: spring}
extends: [java]
practiceRefs:
  - spring-conventions
```

Profile inheritance is resolved first. A Spring repository therefore obtains references from `generic`, `java` and `spring` without copying their documents.

## Project and repository configuration

```yaml
engineering:
  inheritOrganization: true
  practices:
    api-design: {mode: enable}

repositories:
  - id: api
    profiles: [java, spring, maven]
    engineering:
      practices:
        hexagonal-architecture: {mode: enable}
        payment-module-conventions:
          mode: enable
          category: convention
          ref: .ai/context/payment-module-conventions.md
```

Supported modes are `inherit`, `enable`, `disable` and `override`. A local practice requires a document and category. Paths must remain inside the project workspace.

An allowed override is explicit and traceable:

```yaml
java-coding-conventions:
  mode: override
  ref: .ai/context/java-conventions.md
```

When the Practice declares `inheritance.strategy: merge`, the effective content contains the organization document followed by the local specialization. With `replace`, only the local document is delivered. Mandatory rules never reach either override path.

An attempt to disable `secret-management` produces `PRACTICE_CONFLICT` during project validation and Runtime resolution.

## Skill filtering

Skills declare only the categories they need:

```yaml
engineeringContext:
  requires: [architecture, convention, security, testing]
```

`implement-change` receives implementation context; `review-change` additionally receives review practices; `validate-change` receives testing and security. Unrequested categories are excluded.

## Runtime usage

Inspect a repository/Skill context without an Execution:

```bash
aief engineering-context egw-api review-change \
  --project examples/emmany \
  --factory /factory/1.6.0
```

Resolve and persist it for the current execution phase:

```bash
aief execution engineering-context <execution-id> \
  --repository egw-api \
  --project . \
  --factory /factory/1.6.0
```

Normal adapter progression uses:

```bash
aief execution next <execution-id> --project . --factory /factory/1.6.0
```

Once impact information identifies repositories, this command automatically resolves and persists the category subset required by the next Skill. The explicit `engineering-context` command remains available for inspection and diagnostics.

The resulting `EffectiveEngineeringContext` includes:

- project, repository, Skill and resolved profiles;
- requested categories;
- effective practice IDs and versions;
- source (`organization`, `project`, `repository`);
- resolved document path and content;
- a trace of inheritance, activation, disablement and overrides.

Profile-driven validation resolves and persists this context automatically before executing repository commands.

## Example: cross-repository implementation

For `egw-api`, Java/Spring practices, mandatory security/testing, enabled API/hexagonal architecture, project documents and payment conventions are composed.

For `egw-app`, Java/Spring/hexagonal practices are excluded because its profile is Flutter. Mandatory applicable practices and project documents remain available.

The same workflow and agent can therefore operate with two precise contexts without mixing stack-specific conventions.

## Fail-closed conditions

Resolution stops on:

- unknown practice or profile;
- duplicate practice ID;
- unavailable requested version;
- forbidden mandatory disable/override;
- protected default override;
- missing document;
- document escaping its organization/project root;
- unknown repository or Skill.

Project validation performs the same semantic configuration checks before execution.
