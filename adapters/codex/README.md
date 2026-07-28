# Adapter — codex

Reference adapter for codex. Project bootstrap file: `AGENTS.md`.

Native skills such as `$implement` are plug-in entry points. They delegate deterministic orchestration to the shared `aief` Runtime and use Codex only for the agentic work described by the resolved Core Skill.

Do not use `/implement` in Codex: slash-prefixed commands belong to the Codex
client. Install the adapter under `~/.agents/skills`, restart Codex, then use
`$implement`, `/skills`, or a natural-language request. See
[`docs/27-codex-usage.md`](../../docs/27-codex-usage.md).
