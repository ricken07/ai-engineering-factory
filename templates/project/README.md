# Factory Project Template

Copy this directory into a project workspace root, then adapt `.ai/project.yaml`, `.ai/repository-map.yaml` and context files.

Do not copy the full Factory into the project. The project pins a Factory version and resolves it from the developer/runtime Factory home.

Replace placeholders only with verified project information. `context/` and `decisions/` are authoritative, `memory/` contains approved reusable knowledge, and `runtime/` contains gitignored task and execution state. Do not write inferred facts during initialization; use `promote-knowledge` for knowledge discovered later.
