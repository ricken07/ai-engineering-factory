---
name: analyze-impact
description: Identify direct, transitive, contract, data, test, and cross-repository impact without changing code. Use when a Factory workflow invokes the analyze-impact capability.
---

# Analyze Impact

## Objective

Identify direct, transitive, contract, data, test, and cross-repository impact without changing code.

## Procedure

Trace task intent through domain, repositories, components, public contracts, persistence, integrations, and tests; record unknowns and evidence.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when user authority is required or bounded recovery is exhausted. Persist the answer in task execution state, not project memory.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
`details.repositories` is mandatory and contains only repository identifiers
declared by the project. For a mutating workflow it must contain every impacted
repository and must not be empty. Do not place `repositories` at the artifact
root and never patch Task or Execution state manually.
