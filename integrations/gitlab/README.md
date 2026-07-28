# Integration — gitlab

Maps abstract Factory capabilities to `gitlab`. Actual MCP/tool configuration is project/runtime-specific and must respect the effective policy decision.
## MCP binding

This provider supplies source-control, task-provider and continuous-integration.
The project selects it in `.ai/project.yaml`; the adapter resolves
`GITLAB_MCP_URL` on the developer workstation. The official GitLab MCP endpoint
uses OAuth and Claude consumes that native flow. Current Codex CLI versions can
reject GitLab's issuer during OAuth discovery; the Codex adapter therefore uses
a temporary Bearer override through `GITLAB_TOKEN`. Do not add a personal
access token to project files. A separate
organization-managed gateway may use Bearer authentication only when its own
binding explicitly declares a token environment variable.

The binding advertises connectivity and tool hints only. Factory policy still authorizes every operation.

The native provider exposes only operations with a documented MCP mapping.
`update-task` and direct Issue Board administration are intentionally absent;
they require a separately governed organization gateway. See
[`docs/28-gitlab-issues-and-board.md`](../../docs/28-gitlab-issues-and-board.md).
