---
name: promote-memory
description: Identify reusable knowledge from task evidence and propose controlled promotion without writing durable project knowledge. Use when a Factory workflow evaluates or records knowledge learned during a task.
---

# Promote Memory

## Objective

Identify reusable knowledge from task evidence and propose controlled promotion without writing durable project knowledge.

## Procedure

Review verified task artifacts; discard transient or already documented facts; classify reusable knowledge; compare it with authoritative sources; produce candidates and conflicts. Never approve or write the proposal.

## Guardrails

- Read `skill.yaml` and apply referenced policies and standards.
- Separate verified evidence, inference, conflict and unknown information.
- Never copy secrets, credentials or transient reasoning.
- Use bounded recovery for execution failures; ask the user only for missing authority or after the recovery budget is exhausted.
- Return an output conforming to `output.schema.json`.

## Output

Return a structured summary, status, evidence, unknowns and skill-specific details.
