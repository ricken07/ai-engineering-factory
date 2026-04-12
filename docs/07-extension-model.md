# 07 — Extension Model

The Core is extended through three mechanisms.

## Profiles

Profiles provide reusable technical/practice knowledge such as Java, Spring, Maven or Flutter. Profiles may be composed.

Example:

```yaml
profiles:
  - java
  - spring
  - maven
```

A profile may define discovery hints, common validation commands, technical conventions and additional restrictive policies. It must not contain project-specific domain facts.

## Integrations

Integrations implement abstract capabilities:

- `source-control`
- `task-provider`
- `knowledge-base`
- `continuous-integration`

Examples: GitLab, GitHub, Jira and Confluence.

## Agent adapters

Adapters translate Factory semantics into the conventions supported by an agent runtime. The adapter does not redefine the workflow. It maps the same Core workflow and skill contracts to Claude Code, Codex or future agents.
