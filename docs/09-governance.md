# 09 — Governance and Versioning

## Versioning

Factory releases use semantic versioning. The organization's single reference
for the Factory is a published Git tag (`vX.Y.Z`) on its canonical
repository — never an untagged commit, a branch, or a workstation-specific
clone that has drifted from a tag. `factory.yaml#metadata.version` and
`VERSION` must equal `X.Y.Z` for tag `vX.Y.Z`; `pyproject.toml#project.version`
must match as well, so `pip`/`uv` report the same version as `aief`.

A project pins the tag it depends on in `.ai/project.yaml#factory.version`.
This is not advisory: `RuntimeService` refuses to start when the requested
version does not exactly match the installed `factory.yaml`, so a project
cannot silently run against a Factory build that drifted from its declared
tag. This fail-closed check is what makes "the tag is the reference" a
guarantee rather than a convention — see [`04-runtime-model.md`](04-runtime-model.md).

## Release process

1. Land the change on the default branch; land no unrelated version bump in the same commit.
2. Bump `factory.yaml#metadata.version`, `VERSION` and `pyproject.toml#project.version` together, in one commit.
3. Run the compatibility checks below.
4. Tag the release commit `vX.Y.Z` and push the tag; this tag is the artifact every team member and every project resolves through `AI_FACTORY_HOME`, whether by cloning it fresh or pointing an existing shared installation at it. No other channel (a branch, an untagged commit, a rebuilt local copy) is authoritative.
5. Announce the tag to teams already pinned to an older one; upgrading is explicit per project, never automatic — see [`22-project-installation-guide.md`](22-project-installation-guide.md#14-factory-upgrade).

## Changes requiring review

At minimum, review changes to:

- Core schemas,
- risk/autonomy rules,
- human approval rules,
- workflow phase ordering,
- capability semantics,
- durable memory rules.

## Compatibility

Before releasing a new Factory version:

1. validate all JSON Schemas,
2. parse all YAML manifests,
3. verify workflow skill references,
4. verify integration capability references,
5. validate project template examples,
6. run reference scenarios.

## Ownership

A central engineering governance group should own Core changes. Project teams own their `.ai/` context and may contribute reusable profiles/integrations through review.

## Research baseline claim discipline

Code, schemas and tests support claims about deterministic policy resolution,
fingerprinted governed plans, Runtime-observed validation, explicit enforcement
assurance and reviewer independence when trusted identities exist. They do not
establish improvements in quality, reproducibility, policy compliance, human
effort, delivery speed or cost, nor superiority over another framework or
agent. Those remain experimental questions.

Once the Research Baseline freeze commit is selected, behavior, policies and
benchmark scenarios remain unchanged through the experimental campaign. A
future experimental failure is evidence first, not automatic authorization to
modify the subject. Infrastructure-only corrections must demonstrate that they
do not alter the studied behavior and must be recorded separately.
