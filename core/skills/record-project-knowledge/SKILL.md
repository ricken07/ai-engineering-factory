---
name: record-project-knowledge
description: Record an approved memory candidate into the authorized durable project target with traceability. Use when a Factory workflow evaluates or records knowledge learned during a task.
---

# Record Project Knowledge

## Objective

Record an approved memory candidate into the authorized durable project target with traceability.

## Procedure

Verify explicit approval, target and current content immediately before writing; preserve source evidence; make the smallest coherent update; record its location and content hash. Reject stale, conflicting or unapproved candidates.

## Guardrails

- Read `skill.yaml` and apply referenced policies and standards.
- Separate verified evidence, inference, conflict and unknown information.
- Never copy secrets, credentials or transient reasoning.
- Use bounded recovery for execution failures; ask the user only for missing authority or after the recovery budget is exhausted.
- Return an output conforming to `output.schema.json`.

## Output

Return a structured summary, status, evidence, unknowns and skill-specific details.
