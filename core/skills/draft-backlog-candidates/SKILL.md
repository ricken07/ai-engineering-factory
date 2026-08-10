---
name: draft-backlog-candidates
description: Turn a documentation corpus into a neutral, provider-agnostic backlog candidate list. Use when a Factory workflow invokes the draft-backlog-candidates capability.
---

# Draft Backlog Candidates

## Objective

Turn the source files listed by a backlog import plan into a neutral candidate list — epics, features, tasks, bugs — without any provider-specific field.

## Procedure

Read every listed source file; extract one candidate per epic/feature/task/bug the organization-rules configuration's granularity calls for, with a title, description and acceptance criteria; assign hierarchy (`type`, `parent`, `dependsOn`) and `labels` strictly from what the configuration and the source text state; stop and ask when the configuration leaves grouping, hierarchy or granularity ambiguous for a given source.

## Guardrails

- Read `skill.yaml` and obey its mode, rules, standards, policies, and capability requirements.
- Every candidate needs a stable, unique id; `parent`/`dependsOn` must reference another candidate's id from this same batch.
- Never assign a provider-specific field — the candidate model is `type`, `title`, `description`, `acceptanceCriteria`, `parent`, `dependsOn`, `labels` only.
- Return output that validates against `output.schema.json`.
- On failure, diagnose and try a distinct evidence-backed strategy within the recovery budget; never repeat an identical attempt.
- Ask one precise user question only when the organization-rules configuration does not resolve the ambiguity. Persist the answer in the import's state, not project memory.
- Do not perform duplicate search or provider creation; those are later steps.

## Output

Produce a structured result with `summary`, `status`, `evidence`, `unknowns`, `candidates`, and `openQuestions`.
