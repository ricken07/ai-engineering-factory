# AI Engineering Factory

![Status](https://img.shields.io/badge/status-alpha-orange) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

AI Engineering Factory (AIEF) is an agent-independent engineering runtime and governance layer that turns developer intent into contextualized, governed and traceable software engineering workflows executed by coding agents.

**AIEF does not replace Claude Code or Codex. It defines the engineering system in which they operate.**

> The developer expresses intent; the Factory carries the engineering process.

Organizations define how engineering should be performed — standards, practices, context, autonomy, validation and traceability — independently of the coding agent executing the work.

Agents change. Models change. Developer tools change. Engineering rules should not have to.

## Project status: Alpha

The current Factory release is `1.0.0`. AIEF is functional within its current scope, while its versioned contracts (`apiVersion: aief.dev/v1alpha1`) and configuration surface may still evolve.

## Why AIEF?

Coding agents are powerful, but their use is often shaped by individual prompts, local context and informal validation. AIEF provides a stable engineering layer between developer intent and agentic work:

```text
Developer intent
        ↓
AIEF Runtime
  Task + Context + Policies + Workflow
        ↓
Coding agent
        ↓
Validation + Traceability
```

The developer does not need to restate the project architecture, organization conventions, testing rules or approval policy for every task.

## What AIEF standardizes

### Independence

- Agent-agnostic contracts and adapters.
- A technology-agnostic Core with no stack dependency.

### Engineering knowledge

- Organization-owned practices and standards.
- Project-owned context and progressive context loading.

### Governance

- Risk-based autonomy and explicit human accountability.
- Gates for protected actions and most-restrictive-policy resolution.
- A fingerprinted governed execution plan linking policy decisions to Runtime controls.

### Execution

- Deterministic workflow state, ordering and workspace safety.
- Traceability by design for Tasks, Executions and artifacts.

## AIEF is / AIEF is not

| AIEF is | AIEF is not |
| --- | --- |
| An engineering runtime and governance layer | A coding agent |
| An agent-independent execution system | A new LLM |
| A context, workflow and policy system | An IDE |
| A shared contract for supported agents | A fork or reimplementation of an agent |

## Deterministic Runtime, agentic work

| AIEF Runtime | Coding agent |
| --- | --- |
| Task and Execution state | Understand intent |
| Workflow order | Analyze code |
| Policy resolution | Design the implementation |
| Risk, autonomy and gates | Modify code |
| Workspace safety | Reason about trade-offs |
| Traceability | Produce engineering artifacts |

If a decision can be derived from contracts, state or policies, it belongs to AIEF. If it requires understanding software or business meaning, it belongs to the coding agent.

## How it works

```text
Request
→ IntentResolution
→ Task
→ Workflow
→ Execution
→ Artifacts
→ Gates
→ Handoff
```

Explicit commands and natural language enter the same Runtime and are normalized identically. Commands are shortcuts, not a separate execution path, and always activate the Runtime for their own execution.

Natural language is gated by `activation.mode` in `.ai/project.yaml`, on by default at installation:

| `activation.mode` | Native command | Natural language |
| --- | --- | --- |
| `auto` (default) | Runs directly. | The agent asks for explicit confirmation before routing through the Runtime; declined requests are handled directly. |
| `manual` | Runs directly, activating the Runtime for that execution only. | Never routed through the Runtime. |

`aief run`/`aief intake` enforce this themselves — an unconfirmed or disabled natural-language request is refused before any Task is persisted, not just discouraged by adapter instructions. See [`docs/23-first-steps.md`](docs/23-first-steps.md#2-native-command-or-free-text).

## A developer experience

```text
Developer
  "Fix the issue where FAILED transactions remain PENDING."
                         │
                         ▼
AIEF Runtime
  Request → Task → Context → Impact → Risk → Plan
                         │
                         ▼
Claude Code / Codex
  Implementation → Validation → Review → Traceability
```

## Quick start

The complete installation procedure, including adapter permissions and MCP activation, is available in [`docs/22-project-installation-guide.md`](docs/22-project-installation-guide.md).

**1. Select and clone a Factory release:**

```bash
export AIEF_VERSION="1.0.0"
git clone <FACTORY_GIT_URL> "$HOME/.local/share/aief/$AIEF_VERSION"
```

**2. Install the CLI:**

```bash
uv tool install "$HOME/.local/share/aief/$AIEF_VERSION"
aief --help
```

A plain `pip install -e .` from the clone also works.

**3. Point agents at the installation:**

```bash
export GAD_AI_FACTORY_HOME="$HOME/.local/share/aief/$AIEF_VERSION"
```

**4. Install an adapter, starting with a dry run:**

```bash
aief setup-adapter claude-code --factory "$GAD_AI_FACTORY_HOME"
aief setup-adapter claude-code --factory "$GAD_AI_FACTORY_HOME" --execute
```

**5. Initialize a project:**

```bash
cp -R "$GAD_AI_FACTORY_HOME/templates/project/.ai" "$PROJECT_ROOT/.ai"
cp "$GAD_AI_FACTORY_HOME/templates/project/AGENTS.md" "$PROJECT_ROOT/AGENTS.md"
cp "$GAD_AI_FACTORY_HOME/templates/project/CLAUDE.md" "$PROJECT_ROOT/CLAUDE.md"
```

Edit `.ai/project.yaml` with the repositories, profiles, autonomy and organization catalogs for the project. Organization-specific practices belong in a separate catalog; the `core/` directory remains unchanged.

**6. Validate and run a first non-mutating request:**

```bash
aief validate "$PROJECT_ROOT" --factory "$GAD_AI_FACTORY_HOME"
aief doctor "$PROJECT_ROOT"
```

```text
/analyze Analyze the current architecture without modifying any code.
```

## Effective Engineering Context

AIEF turns engineering practices into executable context for coding agents:

```text
Organization
→ Profile
→ Project
→ Repository
→ Task
→ Effective Engineering Context
```

Organizations define practices once. Projects select the catalogs they need, repositories select relevant profiles, and each Skill receives only the context required for its work. Resolved practices carry provenance and content hashes so agents can verify that they are working from the same knowledge.

An organization may use the Factory-provided baseline, create its own catalog, or select no organization catalog at all. See [`docs/16-organization-engineering-context.md`](docs/16-organization-engineering-context.md) and [`docs/24-organization-knowledge-catalog.md`](docs/24-organization-knowledge-catalog.md).

## Supported agents

| Agent | Native entry point |
| --- | --- |
| Claude Code | `/implement`, `/analyze`, `/fix`, `/refactor`, `/test`, `/review`, `/document` |
| Codex | `$implement`, `$analyze`, `$fix`, `$refactor`, `$test`, `$review`, `$document` |

Both adapters map the same Core Workflows and Skills. The difference is invocation syntax.

## Profiles and integrations

Profiles provide technology-specific knowledge without adding technology dependencies to `core/`. Available profiles include generic, Java, Spring, Maven, Node, React and Flutter.

Integrations expose provider-neutral capabilities such as source control, task tracking, knowledge bases and continuous integration. A project selects a capability and provider in `.ai/project.yaml`; secrets are never stored there.

## Architecture

```text
core/           agent-, stack- and provider-agnostic Runtime, schemas and policies
profiles/       reusable technology and practice knowledge
organization/   organization standards and practices, selected per project
integrations/   capability-to-provider contracts
adapters/       thin translations for supported agents
templates/      project and organization scaffolds
examples/       reference projects and scenarios
aief/           Python package and CLI
docs/           architecture and operating model
tests/          Runtime, policy, context and adapter conformance tests
```

The Core must never depend on a stack, provider or agent. Project-specific truth lives in the project's `.ai/` directory, not inside the Factory installation. See [`docs/03-architecture.md`](docs/03-architecture.md).

## Documentation

AIEF documentation is organized by use case and audience, not by file number. **Start here:**

- **Full documentation index:** [`docs/INDEX.md`](docs/INDEX.md) — organized by task, audience and role
- **Quick reference by use case:**
  - **New to AIEF?** Start with [Getting Started](docs/INDEX.md#getting-started)
  - **Configuring a project?** See [Setup & Installation](docs/INDEX.md#setup--installation)
  - **Understanding the system?** Read [Concepts & Architecture](docs/INDEX.md#concepts--architecture)
  - **Running workflows?** Go to [Workflows & Execution](docs/INDEX.md#workflows--execution)
  - **Setting up governance?** Check [Governance & Policies](docs/INDEX.md#governance--policies)
  - **Defining organization practices?** See [Context & Knowledge](docs/INDEX.md#context--knowledge)
  - **Extending AIEF?** Read [Integrations & Extensions](docs/INDEX.md#integrations--extensions)
  - **Troubleshooting?** Go to [Operations & Troubleshooting](docs/INDEX.md#operations--troubleshooting)

**Core entry-point documents:**

| Document | Audience | Start here if... |
| --- | --- | --- |
| [01 — Principles](docs/01-principles.md) | All | You want to understand AIEF's design philosophy |
| [03 — Architecture](docs/03-architecture.md) | Architects, developers | You want to understand the layering and dependency model |
| [04 — Runtime Model](docs/04-runtime-model.md) | Operators, developers | You want to understand how AIEF boots and runs |
| [22 — Installation Guide](docs/22-project-installation-guide.md) | Operators, project leads | You're setting up AIEF in a new project |
| [23 — First Steps](docs/23-first-steps.md) | Developers | You're running your first command |
| [16 — Organization Engineering Context](docs/16-organization-engineering-context.md) | Architects | You're defining organization practices |
| [13 — Agent Adapters & MCP](docs/13-agent-adapters-and-mcp.md) | Adapter developers | You're extending AIEF for a new agent |
| [32 — Runtime Observability](docs/32-runtime-observability.md) | Operators, debuggers | You need to understand how to observe execution |
| [33 — Evaluation Harness](docs/33-evaluation-harness.md) | QA, developers | You're testing AIEF or an adapter |

**All 35 reference documents** are indexed, cross-referenced and organized in [`docs/INDEX.md`](docs/INDEX.md).

## Security

See [`SECURITY.md`](SECURITY.md) for vulnerability reporting and the supported-version policy.

## Research baseline observability

Executions persist monotonic duration measurements, explicit availability for
unknown metrics, actor provenance, review-independence status, provider-neutral
enforcement assurance, reproducibility metadata and a fingerprinted evidence
bundle. These contracts make a run auditable; they do not claim that AIEF
improves quality, speed, effort, policy compliance or cost before controlled
experiments are performed.

Linked Git worktrees share the canonical Project State Store in the main
checkout. A worktree is only an Execution Workspace; its local path is not a
Task or Execution identifier. Existing non-canonical Runtime state causes a
fail-closed conflict instead of silent state selection.

Claims are classified as follows:

- **IMPLEMENTED:** Runtime validation records commands, outcomes, timestamps,
  trusted Runtime verifier and repository revisions.
- **CONDITIONAL:** independent review is provable only with distinct trusted
  producer and reviewer identities.
- **NOT SUPPORTED:** AIEF does not intercept every Git or process invocation
  outside its represented Runtime path.
- **EXPERIMENTALLY UNPROVEN:** improvements in quality, reproducibility,
  compliance, effort, speed and cost require the L0–L3 experiments.

## Contributing

Contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, tests and contribution guidelines. See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community standards.

## Roadmap

For current capabilities, limitations and planned work, see the [CHANGELOG](CHANGELOG.md) and the GitHub issues tracker.

## License

MIT — see [`LICENSE`](LICENSE).
