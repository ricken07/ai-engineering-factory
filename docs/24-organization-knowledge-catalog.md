# 24 — Adding Organization Knowledge

## Purpose

Organizational knowledge must be written once, versioned, governed by Factory contracts, and composed with conventions specific to each project and repository.

```text
Organization documentation repository
  → catalog pinned in Factory/organization/catalogs
  → Practice manifests
  → Profiles and explicit activations
  → Project / Repository / Task specializations
  → EffectiveEngineeringContext
  → Core Skill
  → Claude Code or Codex
```

Files under `organization/catalogs/` and `organization/practices/` are optional extensions. They do not constitute an implicit organization of the Factory. To create a catalog specific to an organization, start with the template [`templates/organization/catalog.yaml`](../templates/organization/catalog.yaml) and the `Practice` manifest presented below, then select it explicitly in the project.

The Core remains agnostic: it only defines the `Practice` contract and the context categories consumed by Skills.

This knowledge catalog must not be confused with the integrations catalog. Conventions and practices live under `organization/`; providers GitLab, GitHub, Jira or Confluence live under `integrations/`. The organization governs both, but a project only selects the elements it is authorized to use. The complete MCP model is defined in [`13-agent-adapters-and-mcp.md`](13-agent-adapters-and-mcp.md).

## Sources and Responsibilities

| Level | Responsibility |
| --- | --- |
| Guidelines repository | Human reference content and editorial history |
| `organization/catalogs/` | Exact revision of the source installed with Factory |
| `Practice` manifest | Version, category, enforcement, applicability and override |
| `OrganizationCatalog` | List of Practices, inheritance and bindings by Profile |
| Profile | Detection and technical knowledge, with no organization preference |
| Project | Explicit selection of catalogs and conventions specific to the project |
| Repository | Activation tied to its role and local specialization |
| Task | Governed temporary constraint, never global memory |

## Why Use a Submodule

An absolute path such as `/Users/.../gd-extensions/guidelines` varies by workstation, escapes the secure catalog, and makes the context non-reproducible. A manual copy quickly diverges from the source.

The submodule preserves:

- an autonomous Git source;
- an exact commit in each Factory version;
- reproducible installation;
- explicit and reviewable updates;
- a stable content fingerprint in EffectiveEngineeringContext.

Installation:

```bash
git clone --recurse-submodules <FACTORY_REPOSITORY_URL> <FACTORY_HOME>
```

Existing clone:

```bash
git submodule update --init --recursive
```

## Declaring a Configurable Catalog

A Factory can embed multiple catalogs without imposing one globally:

```yaml
apiVersion: aief.dev/v1alpha1
kind: OrganizationCatalog
metadata:
  id: example-organization
  name: Example Organization Engineering Catalog
  version: 1.0.0
extends: [factory-default@1.0.0]
practiceRefs:
  - example-java-guidelines@1.0.0
  - example-app-architecture@1.0.0
profileBindings:
  java: [example-java-guidelines@1.0.0]
```

The `factory-default` catalog is an optional foundation. An organization can extend it, select multiple compatible catalogs, or provide an entirely independent catalog.

The project chooses explicitly:

```yaml
engineering:
  inheritOrganization: true
  organizationCatalogs:
    - example-organization@1.0.0
```

The Runtime resolves parents, verifies versions, rejects cycles, and includes catalog provenance in the effective context fingerprint.

## Converting a Document into a Practice

Markdown alone is not loaded by the Runtime. It must be exposed by a YAML manifest located under `organization/`:

```yaml
apiVersion: aief.dev/v1alpha1
kind: Practice
metadata:
  id: organization-api-guidelines
  name: Organization API Guidelines
  version: 1.0.0
category: convention
enforcement: optional
appliesTo:
  profiles: [java, spring]
  skills: [analyze-impact, create-plan, implement-change, review-change]
document:
  path: ../../catalogs/guidelines/api-guidelines.md
inheritance:
  strategy: merge
override:
  allowed: false
tags: [java, spring, api]
```

The document path is relative to the manifest and must remain within `organization/`. The Runtime rejects missing documents or paths that escape this catalog.

## Choosing Enforcement

### `mandatory`

Rule applied automatically and not overrideable. Reserved for truly universal invariants: secrets, security, regulatory obligations, or organizational quality baseline.

```yaml
enforcement: mandatory
override: {allowed: false}
```

### `default`

Practice inherited when a Profile references it. Can be specialized only if `override.allowed` is `true`.

```yaml
enforcement: default
override: {allowed: true}
```

### `optional`

Practice available but activated explicitly. Good choice for an architecture or role that does not concern all repositories in a stack: contractual API, layered APP, hexagonal or event-driven architecture.

```yaml
enforcement: optional
override: {allowed: false}
```

## Profile Binding Without Coupling Profiles

Profiles remain independent of organizations. The catalog associates a general practice with a technology:

```yaml
# organization/catalogs/example-organization.yaml
profileBindings:
  java:
    - example-java-development-guidelines@1.0.0
  spring:
    - example-spring-guidelines@1.0.0
```

An architecture specific to `*-api` or `*-app` repositories must not be activated by the Spring Profile alone: both roles use the same stack. It must remain `optional` and be selected at the repository level.

## Project and Repository Activation

```yaml
engineering:
  inheritOrganization: true
  organizationCatalogs: [example-organization@1.0.0]

repositories:
  - id: product-api
    profiles: [java, spring, maven]
    engineering:
      practices:
        organization-api-guidelines@1.0.0:
          mode: enable

  - id: product-app
    profiles: [java, spring, maven]
    engineering:
      practices:
        organization-app-architecture@1.0.0:
          mode: enable
```

The `@version` suffix explicitly fails resolution if the installed Factory exposes a different version of the practice.

### Organization Only at Project Level

A project that depends on no organizational catalog can disable this layer without disabling its own conventions:

```yaml
engineering:
  inheritOrganization: true
  organizationCatalogs: []
  practices:
    product-architecture:
      mode: enable
      category: architecture
      ref: .ai/context/architecture.md
```

In this case, only explicit local practices and project context documents are sent to Skills. No organizational catalog is loaded implicitly.

## Adding Project-Specific Convention

Local conventions stay in `.ai/context/` and complement the catalog:

```yaml
repositories:
  - id: product-app
    engineering:
      practices:
        product-app-conventions:
          mode: enable
          category: convention
          ref: .ai/context/repositories/product-app-conventions.md
```

An authorized specialization of an existing practice uses `override`:

```yaml
engineering:
  practices:
    organization-java-development-guidelines@1.0.0:
      mode: override
      ref: .ai/context/java-development-specialization.md
```

With `inheritance.strategy: merge`, organizational content is preserved and local specialization is added. With `replace`, only the local document is provided. A `mandatory` or protected practice remains non-overrideable.

## Progressive Loading

Each Core Skill requests only the useful categories:

```yaml
engineeringContext:
  requires: [architecture, convention, security, testing]
```

The Runtime then filters by Profile, Skill, project, and repository. A Java guide is not sent to Flutter; a review practice is not loaded during `understand-task`.

## Updating the Catalog

1. modify and review the source documentation repository;
2. optionally create a guidelines tag;
3. update the submodule on a Factory branch;
4. increment the version of Practices whose content or governance changes;
5. update the `@version` references of affected projects;
6. run `aief validate` and context tests;
7. publish a new Factory version;
8. upgrade projects explicitly.

```bash
git -C organization/catalogs/guidelines fetch --tags
git -C organization/catalogs/guidelines checkout <TAG_OR_COMMIT>
git add organization/catalogs/guidelines
aief validate .
pytest -q
```

Never silently follow the main branch of the documentation repository from an already-published installation.

## Pre-Publication Checks

- [ ] unique and stable Practice identifier;
- [ ] stable catalog identifier and version;
- [ ] catalog inheritance without cycles;
- [ ] version consistent with content;
- [ ] category consumed by expected Skills;
- [ ] minimal profiles and skills applicability;
- [ ] enforcement justified;
- [ ] override explicitly allowed or forbidden;
- [ ] document resolved under `organization/`;
- [ ] submodule pinned on a known commit;
- [ ] repository activation tested;
- [ ] effective context inspected and fingerprinted;
- [ ] no project rules duplicated in organizational catalog.
