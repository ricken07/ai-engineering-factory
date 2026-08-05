# 06 — Context and Knowledge Lifecycle

## Principle

The Factory is an organizational process reference, not project memory. A session discovers, a task preserves, project memory capitalizes, and context or decision records make knowledge authoritative.

The more durable and structural information becomes, the more explicit its validation and write controls must be.

## Four tiers

| Tier | Owner | Lifetime | Durable authority |
|---|---|---|---|
| Session | Agent runtime | Session | None |
| Task | Project runtime | Task and handoff retention | Task only |
| Project memory | Project | Versioned | Approved reusable knowledge |
| Context / decision | Project | Versioned | Authoritative knowledge |

Factory standards, policies, workflows and skills are maintained separately as organizational references.

### Session

Contains inspected files, temporary hypotheses, searches and current reasoning. It is agent-specific, ephemeral and never a project source of truth.

### Task

Contains verified state required to resume one task: understanding, context selection, impact, risk, policy decision, plan, task decisions, validations, review, recovery attempts and handoff. It is portable across agents but does not automatically become project knowledge.

### Project memory

Contains approved, reusable patterns, constraints and lessons not represented more naturally elsewhere. It must remain concise, scoped, evidenced and reviewable.

### Context and decisions

Context documents describe accepted project, architecture, domain and conventions. Decision records capture approved structural choices and consequences. They have greater authority than informal project memory.

## Runtime layout

```text
.ai/runtime/
├── tasks/<task-id>/
│   ├── task.yaml
│   ├── understanding.yaml
│   ├── context.yaml
│   ├── impact.yaml
│   ├── risk.yaml
│   ├── policy-decision.yaml
│   ├── plan.yaml
│   ├── decisions.yaml
│   ├── validation.yaml
│   ├── review.yaml
│   └── handoff.yaml
└── executions/<execution-id>/
    ├── execution.yaml
    └── <phase-artifacts>.yaml
```

Runtime is gitignored by default. A project may publish task summaries and evidence to its task or change provider. Retention is configured by the project and cleanup must never remove the only durable copy of required evidence.

## Versioning and merge conflicts

Version the durable project truth: `.ai/project.yaml`, the repository map, approved context, decisions, validated memory and the integration lock. Keep `.ai/runtime/` ignored because it is generated, local execution state.

When durable `.ai/` files conflict during a merge, resolve them as project code with human review. Preserve both sides until the intended project truth is decided; do not silently choose the local or remote version. Revalidate the resulting configuration and record significant policy, repository or provider changes as a decision.

## Progressive loading

Always load project configuration, repository map, active task, selected workflow and applicable policies. Then load only relevant context, decisions, memory entries, repository documents and profiles. Do not load all project memory defensively.

## Authority and freshness

Governance constraints resolve separately from knowledge authority.

```text
Factory policy → project policy → repository policy → task constraint
```

The most restrictive applicable governance rule wins.

```text
Approved decision → official context → project configuration
→ task source → project memory → task memory → session observation
```

A newer task may intentionally request an authoritative source to change. Record that as a conflict and request the required authority; never silently ignore either source.

## Controlled promotion

```text
Verified task evidence
  → reusable beyond the task?
  → already documented?
  → conflict check
  → MemoryCandidate
  → human approval of statement and target
  → durable write
  → KnowledgePromotion record
```

`promote-memory` only proposes. `record-project-knowledge` writes only an explicitly approved candidate. A changed statement or target invalidates prior approval.

Targets are project memory for operational knowledge, project context for accepted descriptive truth, project conventions for engineering rules, and decision records for structural decisions.

## Safety and hygiene

- Never persist credentials, tokens, private keys, secrets or private reasoning.
- Never promote unverified session observations.
- Keep source task, evidence, approval and review date.
- Mark stale entries as superseded rather than silently rewriting history.
- Prefer the authoritative source over duplicating it in project memory.
- Use handoff artifacts rather than agent conversation history for multi-agent continuation.
