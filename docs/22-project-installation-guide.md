# 22 — Installing AI Engineering Factory in a Project

This document is the target procedure for connecting an existing project to the AI Engineering Factory. The Factory itself stays agnostic of any organization or project: cloning it installs only `core/`, `profiles/`, `adapters/` and `integrations/`, never a specific company's practices. An organization normally installs and pins one Factory version **once**, as the shared reference every team member and every project points to; a project only ever receives its own `.ai/` template and agent bootstrap files. If the organization also maintains its own engineering practices, it defines and hosts that catalog separately — never committed into this repository — and each project selects it explicitly. See [`organization/README.md`](../organization/README.md) and [`24-organization-knowledge-catalog.md`](24-organization-knowledge-catalog.md).

After installation, continue with [`23-first-steps.md`](23-first-steps.md) for the daily workflow from Claude Code or Codex.

Examples use version `1.15.0`. Replace values between `<...>` before execution.

## 0.0 Contract Namespace and Organizational Configuration

Factory files use the generic contract namespace
`aief.dev/v1alpha1`. This field identifies the document shape; it does not designate the organization installing the Factory and should generally not be modified.

The Factory version (`factory.version`) identifies the installed runtime version. It must match exactly the published Factory version. Profile, practice, and organization catalog versions are managed separately in the project configuration.

To adapt the Factory to an organization, do not modify the
`core/` files. Copy the organization catalog template, give it an organization-specific identifier, then configure its practices, standards, profiles and integrations in `.ai/project.yaml`:

```yaml
apiVersion: aief.dev/v1alpha1
kind: Project
metadata:
  id: my-project
  name: My Project
factory:
  version: 1.15.0
  homeEnv: AI_FACTORY_HOME
engineering:
  inheritOrganization: true
  organizationCatalogs: [my-organization@1.0.0]
```

An organization that must publish its own contract namespace should treat this change as a complete schema migration: update YAML files, schema `$id` and constants, examples, documentation, and tests in a coordinated manner.

## 0.1 Making the Factory Visible to the Agent Process

The project references the name of a variable, not a machine-specific path:

```yaml
factory:
  version: 1.15.0
  homeEnv: AI_FACTORY_HOME
```

The developer's workstation provides its value:

```bash
export AI_FACTORY_HOME="<ABSOLUTE_FACTORY_INSTALLATION>"
```

Local example:

```bash
export AI_FACTORY_HOME="/Users/example/.aief/ai-engineering-factory/1.15.0"
```

### `.zshrc` is not sufficient in all launch modes

`.zshrc` is loaded by an interactive Zsh shell. The variable may be absent if Claude Code or Codex is launched:

- from an IDE or graphical application;
- from a non-interactive shell;
- before the export is added;
- from a session that has not reloaded its configuration.

For new Zsh login shells, also declare the variable in
`~/.zprofile`, or use the environment mechanism managed by the organization:

```bash
export AI_FACTORY_HOME="<ABSOLUTE_FACTORY_INSTALLATION>"
```

Then open a new terminal, or reload explicitly:

```bash
source "$HOME/.zshrc"
printenv AI_FACTORY_HOME
test -f "$AI_FACTORY_HOME/factory.yaml"
```

Launching the agent from the same terminal guarantees inheritance:

```bash
cd "<PROJECT_ROOT>"
env | grep '^AI_FACTORY_HOME='
claude
# or: codex
```

### Local Claude Code Configuration

When an agent is launched from an IDE or a path is workstation-specific, Claude Code can receive the variable via the local unversioned file
`.claude/settings.local.json`:

```json
{
  "env": {
    "AI_FACTORY_HOME": "<ABSOLUTE_FACTORY_INSTALLATION>"
  }
}
```

If this file already contains permissions, merge the `env` key without overwriting `permissions`. Do not place this local path in
`.claude/settings.json`, which is shared and committed. Never store secrets in these files.

### Control from the Agent Session

Before the first workflow, execute only:

```bash
printenv AI_FACTORY_HOME
test -f "$AI_FACTORY_HOME/factory.yaml"
```

An empty output is a precondition failure. The adapter must stop and indicate how to configure the environment. It must never search for an arbitrary installation, nor copy, generate, or link `factory.yaml` into the project workspace.

## 1. Expected Result

```text
Developer workstation
├── ~/.aief/ai-engineering-factory/1.15.0/  # Central Factory, read-only
├── ~/.agents/skills/                      # Codex entry points to Factory
└── ~/.claude/skills/                      # Claude Code entry points to Factory

Project workspace
├── .ai/                                   # Project configuration and knowledge
├── .claude/settings.json                  # Shared Claude permissions
├── .codex/config.toml                     # Codex sandbox/approvals
├── .codex/rules/factory.rules             # Codex command rules
├── AGENTS.md                              # Common/Codex bootstrap, concise
└── CLAUDE.md                              # Claude bridge to AGENTS.md
```

The Core, workflows, and skills are never copied into the project.

Permissions are complementary native safeguards. They do not replace
`PolicyDecision`, autonomy levels, or human gates. The ready-to-review template and stack-specific adaptations are documented in
[`25-agent-permissions.md`](25-agent-permissions.md).

### When is the installation truly effective?

The presence of `.ai/project.yaml` only means the project is
**configured**. The Factory is **operational** when the following five layers are verified:

| Layer | Expected verification |
| --- | --- |
| Central Factory | The requested tag exists in `AI_FACTORY_HOME` |
| Runtime | `aief` is installed and accessible in `PATH` |
| Adapter | Skills exist in `~/.agents/skills` or `~/.claude/skills` |
| Project | `.ai/project.yaml`, `AGENTS.md` and `CLAUDE.md` are present at root |
| Session | The agent was restarted after skill installation |

A project can thus pass `aief validate` while displaying
`No commands match "/implement"` if the Claude Code adapter is not installed.

## 1.1 Target Daily Experience

After initial installation, the developer does not run `aief run` to work.
They start their agent from the workspace root:

```bash
# The presence of .ai/project.yaml enables Factory project discovery.
cd "<ABSOLUTE_PROJECT_WORKSPACE>"

# Choose one of the two agents.
codex
# or
claude
```

Then they use an explicit intent:

```text
Codex      $implement TASK-123
Claude     /implement TASK-123
```

or natural language:

```text
Implement TASK-123.
Fix the learning continuity issue described in the audit.
Refactor PaymentOrchestrator without changing its behavior.
Analyze this module without modifying the code.
```

A native command always transmits the request intact to the common Runtime.
Free text does too, but only after clearing the Activation Gate governed by
`activation.mode` in `.ai/project.yaml` (`auto` by default at installation:
the adapter asks for explicit confirmation first; `manual`: free text is
never routed through the Factory, only a native command activates it, for
that execution only). See [`23-first-steps.md`](23-first-steps.md#2-native-command-or-free-text).
Once transmitted, the Runtime normalizes the intent, creates or resumes the
Task and Execution, applies policies and returns to the agent the next phase
to execute.

```text
Developer
    ↓ native command or free text
Claude/Codex
    ↓ installed adapter
aief Runtime
    ↓ Task → Workflow → Phases → Gates → Artifacts
Claude/Codex
    ↓ reasoning, code, tests and report
Developer
```

The `aief` CLI remains necessary, but as an internal dependency of adapters and
as an administration tool (`validate`, `doctor`, inspection, resumption). It
is not the daily interface for task input.

## 2. Prerequisites

Check Git and Python:

```bash
# Git is needed to install/version the Factory and protect workspaces.
git --version

# Python 3.11 or higher is required by the aief CLI.
python3 --version
```

Install `uv` if the command does not exist:

```bash
# Official uv installer for macOS/Linux. In enterprise, use the approved channel.
curl -LsSf https://astral.sh/uv/install.sh | sh

# Reloads the current session's PATH if the installer requests it.
source "$HOME/.local/bin/env"

# Confirms the tool manager is available.
uv --version
```

## 3. Install a Central Factory Version

The organization's single reference is the published Git tag (`vX.Y.Z`), not
a local clone: pin that same tag on every workstation and in CI, rather than
each developer choosing their own version independently. Where each checkout
physically lives — a fresh clone per workstation, or one shared
filesystem/mounted location every `AI_FACTORY_HOME` points to — is a
deployment detail; what must never diverge is the tag. See
[`09-governance.md`](09-governance.md#versioning) for the release process and
the fail-closed guarantee that a project cannot silently run against a build
that drifted from its declared tag.

Define the installation parameters:

```bash
# URL of the organization's central repository.
export AIEF_REPOSITORY_URL="<FACTORY_GIT_URL>"

# Immutable version requested by projects.
export AIEF_VERSION="1.15.0"

# Organizational local root. This folder belongs to no business project.
export AIEF_INSTALL_ROOT="$HOME/.aief/ai-engineering-factory"

# Final path of the installed version.
export AIEF_HOME="$AIEF_INSTALL_ROOT/$AIEF_VERSION"
```

Clone and freeze the version:

```bash
# Creates only the parent directory; does not replace any existing installation.
mkdir -p "$AIEF_INSTALL_ROOT"

# Clones the Factory into a folder dedicated to the version.
git clone "$AIEF_REPOSITORY_URL" "$AIEF_HOME"

# Enter the Factory to verify the requested tag.
cd "$AIEF_HOME"

# Fetch tags, then position the installation on the immutable version.
git fetch --tags
git checkout "v$AIEF_VERSION"

# Verify that HEAD matches the expected tag.
git describe --tags --exact-match
```

For local Factory development, `AIEF_HOME` can temporarily point to its work clone. This variant must not serve as a shared stable installation.

## 4. Install the `aief` CLI

```bash
# Installs the CLI as an isolated tool. The developer manages no venv or pip.
uv tool install "$AIEF_HOME"

# Confirms the executable is available.
aief --help

# Displays the actually used executable, e.g., ~/.local/bin/aief.
command -v aief
```

During Factory development only:

```bash
# Editable mode reflects work clone changes immediately.
uv tool install --force --editable "$AIEF_HOME"
```

Declare the path for resolving Factory assets:

```bash
# Used by bootstraps/adapters to find the central version.
export AI_FACTORY_HOME="$AIEF_HOME"

# Makes the variable persistent for new Zsh sessions.
echo "export AI_FACTORY_HOME=\"$AIEF_HOME\"" >> "$HOME/.zshrc"
source "$HOME/.zshrc"

# Verifies that the current session resolves the Factory and its assets.
test -n "$AI_FACTORY_HOME"
test -d "$AI_FACTORY_HOME/core"
test -f "$AI_FACTORY_HOME/pyproject.toml"
```

## 5. Install Agent Adapters

Always examine the dry-run before modifying user locations:

```bash
# Previews links to Codex skills, no writing.
aief setup-adapter codex --factory "$AIEF_HOME"

# Previews links to Claude Code skills, no writing.
aief setup-adapter claude-code --factory "$AIEF_HOME"
```

If the plan is correct:

```bash
# Installs Codex entries under ~/.agents/skills/.
aief setup-adapter codex --factory "$AIEF_HOME" --execute

# Installs Claude Code entries under ~/.claude/skills/.
aief setup-adapter claude-code --factory "$AIEF_HOME" --execute
```

The adapters remain thin: `$implement` for Codex and `/implement` for Claude trigger the same Core workflow.

Physically verify the installation:

```bash
# Must find the Codex skill manifest.
test -f "$HOME/.agents/skills/implement/SKILL.md"

# Must find the Claude Code skill manifest.
test -f "$HOME/.claude/skills/implement/SKILL.md"

# Displays the links to the central Factory when installed as symlinks.
ls -la "$HOME/.agents/skills/implement"
ls -la "$HOME/.claude/skills/implement"
```

If either test fails, the corresponding agent will not be able to discover its
native `implement` command.

## 6. Initialize the Project

Define the target workspace:

```bash
# Must point to the common root containing the project's repositories.
export PROJECT_ROOT="<ABSOLUTE_PROJECT_WORKSPACE>"

# Implicitly refuses a bad target during following commands.
test -d "$PROJECT_ROOT"
```

For a new project without `.ai/` configuration:

```bash
# Verifies that the target does not exist to avoid overwriting.
test ! -e "$PROJECT_ROOT/.ai"

# Copies only the project context. The Core remains centralized.
cp -R "$AIEF_HOME/templates/project/.ai" "$PROJECT_ROOT/.ai"
```

Any existing `AGENTS.md` and `CLAUDE.md` must be manually analyzed and merged. Never blindly overwrite them with a copy.

If these files do not yet exist, install the template bootstraps:

```bash
# Guards prevent any overwriting of existing instructions.
test ! -e "$PROJECT_ROOT/AGENTS.md"
test ! -e "$PROJECT_ROOT/CLAUDE.md"

cp "$AIEF_HOME/templates/project/AGENTS.md" "$PROJECT_ROOT/AGENTS.md"
cp "$AIEF_HOME/templates/project/CLAUDE.md" "$PROJECT_ROOT/CLAUDE.md"

# Confirms that launching from PROJECT_ROOT will expose both bootstraps.
test -f "$PROJECT_ROOT/AGENTS.md"
test -f "$PROJECT_ROOT/CLAUDE.md"
```

For an existing file, merge only Factory instructions after human review. `CLAUDE.md` must import `AGENTS.md` with `@AGENTS.md` to
avoid two divergent copies.

## 7. Configure `.ai/project.yaml`

Commented poly-repo example:

```yaml
apiVersion: aief.dev/v1alpha1 # Contract version, not Factory version.
kind: Project

metadata:
  id: my-project                         # Stable identifier, no spaces.
  name: My Project                       # Human-readable name.

factory:
  version: 1.15.0                        # Central version required by project.
  homeEnv: AI_FACTORY_HOME           # Variable that locates its installation.

workspace:
  strategy: polyrepo                     # Use monorepo if single Git root.
  root: .                                # Path relative to project file.

workspaceSafety:
  mode: worktree                         # Isolates agent changes.
  baseBranch: main                       # Default target branch.
  taskBranchPrefix: aief                 # Prefix for Factory work branches.

activation:
  mode: auto                             # auto (default): free text asks before routing through
                                          # the Factory. manual: only a native command activates it,
                                          # and only for that execution; free text never routes.

repositories:
  - id: backend
    path: ./backend                      # Must stay within workspace.
    role: backend-application
    profiles: [java, spring, maven]      # Technical knowledge, never in Core.
    responsibilities: [business-domain, rest-api]
    dependencies: []
    criticalDomains: [authentication, personal-data]
    git:
      baseBranch: main

  - id: frontend
    path: ./frontend
    role: web-application
    profiles: [node, react]
    responsibilities: [user-interface]
    dependencies:
      - repository: backend
        type: REST
    criticalDomains: [authentication]
    git:
      baseBranch: main

context:
  project: .ai/context/project.md
  architecture: .ai/context/architecture.md
  domain: .ai/context/domain.md
  conventions: .ai/context/conventions.md
  decisions: .ai/decisions
  memory: .ai/memory/shared.md

runtime:
  root: .ai/runtime                      # Deterministic Task/Execution/Handoff state.
  taskRetentionDays: 30
  executionRetentionDays: 14

integrations: {}                         # Starting without MCP or external provider.

taskTracking:
  mode: local                            # .ai/runtime suffices; no task-provider required.

autonomy:
  default: L2                            # Read, local modifications and tests.
  maximum: L2                            # Forbids auto commit/push/MR to pilot.

policyRefs: []                           # Additional project policies if needed.

engineering:
  inheritOrganization: true              # Inherit organizational standards/practices.
  organizationCatalogs:                  # Catalogs chosen by this project.
    - factory-default@1.0.0
  practices: {}                          # Explicit activations/overrides by project.
```

Configuration principles:

- declare each Git repository actually managed;
- do not declare a documentation-only folder as an executable repository;
- use existing profiles in `profiles/`;
- explicitly select applicable organizational catalogs;
- start at `L2`, then raise autonomy after experience;
- explicitly choose `taskTracking.mode: local` without a task manager,
  or `external` when a `task-provider` should become the canonical reference;
- place no secrets, endpoints or tokens in this file.

Selection examples:

```yaml
# Baseline provided by the Factory.
organizationCatalogs: [factory-default@1.0.0]

# Example organization extending the Factory baseline.
organizationCatalogs: [example-organization@1.0.0]

# Autonomous project: no implicit organizational conventions.
organizationCatalogs: []
```

Another organization adds its own `OrganizationCatalog` without modifying
the Core or Profiles. See
[`24-organization-knowledge-catalog.md`](24-organization-knowledge-catalog.md).

## 8. Configure Topology

Example `.ai/repository-map.yaml`:

```yaml
apiVersion: aief.dev/v1alpha1
kind: RepositoryMap

metadata:
  id: my-project-repositories

repositories:
  backend:
    responsibilities: [business-services, persistence]
    exposes: [rest-api]
    consumes: [postgresql]

  frontend:
    responsibilities: [web-ui]
    exposes: [public-web-application]
    consumes: [rest-api]

relationships:
  - from: frontend
    to: backend
    type: REST

criticalDomains:
  - authentication
  - personal-data
```

This map describes cross-cutting impacts. It does not replace analysis of actual code.

## 9. Write Markdown Context

Complete at minimum:

```text
.ai/context/project.md       objective, users, scope and strategic references
.ai/context/architecture.md  components, flows, dependencies and invariants
.ai/context/domain.md        business vocabulary, states and rules
.ai/context/conventions.md   conventions truly specific to the project
```

Documentation rules:

- distinguish target product, observed state and assumptions;
- reference useful audits/ADRs by their path;
- ask the agent to verify reports against code and tests;
- do not recopy organizational conventions already resolved by profiles;
- do not turn `.ai/memory/` into ungovernored general documentation.

## 10. Bootstrap `AGENTS.md` and `CLAUDE.md`

`AGENTS.md` must remain concise:

```markdown
# AI Engineering Factory Project

Before engineering work:

1. Read `.ai/project.yaml` and resolve the pinned Factory version.
2. Use Factory workflows and policies for engineering tasks.
3. Load `.ai/` context progressively.
4. Never overwrite unrelated local changes.
5. Respect human gates and persist structured runtime artifacts.
```

`CLAUDE.md` can import this shared bootstrap:

```markdown
@AGENTS.md

Use the centrally installed AI Engineering Factory Claude Code adapter.
Do not duplicate Core workflows or policies in this file.
```

If the workspace already has these files, preserve existing instructions and add only the necessary Factory bridge.

## 11. Validate Installation Without MCP

```bash
# Validates YAML, schemas, references, profiles and project coherence.
aief validate "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Verifies general workspace preconditions.
aief doctor "$PROJECT_ROOT"

# Generates an empty lock without secrets when integrations: {}.
aief integrations lock "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Must report providers: [] and all checks in ok status.
aief integrations doctor "$PROJECT_ROOT" --factory "$AIEF_HOME"
```

The empty lock configures no MCP. It proves that the absence of integration is intentional.

### Choose Traceability Without a Task Manager

An installation without MCP must also explicitly declare that local
traceability satisfies the policies:

```yaml
integrations: {}
taskTracking:
  mode: local
```

The calculated level (`optional`, `recommended`, `required`) remains unchanged. For
a critical task, `required` always requires the Task, artifacts, decisions, validations and Runtime journal; it simply does not require
an external ticket.

Do not use `mode: external` without `integrations.task-provider`, unless the
`PROVIDER_NOT_CONFIGURED` blockage is intentional during onboarding.

| Configuration | Result of `required` tracking |
| --- | --- |
| `mode: local`, no provider | satisfied by `.ai/runtime` |
| `mode: external`, provider configured and linked | satisfied by external reference |
| `mode: external`, provider absent | Execution blocked |
| property absent | conservative `external` behavior |

### Execution Already Blocked by External Tracking

After a reviewed modification from `external` to `local`, never edit
`tracking.yaml` or `execution.yaml`. Simply resume resolution:

```bash
aief execution next <execution-id> \
  --project "/absolute/project" \
  --factory "/absolute/factory" \
  --json
```

The Runtime recalculates `tracking.yaml`, marks the local decision as
`satisfied: true`, removes `external-tracking-required`, then applies the
next check. If the project uses `workspaceSafety.mode: worktree`, the
expected new blockage may be `workspace-preparation-required`:

```bash
aief workspace prepare <execution-id> \
  --project "/absolute/project" \
  --factory "/absolute/factory" \
  --execute \
  --json
```

This second blockage is independent of the task manager: it protects the
developer's local Git changes.

### Go/No-Go Control Before Launching an Agent

Execute these checks from a new terminal session:

```bash
# 1. Runtime available.
command -v aief

# 2. Central Factory resolved.
test -n "$AI_FACTORY_HOME"
test -d "$AI_FACTORY_HOME/core"

# 3. Project and bootstraps present.
test -f "$PROJECT_ROOT/.ai/project.yaml"
test -f "$PROJECT_ROOT/AGENTS.md"
test -f "$PROJECT_ROOT/CLAUDE.md"
test -f "$PROJECT_ROOT/.claude/settings.json"
test -f "$PROJECT_ROOT/.codex/config.toml"
test -f "$PROJECT_ROOT/.codex/rules/factory.rules"

# 4. Claude Code adapter, if Claude will be used.
test -f "$HOME/.claude/skills/implement/SKILL.md"

# 5. Codex adapter, if Codex will be used.
test -f "$HOME/.agents/skills/implement/SKILL.md"

# 6. Valid deterministic configuration.
aief validate "$PROJECT_ROOT" --factory "$AI_FACTORY_HOME"
aief doctor "$PROJECT_ROOT"
```

All applicable checks must pass. An error must be corrected
before opening the first agent session.

## 12. First Controlled Test from Claude Code or Codex

Start with a local, non-mutating task:

```bash
cd "$PROJECT_ROOT"

# Starts the chosen agent from the root containing .ai/project.yaml.
codex
# or: claude
```

Close any Claude Code or Codex session open before skill installation,
then start a new session. Native commands are
discovered at agent startup.

In the agent session, after adapter installation:

```text
Codex      $analyze Analyze the current architecture without modifying the code.
Claude     /analyze Analyze the current architecture without modifying the code.
```

Free text must follow the same path, once the Activation Gate has cleared it
(the agent asks for confirmation first under the default `activation.mode:
auto`; see [`23-first-steps.md`](23-first-steps.md#2-native-command-or-free-text)):

```text
Analyze the current architecture, verify documents against code and do
not modify any files.
```

`aief run` is only useful for directly diagnosing the Runtime boundary, writing an automated integration test or developing an adapter:

```bash
# Low-level command; it does not constitute the normal developer experience.
aief run \
  "Analyze the current architecture without modifying the code." \
  --agent codex \
  --agent-session "codex:diagnostic-session" \
  --project "$PROJECT_ROOT" \
  --factory "$AIEF_HOME"
```

For mutating diagnostics, acquire the returned Execution lease with
`--owner codex:diagnostic-session` and pass that owner to every mutating
Execution command. The session flag alone records an observed label; it does
not authenticate or trust the actor.

Then test a limited local modification, on a clean workspace or a worktree prepared by the Factory:

```text
Codex      $test Add only the missing tests for this behavior.
Claude     /test Add only the missing tests for this behavior.
```

### Diagnosing `No commands match "/implement"`

This message indicates that Claude Code did not discover the skill. It does not necessarily mean `.ai/project.yaml` is invalid.

Check in this order:

```bash
# 1. Is the Claude skill really installed?
test -f "$HOME/.claude/skills/implement/SKILL.md"

# 2. Does any symlink point to an existing target?
ls -la "$HOME/.claude/skills/implement"

# 3. Is the central Factory resolved in this session?
printenv AI_FACTORY_HOME
test -f "$AI_FACTORY_HOME/adapters/claude-code/runtime-protocol.md"

# 4. Do the project instructions exist at the launch root?
test -f "$PROJECT_ROOT/CLAUDE.md"
test -f "$PROJECT_ROOT/AGENTS.md"
```

If the skill is missing:

```bash
aief setup-adapter claude-code \
  --factory "$AI_FACTORY_HOME" \
  --execute
```

Then completely exit Claude Code and restart it from the root:

```bash
cd "$PROJECT_ROOT"
claude
```

For Codex, replace `~/.claude/skills/implement` with
`~/.agents/skills/implement`, install the `codex` adapter, then restart
`codex`. In Codex, the correct invocation is `$implement`; `/implement`
normally returns `Unrecognized command` because `/` designates the client's built-in commands. The complete walkthrough and Codex troubleshooting are documented
in [`27-codex-usage.md`](27-codex-usage.md).

## 13. Activate an MCP Provider Later

The provider must first exist in the Factory's central catalog and be
authorized by organizational governance. The project does not configure
MCP: it only activates a logical association between capability and
provider.

```text
Factory integrations/   technical definition and operations
Organization            authorized providers and defaults
Project                 capability activation
Adapter                 Claude/Codex generation
Developer runtime       local authentication
```

The project thus chooses a capability and provider, never a transport, URL, command, header or token:

```yaml
taskTracking:
  mode: external       # Only if Jira/GitLab/GitHub should carry required Tasks.

integrations:
  task-provider:
    provider: jira
  source-control:
    provider: gitlab
  knowledge-base:
    provider: confluence
```

Configuration forbidden in `.ai/project.yaml`:

```yaml
integrations:
  gitlab:
    url: https://gitlab.example/mcp  # forbidden
    transport: http                  # forbidden
    token: glpat-secret              # strictly forbidden
```

A project can keep `taskTracking.mode: local` while activating
`source-control` or `knowledge-base`. The presence of an MCP does not impose external mode; only the choice of canonical Task system determines it.

Then:

```bash
# Freezes selected integration definitions, without secrets.
aief integrations lock "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Verifies catalogs, capabilities, MCP and required variables.
aief integrations doctor "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Previews native Codex configuration; no writing without --execute.
aief integrations sync codex "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Applies after explicit review of plan. For shared organizational provider,
# prefer user scope to avoid per-project configuration.
aief integrations sync codex "$PROJECT_ROOT" --factory "$AIEF_HOME" --scope user --execute

# Same procedure for Claude Code.
aief integrations sync claude-code "$PROJECT_ROOT" --factory "$AIEF_HOME"
aief integrations sync claude-code "$PROJECT_ROOT" --factory "$AIEF_HOME" --scope user --execute
```

`sync` materializes native configuration; it does not move the source of truth into the client. For an MCP specific to the project and explicitly
authorized, project scope can be used after organizational policy validation.

Managed endpoints and credentials remain in an enterprise configuration,
keychain, secret manager, the agent's authentication store or
environment. They are never committed in `.ai/`, `.mcp.json` or
`.codex/config.toml`.

### Project-Specific MCP

A project cannot arbitrarily declare a custom server. Organizational
governance must authorize custom MCPs, their transports,
their scopes and, if necessary, mandate human approval. Until this
contract is supported by the Runtime, manually adding a server
in `.mcp.json` or `.codex/config.toml` does not constitute a valid
Factory integration.

## 14. Factory Upgrade

A version upgrade is explicit:

1. install the new tag in a new central folder;
2. update `factory.version` in `.ai/project.yaml` on a project branch;
3. repoint `AI_FACTORY_HOME` to this installation;
4. reinstall/repoint adapters;
5. regenerate the integration lock;
6. execute `validate` and `doctor`;
7. test a non-mutating workflow before an implementation.

Do not silently replace the contents of an existing version folder.

## 15. Acceptance Checklist

- [ ] The Factory is installed from a known tag.
- [ ] `AI_FACTORY_HOME` points to this version.
- [ ] `aief --help` works without manual Python environment.
- [ ] Adapters were previewed then explicitly installed.
- [ ] Native Claude/Codex permissions were reviewed and committed.
- [ ] Profile-specific validations have precise prefixes, no global shell authorization.
- [ ] `activation.mode` reflects the intended default (`auto` unless the team explicitly wants `manual`).
- [ ] Gates, external writes and Git publications remain interactive.
- [ ] `.ai/project.yaml` describes all managed repositories.
- [ ] Profiles match technologies actually detected.
- [ ] `.ai/repository-map.yaml` describes inter-repository dependencies.
- [ ] Context documents distinguish actual state, target and assumptions.
- [ ] Initial autonomy and critical domains are explicit.
- [ ] No secrets are stored in the repository.
- [ ] `aief validate` and `aief doctor` succeed.
- [ ] `aief integrations doctor` succeeds, including without provider.
- [ ] First test is a non-mutating analysis.
- [ ] Runtime receipt contains `execution`, `workflow`, `nextPhase` and `taskLog`.
- [ ] `aief task log <task-id>` shows `task.normalized` and `workflow.started`.
- [ ] Preexisting local modifications are neither overwritten nor incorporated.
