# 10 — Security Baseline

The Factory is not a security sandbox by itself. Agent runtime permissions and MCP/tool permissions remain critical.

## Baseline

- Default to least privilege.
- Secrets must not be stored in `.ai/memory/`, prompts or generated artifacts.
- Destructive operations require explicit approval.
- Protected branch merge remains policy-gated.
- Critical authentication/authorization/cryptography changes receive critical risk by default.
- External actions require both capability availability and policy permission.
- Generated code must be validated and reviewed according to task risk.
- Agents must not suppress failing tests merely to obtain a successful pipeline.

## Provider permissions

Integration configuration should expose only capabilities needed by the project. Do not grant write permissions to knowledge bases or SCM providers when the workflow only needs read access.
