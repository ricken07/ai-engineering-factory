---
name: record-traceability
description: Record a reconstructable chain from task and decisions to changes, validations, and review. Use when a Factory workflow invokes the record-traceability capability.
---

# Record Traceability

## Objective

Record a reconstructable chain from task and decisions to changes, validations, and review.

## Procedure

Persist only evidence-backed facts; link repositories, decisions, artifacts, validation results, unresolved issues, and external references.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
