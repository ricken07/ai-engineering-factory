# 16 — Organization engineering context

## Purpose

The organization catalog capitalizes engineering knowledge once and distributes only the applicable subset to each agent operation. It is an extension of the Factory, not project knowledge and not a dependency of the agnostic Core.

```text
Core contracts
  → project-selected OrganizationCatalog
  → organization standards/practices
  → catalog profile bindings
  → project selection/override
  → repository specialization
  → Skill category requirements
  → EffectiveEngineeringContext
```

## Practice contract

Each practice consists of a YAML manifest and a Markdown document:

```yaml
apiVersion: aief.dev/v1alpha1
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
- `default`: inherited through bindings in a selected organization catalog and replaceable only when allowed;
- `optional`: inactive until a project or repository explicitly enables it.

## Organization catalog and Profile binding

Profiles remain technical and organization-neutral. A selected catalog binds
organization knowledge to Profile IDs:

```yaml
kind: OrganizationCatalog
metadata: {id: example-organization, version: 1.0.0}
extends: [factory-default@1.0.0]
practiceRefs: [spring-conventions@1.0.0]
profileBindings:
  spring: [spring-conventions@1.0.0]
```

Profile inheritance is resolved first, then bindings from only the
project-selected catalogs are applied. A Spring repository can therefore use
different conventions in two organizations without changing `profiles/spring`.

## Project and repository configuration

```yaml
engineering:
  inheritOrganization: true
  organizationCatalogs: [example-organization@1.0.0]
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
  --factory /factory/1.7.0
```

Resolve and persist it for the current execution phase:

```bash
aief execution engineering-context <execution-id> \
  --repository egw-api \
  --project . \
  --factory /factory/1.7.0
```

Normal adapter progression uses:

```bash
aief execution next <execution-id> --project . --factory /factory/1.7.0
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

## Output contracts

A practice tells an agent what to do; it does not prove the agent did it. An
organization catalog or a project can turn part of a practice into a checked
contract: an extra JSON Schema that a Skill output must satisfy, on top of the
Core `output.schema.json`.

```yaml
# organization/catalogs/acme-backend.yaml (schema path relative to organization/)
outputContracts:
  - skill: analyze-impact
    schema: contracts/acme-impact-classification.schema.json
```

```yaml
# .ai/project.yaml (schema path relative to the project root)
engineering:
  outputContracts:
    - skill: analyze-impact
      schema: .ai/contracts/impact-domains.schema.json
```

Rules:

- contracts only add constraints: the Core schema is checked first, then every
  contract of every selected catalog and of the project;
- they apply to outputs whose `status` is `completed`; a `blocked` or `failed`
  output is held to the Core schema only;
- `complete-phase` rejects a non-conforming output and names the contract
  (`organization:<catalog>` or `project`);
- `prepare_phase` returns them in `skillContract.outputContracts` with their
  SHA-256, so the agent reads them and the event log records which version
  applied;
- schema paths cannot escape their root; repository and task levels do not
  accept contracts; `aief validate` reports missing or invalid schemas.

A JSON Schema checks structure and closed vocabularies. Rules that compare
fields with each other or with the file system stay in organization tooling.
