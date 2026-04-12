# QA Report

Package: `ai-engineering-factory`
Version: `0.1.0`

Checks completed successfully:

- 17 JSON Schemas are valid Draft 2020-12 schemas.
- All YAML files parse successfully.
- Factory manifest validates against `factory.schema.json`.
- Project template validates against `project.schema.json`.
- Emmany poly-repo example validates against `project.schema.json`.
- Reference Task, PolicyDecision and Handoff validate against their schemas.
- All Core policies, standards, skills and workflows validate against their schemas.
- All workflow skill references resolve to existing Core skills.
- All provided profiles, integrations and adapters validate against their contracts.
- Emmany integration provider IDs resolve to packaged integrations.

This QA checks structural consistency, not the behavior of a specific coding agent or provider MCP.
