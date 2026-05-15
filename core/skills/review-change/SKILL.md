---
name: review-change
description: Review the actual diff against task intent, plan, standards, risk, and validation evidence. Use when a Factory workflow invokes the review-change capability.
---

# Review Change

## Objective

Review the actual diff against task intent, plan, standards, risk, and validation evidence.

## Procedure

Check correctness, scope, architecture, security, regressions, tests, and unresolved issues; rank findings by severity and cite evidence.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
