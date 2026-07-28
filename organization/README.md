# Organization Engineering Catalog

This directory contains versioned organization standards and practices. Every YAML manifest is machine-readable; its adjacent Markdown document contains the knowledge supplied to agents after deterministic resolution.

`mandatory` practices cannot be disabled or overridden. `default` practices are inherited when selected by a binding in an active organization catalog and may be specialized when explicitly allowed. `optional` practices require explicit enablement.

The Core never imports a concrete catalog directly. Projects select versioned
`OrganizationCatalog` contracts; those catalogs bind Practice IDs to neutral
technical Profiles. The Runtime constructs a repository- and Skill-specific
`EffectiveEngineeringContext` from only the selected catalogs.

External organization knowledge is pinned under `catalogs/` as a Git submodule.
Factory `Practice` manifests remain outside that submodule and provide the
governance metadata, applicability, enforcement and version consumed by the
Runtime. Clone installations with `--recurse-submodules` and never reference an
absolute developer-machine path from a Project.

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
