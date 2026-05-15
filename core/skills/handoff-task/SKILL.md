---
name: handoff-task
description: Create self-contained portable execution state for another agent or session. Use when a Factory workflow invokes the handoff-task capability.
---

# Handoff Task

## Objective

Create self-contained portable execution state for another agent or session.

## Procedure

Capture task, workflow, policy decision, completed and next phases, artifacts, repository state, decisions, blockers, and exact continuation instructions.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
