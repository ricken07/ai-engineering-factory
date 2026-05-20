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
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when user authority is required or bounded recovery is exhausted. Persist the answer in task execution state, not project memory.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
