---
name: resolve-context
description: Load the smallest authoritative context needed for the active task. Use when a Factory workflow invokes the resolve-context capability.
---

# Resolve Context

## Objective

Load the smallest authoritative context needed for the active task.

## Procedure

Read project and repository maps first; expand to relevant domain, architecture, decisions, conventions, and repository sources; record every loaded source and exclude session memory as truth.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
