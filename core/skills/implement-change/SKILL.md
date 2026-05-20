---
name: implement-change
description: Execute only the approved plan within the active PolicyDecision. Use when a Factory workflow invokes the implement-change capability.
---

# Implement Change

## Objective

Execute only the approved plan within the active PolicyDecision.

## Procedure

Verify assumptions against code; apply the smallest coherent change; preserve unrelated behavior and tests; stop and reassess when scope or risk materially changes.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when user authority is required or bounded recovery is exhausted. Persist the answer in task execution state, not project memory.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
