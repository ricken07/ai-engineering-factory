---
name: submit-change
description: Plan or perform an authorized provider-neutral change submission. Use when a Factory workflow invokes the submit-change capability.
---

# Submit Change

## Objective

Plan or perform an authorized provider-neutral change submission.

## Procedure

Recheck gates and capability immediately before side effects; create one change request per repository when required; link related requests and report exact external results.

The Runtime refuses a completed submission unless `planning.yaml`,
`validation.yaml` and `review.yaml` form a complete evidence chain: every
acceptance criterion is verified, every required validation passed, and an
independent review is approved. Validation commands can be replayed from the
persisted plan with `aief execution replay-validation <execution-id>`.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when user authority is required or bounded recovery is exhausted. Persist the answer in task execution state, not project memory.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
