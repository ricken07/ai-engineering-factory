---
name: submit-change
description: Plan or perform an authorized provider-neutral change submission. Use when a Factory workflow invokes the submit-change capability.
---

# Submit Change

## Objective

Plan or perform an authorized provider-neutral change submission.

## Procedure

Recheck gates and capability immediately before side effects; create one change request per repository when required; link related requests and report exact external results.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
