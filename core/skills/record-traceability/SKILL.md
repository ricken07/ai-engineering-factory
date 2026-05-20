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
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when user authority is required or bounded recovery is exhausted. Persist the answer in task execution state, not project memory.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
