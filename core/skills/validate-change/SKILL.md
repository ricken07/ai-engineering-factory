---
name: validate-change
description: Run relevant profile and project validations and preserve complete evidence. Use when a Factory workflow invokes the validate-change capability.
---

# Validate Change

## Objective

Run relevant profile and project validations and preserve complete evidence.

## Procedure

Build a validation plan from impacted scope; execute authorized checks; record commands, results, failures, omissions, and whether failures are new or pre-existing.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
