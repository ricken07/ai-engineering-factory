# 09 — Governance and Versioning

## Versioning

Factory releases use semantic versioning. Projects pin a Factory version.

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
