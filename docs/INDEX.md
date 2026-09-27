# AI Engineering Factory — Documentation Index

This is the authoritative documentation structure for AIEF. Use this index to navigate by task, not by file number. The README points to key entry points; detailed references and advanced topics live here.

## Quick Navigation by Use Case

- **I'm new to AIEF** → Start with [Getting Started](#getting-started)
- **I'm setting up a project** → See [Setup & Installation](#setup--installation)
- **I'm configuring governance** → Go to [Governance & Policies](#governance--policies)
- **I need to understand how it works** → Read [Concepts & Architecture](#concepts--architecture)
- **I'm running a workflow** → See [Workflows & Execution](#workflows--execution)
- **I'm setting up an organization** → Check [Organization Knowledge](#organization-knowledge)
- **I'm integrating with external systems** → See [Integrations & Extensions](#integrations--extensions)
- **I'm troubleshooting or observing** → Go to [Operations & Troubleshooting](#operations--troubleshooting)
- **I need a term explained** → Use [Reference](#reference)

---

## Getting Started

**For developers and project leads just starting with AIEF.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [22 — Installation Guide](22-project-installation-guide.md) | Step-by-step Factory installation in a project | Operators, project leads |
| [23 — First Steps](23-first-steps.md) | Your first native command and workflow execution | Developers |
| [25 — Agent Permissions](25-agent-permissions.md) | Permission model, native permission templates, classification | Operators, security |
| [27 — Codex Usage](27-codex-usage.md) | Complete journey from setup to execution with Codex | Codex users, operators |

**What you'll learn:**
- How to install AIEF in a project (one-time per machine)
- How to initialize a project with Factory templates
- How to invoke your first `/analyze` or `$implement` command
- How permissions work between Factory, agent and OS

---

## Concepts & Architecture

**Foundational understanding of how AIEF is designed.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [00 — Reference Architecture](00-factory-reference-architecture.md) | Product purpose, responsibility model, how AIEF industrializes coding agents | Decision-makers, architects |
| [01 — Principles](01-principles.md) | 14 core design principles (P01–P14): agent-agnostic, tech-agnostic, human accountability, traceability | All |
| [02 — Conceptual Model](02-conceptual-model.md) | Visual hierarchy: Factory → Project → Workspace → Task → Execution. Concept definitions. | Architects, implementers |
| [03 — Architecture](03-architecture.md) | Layering (Core → Profiles → Organization → Integrations → Adapters). Dependency rules. Filesystem layout. | Architects, developers |
| [04 — Runtime Model](04-runtime-model.md) | How the agent boots, discovers project config, loads context, resolves policies, executes workflow | Operators, developers |
| [12 — Glossary](12-glossary.md) | Quick reference: definitions of all core terms | All |

**What you'll learn:**
- AIEF's place in the engineering pipeline
- Why AIEF doesn't replace Claude Code, it enables it
- The roles of Core, Profiles, Organization Catalog, Integrations, Adapters
- How a project boots and discovers its configuration

---

## Setup & Installation

**Configure a project, install adapters, set environment variables.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [22 — Installation Guide](22-project-installation-guide.md) | Clone Factory, install CLI, set `AI_FACTORY_HOME`, install adapter, init project | Operators, project leads |
| [08 — Project Adoption](08-project-adoption.md) | Organizing a project to work with AIEF: context locations, profiles, integrations, repository structure | Project leads |
| [25 — Agent Permissions](25-agent-permissions.md) | Permission templates for Claude Code, Codex; three-layer intersection: Factory policy + native + OS sandbox | Operators, security |

**Cross-reference:**
- See [Governance & Policies](#governance--policies) for `.ai/project.yaml` policy configuration
- See [Integrations & Extensions](#integrations--extensions) for integration and provider setup

---

## Workflows & Execution

**Understanding and running the Factory execution model.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [04 — Runtime Model](04-runtime-model.md) | Bootstrap sequence, runtime state, universal intake, executable commands | Operators, developers |
| [11 — Task Lifecycle](11-lifecycle.md) | Complete task journey: understand → context → impact → risk → plan → implement → validate → review → trace → submit | Developers, process owners |
| [14 — Universal Runtime](14-universal-runtime.md) | Runtime as coordination layer (not coding agent). Request pipeline, workflow compilation, artifact validation, gates | Architects, adapter developers |
| [23 — First Steps](23-first-steps.md) | Native commands vs. natural language. Command resolution. Execution receipt. Task log queries. | Developers |
| [26 — Task Execution Log](26-task-execution-log.md) | Local append-only journal (events.jsonl) for every task. Event structure, querying, observability. | Operators, debuggers |
| [31 — Task Ordering & Readiness](31-task-ordering-and-readiness.md) | Declaring dependencies between tasks. Runtime derives order and availability from state. | Operators, workflow designers |

**What you'll learn:**
- What happens when you run `/implement TASK-123`
- How context loads progressively
- What the execution receipt means
- How to query the task log for debugging
- How to express task dependencies and readiness

---

## Governance & Policies

**Risk, autonomy, approval gates, policy resolution.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [05 — Policy Resolution](05-policy-resolution.md) | Multi-layer policies (Factory → Profile → Project → Repository → Task). Resolution algorithm. Risk and autonomy escalation. | Governance, architects |
| [09 — Governance & Versioning](09-governance.md) | Semantic versioning, the published Git tag as the organization's single reference, release process, review requirements for schema/policy/workflow changes, compatibility checks, ownership model | Governance, release managers |
| [10 — Security Baseline](10-security.md) | Security principles, least privilege, no secrets in prompts, destructive operations, critical changes, permission templates | Security, operators |
| [20 — Dynamic Policy Re-evaluation](20-dynamic-policy-reevaluation.md) | Policies re-evaluated after impact analysis and planning. Monotonic risk/scope. Escalation audit trail. | Governance, operators |

**What you'll learn:**
- How to declare policies at Factory, project, repository or task level
- How policies combine and escalate (highest risk wins, lowest autonomy wins)
- What "gates" are and when they block actions
- How to trace governance decisions with PolicyDecision artifacts

---

## Context & Knowledge

**Managing project knowledge, organization practices, and effective context.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [06 — Context & Knowledge Lifecycle](06-context-and-memory.md) | Four tiers: Session (agent runtime) → Task runtime → Project memory (versioned) → Context (authoritative). Ownership and lifetime. | Architects, knowledge managers |
| [16 — Organization Engineering Context](16-organization-engineering-context.md) | What organization practices are, practice contract (YAML + Markdown), binding to profiles, inheritance, override | Knowledge architects |
| [21 — Effective Engineering Context Resolver](21-effective-engineering-context.md) | How context resolves per repository/Skill: mandatory practices + project catalogs + profiles + repo + task constraints | Architects, skill developers |
| [24 — Organization Knowledge Catalog](24-organization-knowledge-catalog.md) | Versioned, governed knowledge: repository guidelines, catalog structure, Practice manifests, OrganizationCatalog, profile management | Organization, knowledge managers |

**What you'll learn:**
- Difference between session, task, project and durable knowledge
- How to capitalize organization practices once and distribute to projects
- How progressive context loading works
- How profiles compose and override practices

---

## Integrations & Extensions

**Extending AIEF with profiles, integrations, and adapters.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [07 — Extension Model](07-extension-model.md) | Three mechanisms: Profiles (reusable tech/practice), Integrations (abstract capabilities), Adapters (agent-runtime mapping) | Architects, extenders |
| [13 — Agent Adapters & MCP](13-agent-adapters-and-mcp.md) | What adapters do, MCP binding, governance sources, installation flow, adapter responsibility vs. Factory responsibility | Adapter developers |
| [15 — Profile-driven Validation Runtime](15-profile-runtime.md) | How Skill validate-change discovers commands, executes safely (shell: false), resolves profiles | Profile developers, operators |
| [17 — Task Tracking & Provider Resolution](17-task-tracking-provider-runtime.md) | Task traceability: local vs. external provider. Tracking policy, provider resolution, idempotent operations. | Operators, integrations |
| [28 — GitLab Issues & Issue Board](28-gitlab-issues-and-board.md) | Using GitLab as task-provider. MCP mapping, core operations (get, search, create, comment, link), workflow labels | Operators, GitLab users |
| [30 — Backlog Import Runtime](30-backlog-import-runtime.md) | Convert documentation into tracker tickets. Preview before creation, approval gates, reuses Task Tracking contracts | Operators, backlog managers |

**What you'll learn:**
- How to write a Profile for a new technology stack
- How to map an external capability (e.g., GitLab issues) via Integration
- How to extend AIEF's validator for your tech stack
- How to import a documentation backlog into your task tracker

---

## Workspace & Safety

**Git safety, idempotence, execution ownership.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [18 — Workspace & Git Safety](18-workspace-git-safety.md) | Safety boundary, canonical Project State Store, WorkspaceBinding, worktree/check-out strategies and drift handling. | Operators, developers |
| [19 — Idempotence & Execution Leases](19-idempotence-execution-leases.md) | Execution-scoped ownership across worktrees/agents, replay-safe operation IDs and handoff. | Operators, adapter developers |

**What you'll learn:**
- How AIEF prevents unwanted Git state changes
- How execution leases work to prevent concurrent writes
- How to safely resume an execution in a different agent session

---

## Operations & Troubleshooting

**Observability, validation, testing, debugging.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [26 — Task Execution Log](26-task-execution-log.md) | Query and inspect the local task journal (events.jsonl) | Operators, debuggers |
| [29 — Evidence Chain & Validation Replay](29-evidence-chain-and-replay.md) | Acceptance criteria, revision-bound validation, trusted review identity and fingerprinted EvidenceBundle. | Developers, reviewers |
| [32 — Runtime Observability](32-runtime-observability.md) | Structured events and monotonic timing with explicit availability and redaction. | Operators, debuggers |
| [33 — Evaluation Harness](33-evaluation-harness.md) | Conformance levels plus explicit experimental conditions L0–L3 and reproducibility metadata. | Developers, QA |

**What you'll learn:**
- How to debug a failed task
- How to query execution logs for audit
- How to validate your adapter conforms to Factory contracts
- How to capture and replay evidence for reviews

---

## Reference

**Quick lookups and term definitions.**

| Document | Purpose | Audience |
|----------|---------|----------|
| [12 — Glossary](12-glossary.md) | Definitions of Core, Profile, Integration, Adapter, Task, Workflow, Skill, Policy, Standard, Gate, Execution, Artifact, Handoff, Workspace, Project memory | All |

---

## Document Organization by File Number

| Range | Category | Purpose |
|-------|----------|---------|
| 00–03 | Foundational | Reference architecture, principles, conceptual model, architecture |
| 04–06 | Runtime & execution | Runtime model, policy resolution, context & memory |
| 07–12 | Core concepts | Extension model, project adoption, governance, security, lifecycle, glossary |
| 13–21 | Runtime layers | Adapters, universal runtime, profiles, context resolution |
| 22–27 | Getting started | Installation, first steps, permissions, Codex usage, tracking, execution log |
| 28–33 | Operations | GitLab, backlog import, evidence chain, observability, evaluation harness, readiness |

---

## Cross-Reference Guide

**Need to understand a specific topic? Start here.**

| Topic | Primary | Secondary |
|-------|---------|-----------|
| **Permissions** | [25 — Agent Permissions](25-agent-permissions.md) | [10 — Security Baseline](10-security.md), [04 — Runtime Model](04-runtime-model.md) |
| **Policy and Risk** | [05 — Policy Resolution](05-policy-resolution.md) | [20 — Dynamic Policy Re-evaluation](20-dynamic-policy-reevaluation.md), [09 — Governance](09-governance.md) |
| **Organization Practices** | [16 — Org Engineering Context](16-organization-engineering-context.md) | [24 — Organization Knowledge Catalog](24-organization-knowledge-catalog.md), [21 — Effective Context](21-effective-engineering-context.md) |
| **Context Loading** | [06 — Context & Knowledge Lifecycle](06-context-and-memory.md) | [21 — Effective Context](21-effective-engineering-context.md) |
| **Task Execution** | [11 — Task Lifecycle](11-lifecycle.md) | [04 — Runtime Model](04-runtime-model.md), [26 — Execution Log](26-task-execution-log.md) |
| **External Integrations** | [17 — Task Tracking & Provider](17-task-tracking-provider-runtime.md) | [28 — GitLab](28-gitlab-issues-and-board.md), [30 — Backlog Import](30-backlog-import-runtime.md) |
| **Profile Development** | [15 — Profile Runtime](15-profile-runtime.md) | [07 — Extension Model](07-extension-model.md) |
| **Adapter Development** | [13 — Agent Adapters & MCP](13-agent-adapters-and-mcp.md) | [04 — Runtime Model](04-runtime-model.md), [14 — Universal Runtime](14-universal-runtime.md) |
| **Git Safety** | [18 — Workspace & Git Safety](18-workspace-git-safety.md) | [19 — Idempotence & Leases](19-idempotence-execution-leases.md) |
| **Debugging** | [26 — Execution Log](26-task-execution-log.md) | [32 — Runtime Observability](32-runtime-observability.md) |

---

## Language Note

This project uses French and English interchangeably. Documents are marked:
- 🇬🇧 English
- 🇫🇷 French

Both are equally authoritative. Choose the language you prefer.

---

## How the Documentation Fits with README

The **README** provides:
- Product overview and positioning
- Why AIEF exists
- Quick start (steps 1–6)
- What AIEF standardizes
- Supported agents and profiles
- Pointer to key documentation

This **INDEX** provides:
- Organized navigation by task and use case
- All 35 reference documents
- Cross-references between related docs
- Where to start based on your role

Use the **README** as your entry point. Use this **INDEX** to navigate the detailed documentation by topic.

---

**Last updated:** 2025-09-03 | **AIEF version:** 1.15.0+
