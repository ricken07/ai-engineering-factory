---
name: understand-task
description: Establish a reliable task interpretation before proposing implementation. Use when a Factory workflow invokes the understand-task capability.
---

# Understand Task

## Objective

Establish a reliable task interpretation before proposing implementation.

## Procedure

Read the authoritative task source; extract objective, expected behavior, acceptance criteria, constraints, facts, assumptions, and open questions; stop when ambiguity materially changes the result.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
