# 01 — Factory Principles

## Purpose

The Factory exists to make AI-assisted software engineering repeatable,
governable and portable across projects, organizations and coding agents.

Its intended progression is:

```text
Augmented developer → Augmented team → Augmented delivery → Augmented engineering organization
```

## P01 — Agent agnostic

The Core never requires a specific coding agent. Agent-specific mechanics are implemented in `adapters/`.

## P02 — Technology agnostic

The Core never embeds stack-specific commands or architecture rules. Those live in composable `profiles/`.

## P03 — Tool/provider agnostic

The Core requests capabilities such as `source-control`, `task-provider` or `knowledge-base`. Provider-specific behavior belongs to `integrations/`.

## P04 — Project owns its context

Architecture, domain knowledge, conventions and durable decisions belong to the project workspace and versioned project knowledge.

## P05 — Factory owns the process

The agent does not invent a delivery process for each session. It executes a Factory workflow governed by policies.

## P06 — Progressive context loading

Load the minimum mandatory bootstrap context first, then expand only after impact analysis identifies what is relevant.

## P07 — Risk-based autonomy

Requested autonomy is only an upper request. Effective autonomy is the minimum allowed by Factory, profile, project, repository and task policies.

## P08 — Human accountability

Critical architecture, security, production and business-risk decisions remain subject to explicit human control.

## P09 — Traceability by design

Task, execution, decisions, changed scope, validations and submissions must be reconstructable without relying on agent chat history.

## P10 — Reproducible operating model

Different agents may reason differently but must honor the same workflow phases, gates, outputs and quality expectations.

## P11 — Explicit contracts

Projects, tasks, workflows, skills, policies, executions and handoffs are machine-readable contracts rather than implicit prompt conventions.

## P12 — Durable vs ephemeral knowledge

Session context is temporary. Task context is bounded to a unit of work. Project knowledge and ADRs are durable and governed.

## P13 — No silent relaxation

A lower layer may add restrictions but cannot silently relax a stronger Factory constraint.

## P14 — Least privilege for external actions

External actions (commit, push, submit, merge, update ticket, update documentation) require explicit capability and policy permission.
