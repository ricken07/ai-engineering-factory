# 10 — Security Baseline

The Factory is not a security sandbox by itself. Agent runtime permissions and MCP/tool permissions remain critical.

An `ENFORCED` assurance applies only to the AIEF-controlled execution path
named by its `EnforcementPoint`. AIEF does not infer that an agent is unable to
invoke the same operation outside Runtime. External or native mechanisms are
reported as `ENFORCEABLE`, `UNVERIFIED` or `UNAVAILABLE` until execution-bound
evidence exists.

## Baseline

- Default to least privilege.
- Secrets must not be stored in `.ai/memory/`, prompts or generated artifacts.
- Destructive operations require explicit approval.
- Protected branch merge remains policy-gated.
- Critical authentication/authorization/cryptography changes receive critical risk by default.
- External actions require both capability availability and policy permission.
- Generated code must be validated and reviewed according to task risk.
- Agents must not suppress failing tests merely to obtain a successful pipeline.
- Artifact-authored actor labels never authenticate their author or prove
  independent review.

## Provider permissions

Integration configuration should expose only capabilities needed by the project. Do not grant write permissions to knowledge bases or SCM providers when the workflow only needs read access.

## Native agent permissions

Every adopted project must review and commit the native permission templates
from `templates/project/.claude/` and `templates/project/.codex/`. They keep
routine Factory diagnostics and local work usable while requiring confirmation
for gates and external/Git mutations, and forbidding destructive recovery
shortcuts. See [Project agent permissions](25-agent-permissions.md).
