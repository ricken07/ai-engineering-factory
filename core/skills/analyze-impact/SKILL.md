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
declared by the project. It lists every repository the task concerns, whether
the task analyses it or modifies it: a read-only analysis of a repository still
lists that repository. It must not be empty when the project declares
repositories. Do not place `repositories` at the artifact
root and never patch Task or Execution state manually.

List in `details.paths` the files or directories the change is expected to
modify, relative to the project root. A repository may restrict a critical
domain to some of its paths: the Runtime then applies that domain only when a
listed path matches, and applies it whenever the analysis lists no path in the
repository.
