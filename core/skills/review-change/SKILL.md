---
name: review-change
description: Review the actual diff against task intent, plan, standards, risk, and validation evidence. Use when a Factory workflow invokes the review-change capability.
---

# Review Change

## Objective

Review the actual diff against task intent, plan, standards, risk, and validation evidence.

## Procedure

Check correctness, scope, architecture, security, regressions, tests, and unresolved issues; rank findings by severity and cite evidence.

The review must be independent of the implementation conclusion. Record
`details.independent: true`, `details.decision: approved` only when the diff,
acceptance criteria and validation evidence were checked, and keep unresolved
blocking findings in `details.blockingFindings`.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when user authority is required or bounded recovery is exhausted. Persist the answer in task execution state, not project memory.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
