# QA Report

Package: `ai-engineering-factory`
Version: `1.1.0`

Checks completed successfully:

- All packaged JSON Schemas, including task memory and knowledge promotion contracts, are valid Draft 2020-12 schemas.
- All YAML files parse successfully.
- Factory manifest validates against `factory.schema.json`.
- Project template validates against `project.schema.json`.
- Emmany poly-repo example validates against `project.schema.json`.
- Reference Task, PolicyDecision and Handoff validate against their schemas.
- All Core policies, standards, skills and workflows validate against their schemas.
- All workflow skill references resolve to existing Core skills.
- All provided profiles, integrations and adapters validate against their contracts.
- Emmany integration provider IDs resolve to packaged integrations.
- Every Core workflow and skill references bounded recovery.
- Core agnosticity is tested against project, stack, provider and agent leakage.
- Skill output examples validate against their output schemas.
- Knowledge approval is cryptographically bound to candidate content and target.

This QA checks structural consistency, not the behavior of a specific coding agent or provider MCP.
