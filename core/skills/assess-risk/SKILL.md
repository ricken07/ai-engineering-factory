---
name: assess-risk
description: Classify execution risk and produce inputs for deterministic policy resolution. Use when a Factory workflow invokes the assess-risk capability.
---

# Assess Risk

## Objective

Classify execution risk and produce inputs for deterministic policy resolution.

## Procedure

Evaluate critical domains, security, data, migrations, public contracts, blast radius, reversibility, and uncertainty; never let uncertainty lower risk.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Separate evidence from inference and expose unknowns.
- Return output that validates against `output.schema.json`.
- Do not perform work owned by a later workflow phase.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `details`.
