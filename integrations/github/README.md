# Integration — github

Maps abstract Factory capabilities to `github`. Actual MCP/tool configuration is project/runtime-specific and must respect the effective policy decision.
## MCP binding

This provider supplies source-control, task-provider and continuous-integration. The project selects it in `.ai/project.yaml`; the adapter resolves `GITHUB_MCP_URL` on the developer workstation. Keep `GITHUB_TOKEN` in the environment or native authentication store, never in project files.

The binding advertises connectivity and tool hints only. Factory policy still authorizes every operation.
