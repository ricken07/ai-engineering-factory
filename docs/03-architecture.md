# 03 — Architecture

## Layering

```text
┌──────────────────────────────────────────────┐
│                 Factory Core                 │
│ schemas · policies · standards · workflows  │
│                    skills                    │
└───────────────────┬──────────────────────────┘
                    │ extends / implements
        ┌───────────┼────────────┐
        │           │            │
 Organization   Integrations   Adapters
        │
     Profiles
        │           │            │
        └───────────┼────────────┘
                    │
                 Project
                    │
                 Workspace
                    │
                  Task
                    │
                Execution
```

## Dependency rule

Dependencies may point **toward Core contracts**, never from the Core toward a concrete provider, stack or agent.

Allowed:

```text
Project -> Profile -> Core
Profile -> Organization Practice contract
Project -> Integration -> Core
Agent Adapter -> Core
```

Forbidden:

```text
Core -> Spring
Core -> GitLab
Core -> Claude Code
Core -> Emmany
```

## Filesystem layout

```text
core/
├── schemas/
├── policies/
├── standards/
├── workflows/
└── skills/

profiles/
organization/
integrations/
adapters/
templates/
```

## Contract-first rule

A feature is introduced in this sequence:

1. concept,
2. schema/contract,
3. policy or standard,
4. workflow/skill usage,
5. provider/agent mapping.

This prevents implementation-specific behavior from leaking into the Core.
