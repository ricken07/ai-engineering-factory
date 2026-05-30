# Integration — confluence

Maps abstract Factory capabilities to `confluence`. Actual MCP/tool configuration is project/runtime-specific and must respect the effective policy decision.
## MCP binding

This provider supplies knowledge-base. The project selects it in `.ai/project.yaml`; the adapter resolves `CONFLUENCE_MCP_URL` on the developer workstation. Keep `CONFLUENCE_TOKEN` in the environment or native authentication store, never in project files.

The binding advertises connectivity and tool hints only. Factory policy still authorizes every operation.
