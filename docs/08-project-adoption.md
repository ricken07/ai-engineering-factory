# 08 — Project Adoption

## 1. Install/pin the Factory

Install the required Factory version on the workstation, for example:

```text
~/.gad/ai-engineering-factory/0.1.0/
```

## 2. Copy the project template

Copy `templates/project/` into the project workspace root.

## 3. Configure `.ai/project.yaml`

Declare:

- project identity,
- Factory version,
- mono/poly-repo strategy,
- repository list,
- enabled profiles,
- capability integrations,
- default/maximum autonomy.

## 4. Configure `.ai/repository-map.yaml`

Describe repository responsibilities and relationships. This is essential for poly-repo impact analysis.

## 5. Fill project context

Complete:

```text
.ai/context/project.md
.ai/context/architecture.md
.ai/context/domain.md
.ai/context/conventions.md
```

## 6. Initialize knowledge and runtime

Initialize `.ai/memory/` without speculative project facts. Keep `.ai/runtime/` ignored by Git and configure retention in `.ai/project.yaml`. Knowledge learned during work must pass through `promote-knowledge`; never copy task or session notes directly into durable project files.

## 7. Bootstrap agents

`AGENTS.md` and `CLAUDE.md` must remain thin bootstraps. They point to the Factory and project context; they must not duplicate the full Factory rules.

## 8. Start work from workspace root

Examples:

```text
/implement TASK-123
/review CR-52
/analyze TASK-456
```

Exact slash-command syntax is adapter-specific; the Factory workflow identity remains stable.
