---
name: summarize-change
description: Produce a concise evidence-backed account of behavior, scope, validation, and residual risk. Use when a Factory workflow invokes the summarize-change capability.
---

# Summarize Change

## Objective

Produce a concise evidence-backed account of behavior, scope, validation, and residual risk.

## Procedure

Describe why and what changed by repository; report validations, review outcome, deviations, risks, and follow-up without reducing the summary to filenames.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when user authority is required or bounded recovery is exhausted. Persist the answer in task execution state, not project memory.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
