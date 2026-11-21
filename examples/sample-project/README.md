# Sample Project — Poly-repository Example

This example demonstrates how a project workspace may contain multiple independent Git repositories while using one project-level Factory context. The names, stacks and domains are illustrative: the Factory is agnostic of the technology and of the kind of repository (backend, frontend, mobile, data, infrastructure).

```text
sample-project/
├── .ai/
├── AGENTS.md
├── CLAUDE.md
├── backend/    # independent Git repository in a real checkout
└── frontend/   # independent Git repository in a real checkout
```

The example directories are placeholders only; they are not nested Git repositories in this package.
