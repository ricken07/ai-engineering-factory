# Adapter — claude-code

Reference adapter for claude-code. Project bootstrap file: `CLAUDE.md`.

Native skills such as `/implement` are plug-in entry points. They delegate deterministic orchestration to the shared `aief` Runtime and use Claude Code only for the agentic work described by the resolved Core Skill.
