---
name: create-plan
description: Create the smallest sufficient, ordered, and verifiable implementation plan. Use when a Factory workflow invokes the create-plan capability.
---

# Create Plan

## Objective

Create the smallest sufficient, ordered, and verifiable implementation plan.

## Procedure

Map each acceptance criterion to repository actions and validation; order cross-repository dependencies; identify gates, rollback needs, and unresolved blockers.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when user authority is required or bounded recovery is exhausted. Persist the answer in task execution state, not project memory.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
