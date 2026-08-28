# Emmany - AI Engineering Configuration Example

This directory demonstrates how a poly-repository project consumes the centrally installed Factory. It is reference data, not an active production configuration.

- `project.yaml` selects Factory version, profiles and provider integrations.
- `integration-lock.yaml` demonstrates the generated, secret-free provider resolution committed by a project.
- `repository-map.yaml` explains the relationship between the API and application repositories.
- `context/` contains example project-owned knowledge.
- `decisions/` and `memory/` illustrate durable knowledge boundaries.
- `runtime/` would contain local cross-agent task state and remains ignored.

Factory policies and workflows are not copied here. Agent-native skills resolve them through the Codex or Claude Code adapter.
