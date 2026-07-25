# Organization Engineering Catalog

This directory contains versioned organization standards and practices. Every YAML manifest is machine-readable; its adjacent Markdown document contains the knowledge supplied to agents after deterministic resolution.

`mandatory` practices cannot be disabled or overridden. `default` practices are inherited when selected by an applicable profile and may be specialized when explicitly allowed. `optional` practices require explicit enablement.

The Core never imports this catalog directly. Profiles reference practice IDs and the Runtime constructs a repository- and Skill-specific `EffectiveEngineeringContext`.

External organization knowledge is pinned under `catalogs/` as a Git submodule.
Factory `Practice` manifests remain outside that submodule and provide the
governance metadata, applicability, enforcement and version consumed by the
Runtime. Clone installations with `--recurse-submodules` and never reference an
absolute developer-machine path from a Project.
