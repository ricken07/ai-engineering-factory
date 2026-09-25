# Organization Engineering Catalog

This directory contains versioned organization standards and practices. Every YAML manifest is machine-readable; its adjacent Markdown document contains the knowledge supplied to agents after deterministic resolution.

The Factory itself is agnostic of any single organization: nothing in `core/` references a specific company, and a project may select zero organization catalogs at all (`organizationCatalogs: []`). This directory ships two catalogs purely as illustration — `factory-default` (generic conventions any project can use as-is) and `sample-organization` (a second, independent catalog demonstrating that a project may compose more than one at once; not to be confused with the `example-organization` placeholder id in `templates/organization/catalog.yaml`, which a company copies and renames to start its own). Neither is required, and neither carries any real organization's proprietary content. A company adopting the Factory maintains its own catalog separately (see `templates/organization/`) rather than committing its practices into this repository.

`mandatory` practices cannot be disabled or overridden. `default` practices are inherited when selected by a binding in an active organization catalog and may be specialized when explicitly allowed. `optional` practices require explicit enablement.

The Core never imports a concrete catalog directly. Projects select versioned
`OrganizationCatalog` contracts; those catalogs bind Practice IDs to neutral
technical Profiles. The Runtime constructs a repository- and Skill-specific
`EffectiveEngineeringContext` from only the selected catalogs.

A company maintaining its own, private organization catalog outside this
repository may pin it as a Git submodule under its own installation of the
Factory (or reference it by any other version-controlled path); this
repository does not ship one itself. `Practice` manifests always provide the
governance metadata, applicability, enforcement and version consumed by the
Runtime, whether their document lives alongside them or in a separately
maintained location. Never reference an absolute developer-machine path from
a Project.

## Integration governance

Organization engineering knowledge and integration governance share the same
inheritance principle but remain separate contracts. Integration provider
definitions live under `integrations/`, never in Core and never duplicated in a
Project. An organization selects the providers it allows, establishes defaults,
controls endpoint/authentication profiles and decides whether project-specific
MCPs are permitted.

A Project only binds an abstract capability to an authorized provider. Native
Claude/Codex files are generated adapter artifacts, not organization policy and
not project knowledge. Secret values belong to the developer or enterprise
runtime.

Until an executable organization integration-policy schema is available, the
installed Factory integration catalog is the effective allow-list and custom
project provider manifests fail closed. See
[`docs/13-agent-adapters-and-mcp.md`](../docs/13-agent-adapters-and-mcp.md) for
the normative resolution model.
