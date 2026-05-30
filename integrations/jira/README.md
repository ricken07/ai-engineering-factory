# Integration — jira

Maps abstract Factory capabilities to `jira`. Actual MCP/tool configuration is project/runtime-specific and must respect the effective policy decision.
## MCP binding

This provider supplies task-provider. The project selects it in `.ai/project.yaml`; the adapter resolves `JIRA_MCP_URL` on the developer workstation. Keep `JIRA_TOKEN` in the environment or native authentication store, never in project files.

The binding advertises connectivity and tool hints only. Factory policy still authorizes every operation.
