# How to Use AIEF Documentation

This guide helps you navigate the 34 reference documents efficiently based on your role and current task.

## The Documentation Philosophy

AIEF's documentation is organized by **task and audience**, not by file number. The file numbers (00–33) reflect historical development order and are kept for stable references. Use them only if directly linked or cited.

**Your entry point is always one of these:**
1. The **README** for the 30-second pitch and quick start
2. The **INDEX.md** for organized navigation by use case
3. This document for guidance on how to navigate

## Three Ways to Find What You Need

### 1. By Role (Start Here)

**I am a…**

- **Developer using AIEF**
  - Start: [First Steps](23-first-steps.md)
  - Then: [Task Lifecycle](11-lifecycle.md)
  - If needed: [Execution Log](26-task-execution-log.md) to debug

- **Project lead setting up AIEF**
  - Start: [Installation Guide](22-project-installation-guide.md)
  - Then: [Project Adoption](08-project-adoption.md)
  - Then: [Agent Permissions](25-agent-permissions.md)

- **Operator managing AIEF at scale**
  - Start: [Runtime Model](04-runtime-model.md)
  - Then: [Workspace & Git Safety](18-workspace-git-safety.md)
  - Then: [Runtime Observability](32-runtime-observability.md)
  - Then: [Evaluation Harness](33-evaluation-harness.md)

- **Governance/Security lead**
  - Start: [Policy Resolution](05-policy-resolution.md)
  - Then: [Security Baseline](10-security.md)
  - Then: [Dynamic Policy Re-evaluation](20-dynamic-policy-reevaluation.md)

- **Knowledge architect at an organization**
  - Start: [Organization Engineering Context](16-organization-engineering-context.md)
  - Then: [Organization Knowledge Catalog](24-organization-knowledge-catalog.md)
  - Then: [Effective Engineering Context Resolver](21-effective-engineering-context.md)

- **Profile or adapter developer**
  - Start: [Extension Model](07-extension-model.md)
  - Then: [Agent Adapters & MCP](13-agent-adapters-and-mcp.md) for adapters, OR [Profile Runtime](15-profile-runtime.md) for profiles
  - Then: [Evaluation Harness](33-evaluation-harness.md)

### 2. By Task (What are you trying to do?)

**I need to…**

| Task | Start Here | Then Read |
|------|-----------|-----------|
| Understand what AIEF is | [Principles](01-principles.md) | [Reference Architecture](00-factory-reference-architecture.md) |
| Install AIEF in a project | [Installation Guide](22-project-installation-guide.md) | [Project Adoption](08-project-adoption.md) |
| Run my first command | [First Steps](23-first-steps.md) | [Task Lifecycle](11-lifecycle.md) |
| Debug a failed execution | [Execution Log](26-task-execution-log.md) | [Runtime Observability](32-runtime-observability.md) |
| Define organization practices | [Org Engineering Context](16-organization-engineering-context.md) | [Org Knowledge Catalog](24-organization-knowledge-catalog.md) |
| Set up governance rules | [Policy Resolution](05-policy-resolution.md) | [Dynamic Policy Re-evaluation](20-dynamic-policy-reevaluation.md) |
| Understand how context loads | [Context & Knowledge Lifecycle](06-context-and-memory.md) | [Effective Context Resolver](21-effective-engineering-context.md) |
| Set up GitLab integration | [GitLab Issues & Board](28-gitlab-issues-and-board.md) | [Task Tracking & Provider Runtime](17-task-tracking-provider-runtime.md) |
| Build a new Profile | [Extension Model](07-extension-model.md) | [Profile Runtime](15-profile-runtime.md) |
| Build a new Adapter | [Extension Model](07-extension-model.md) | [Agent Adapters & MCP](13-agent-adapters-and-mcp.md) |
| Ensure Git safety | [Workspace & Git Safety](18-workspace-git-safety.md) | [Idempotence & Leases](19-idempotence-execution-leases.md) |
| Understand execution leases | [Idempotence & Leases](19-idempotence-execution-leases.md) | [Runtime Model](04-runtime-model.md) |
| Import a documentation backlog | [Backlog Import Runtime](30-backlog-import-runtime.md) | [Task Tracking & Provider](17-task-tracking-provider-runtime.md) |
| Test AIEF or an adapter | [Evaluation Harness](33-evaluation-harness.md) | [Runtime Conformance](33-evaluation-harness.md) |
| Understand task dependencies | [Task Ordering & Readiness](31-task-ordering-and-readiness.md) | [Task Lifecycle](11-lifecycle.md) |
| Look up a term | [Glossary](12-glossary.md) | (Usually enough) |

### 3. By Category (Browse the organized topics)

See [INDEX.md](INDEX.md) for the full categorized list:

- **Getting Started** — Installation, first command, permissions
- **Concepts & Architecture** — Principles, conceptual model, architecture
- **Workflows & Execution** — Runtime model, task lifecycle, execution log
- **Governance & Policies** — Policy resolution, risk, approval gates
- **Context & Knowledge** — Knowledge lifecycle, organization practices
- **Integrations & Extensions** — Profiles, adapters, GitLab, backlog import
- **Workspace & Safety** — Git safety, idempotence, leases
- **Operations & Troubleshooting** — Observability, evidence chain, harness

---

## Document Sections (What to Expect)

Most AIEF documents follow this structure:

1. **Purpose** — Why this document exists, what problem it solves
2. **Concept diagram or visual** — How the pieces fit together
3. **Core sections** — The main content, divided by topic
4. **Examples** — Concrete code or configuration examples
5. **Cross-references** — Links to related documents

Each document is self-contained but linked to related ones. You don't need to read sequentially.

---

## Common Questions

**Q: I see document numbers like 05-policy-resolution.md. Should I read them in order?**

A: No. The numbers reflect historical development. Use [INDEX.md](INDEX.md) or the task-based table above to find what you need.

**Q: Some documents are in French, some in English. Should I worry?**

A: No. Choose the language you prefer; both are equally authoritative and complete. The Factory doesn't distinguish.

**Q: I found the README mentions docs I haven't read yet. Do I need to read all the background?**

A: No. Use the role-based and task-based sections above to pick *only* what's relevant to you right now. You can explore deeper later.

**Q: Is there a step-by-step tutorial for the whole thing?**

A: Not a single tutorial, but the **[Getting Started](INDEX.md#getting-started)** section + **[First Steps](23-first-steps.md)** walk you through the basics. Then explore by task.

**Q: Where are the examples and templates?**

A: Look in `templates/` (project and organization scaffolds) and `examples/` (reference projects and scenarios). Documentation points to them when relevant.

**Q: I'm stuck. Where do I ask for help?**

A: See **CONTRIBUTING.md** for how to report issues or ask questions.

---

## Navigation Shortcut

```
README
  ↓
This guide (00-HOW-TO-USE-THESE-DOCS.md)
  ↓
Choose your path:
  ├─ By role? → Use the "Three Ways" section above
  ├─ By task? → Use the task table above
  └─ Browse? → Go to INDEX.md
```

---

## Feedback on Documentation

If you found documentation confusing, unclear, or missing:

1. Open an issue with the document name and what was confusing
2. Suggest where the information should live instead
3. Offer to help improve it

See **CONTRIBUTING.md** for guidelines.

---

**Welcome to AIEF. Start with the path that matches your role.** You'll find everything you need from there.
