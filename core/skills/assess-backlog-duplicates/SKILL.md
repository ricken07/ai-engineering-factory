---
name: assess-backlog-duplicates
description: Assess drafted backlog candidates against existing external tickets before any creation is proposed. Use when a Factory workflow invokes the assess-backlog-duplicates capability.
---

# Assess Backlog Duplicates

## Objective

For every drafted candidate, search the configured task-provider with the Runtime-prepared query and return an assessed set of matches, so no candidate reaches creation without a duplicate check.

## Procedure

For each candidate query, search the configured task-provider; for every plausible match, record its reference, title, confidence and rationale, and recommend `link-existing`, `review` or `ignore`; return an empty match list for a candidate with no plausible match.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Search through the resolved `task-provider` capability only; never name or assume a specific provider in this Skill's own reasoning.
- A `link-existing` recommendation requires a concrete matched reference; never fabricate one.
- Return output that validates against `output.schema.json`.
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Do not create or link anything; that remains a human/autonomy-gated Runtime step.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, and `matches` (candidate id to match list).
