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
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
