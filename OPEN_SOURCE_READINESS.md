# AI Engineering Factory — Open Source Readiness

Audit of the actual repository state at `1.15.0` (branch `optimise-aief`, commit `aeb69b4`), ahead of a planned public GitHub release. Every finding below is sourced from a command actually run or a file actually read in this session — not from documentation claims alone.

## Executive Summary

The Runtime itself is in reasonable shape for an alpha: 195 tests, 194 passing, none of the passing ones requiring a paid agent subscription or live external credentials, and a real (if minimal) CI workflow.

Three of the four original P0 blockers found by this audit are now resolved: a real MIT `LICENSE` is in place, the leaked internal GitLab path/product codename (`Gad-Digital-IT/products/emi-ai`) has been replaced with the existing `emmany`/`EGW-142` example, and the organization-specific `gad-digital` example catalog (and its private `gad-guidelines` submodule dependency) has been removed and replaced with a fully self-contained, generic `sample-organization` catalog — which, as a side effect, fixed 2 of the 3 previously-known test failures (194/195 now pass). `organization/README.md` and the README now state explicitly that the Factory Core is agnostic of any organization.

What remains open: **the git history still exposes two personal email addresses**, and **the schema/data-model namespace decision** (`factory.gaddigital.io`, still present in every schema `$id` as Core infrastructure, not example content) **has not been resolved** — it was deliberately left untouched, since renaming an `apiVersion`/`$id` used across every document kind is a real schema migration requiring its own specification, not a side effect of removing example data.

## Current Level: **LEVEL 1 — PUBLIC PREVIEW READY**, pending the git-history decision

The example/IP leak and the missing license — the two items that made this LEVEL 0 — are resolved. One decision remains before a first public push: whether to publish this repository's actual history (personal emails included) or a fresh, squashed initial commit. See P0 below.

## P0 — Remaining blocker before the repository becomes public

1. **Personal identity in git history** (unresolved). Every commit in this history is authored as `Ricken Bazolo <ricken.bazolo@gmail.com>` or `<ricken.bazolo@carbon-it.fr>`. This was not rewritten in this session — history rewriting is a destructive, one-way action affecting shared state and was not asked for. **Recommendation stands: publish as a fresh, squashed initial commit** rather than this repository's existing history, unless the organization explicitly decides authorship attribution should remain visible.

## Resolved this session

- ~~`BLOCKER: LICENSE_MISSING`~~ — `LICENSE` now carries the MIT license (copyright: "AI Engineering Factory contributors", 2026).
- ~~Real internal reference leaked in tracked content~~ — `tests/test_intake.py` and `docs/28-gitlab-issues-and-board.md` now use `example-organization/emmany/egw-api` / `EGW-142`, consistent with every other example in the repository.
- ~~Organization-branded example catalog~~ — `organization/catalogs/gad-digital.yaml`, `organization/practices/gad-digital/*`, and the `organization/catalogs/gad-guidelines` submodule are removed. Replaced by `organization/catalogs/sample-organization.yaml` (extends `factory-default@1.0.0`), fully self-contained, no external dependency. `templates/organization/catalog.yaml`'s own placeholder id (`example-organization`, meant to be copied and renamed by an adopting company) was kept distinct from the new shipped example to avoid confusion between "a template to copy" and "a demonstration that ships as-is."

## Open decision, not a hygiene item

- **Schema/data-model namespace.** `apiVersion: factory.gaddigital.io/v1alpha1` and every schema `$id` (`https://factory.gaddigital.io/schemas/...`) still appear in every schema, policy and document kind — this is Core infrastructure, not example content, and remains unchanged. Keep it (the organization's namespace, publicly disclosed as the project's origin), or migrate to a project-neutral namespace as a dedicated, specified schema migration — not a side effect of this or any other cleanup.

## P1 — Before public launch (blocks a credible Level 2 "contribution ready", not Level 1 preview)

2. Add `CONTRIBUTING.md`, `SECURITY.md`.
3. Add `.github/ISSUE_TEMPLATE/` (bug report, feature request, documentation) and `.github/PULL_REQUEST_TEMPLATE.md`.
4. Reconcile `QA_REPORT.md` (still states `Version: 1.11.0`, "95 tests") with the current `1.15.0`/195-tests reality, or retire it in favor of `docs/34-release-readiness.md`.
5. Fix two stale doc mentions that the event log "starts with `task.normalized`" (`docs/22-project-installation-guide.md` checklist item, `docs/23-first-steps.md` twice) — it now starts with `request.created` since the Observability increment.
6. Tag `v1.15.0`. The only existing tag is `v1.14.0`, four commits behind current `HEAD` and two minor versions behind `VERSION`/`pyproject.toml`/`factory.yaml` (which already agree at `1.15.0`, after a prior drift documented in `CHANGELOG.md`).
7. Add a lightweight `GOVERNANCE.md` (see Governance below).

## P2 — After launch

- Add `CODE_OF_CONDUCT.md` (adopt the Contributor Covenant rather than drafting one).
- Add a lint/type-check step to CI (`ruff`/`mypy` are configured nowhere today).
- Add a single dependency-update bot (Dependabot **or** Renovate, not both — neither is configured today).
- Add a `uv.lock` or equivalent for reproducible CI, once the dependency surface grows beyond PyYAML/jsonschema.
- Consider `docs/adr/` only if architecture-impacting contributions actually start arriving — do not pre-build governance for a contributor base that does not exist yet.
- Untrack `.idea/` (already gitignored, but 5 files were committed before the ignore rule existed; contents checked, no secrets — just a maintainer's local AWS Toolkit region preference).

---

## Repository Hygiene

| Check | Status |
| --- | --- |
| `.gitattributes`, `.editorconfig`, `.pre-commit-config.yaml`, `Dockerfile`, `Makefile`, `justfile`, `tox.ini` | MISSING (none present; not blocking, Python project with a trivial dependency surface) |
| `.gitignore` | READY, but incomplete in effect — `.idea/` is listed yet 5 files under it are already tracked |
| Secret scan of HEAD | READY — no AWS/GitHub/GitLab/OpenAI/Anthropic/Jira token shapes, no private-key blocks, no private IPs found in source, tests, docs, fixtures, or CI config. The two `ghp_`/`AKIA`-shaped strings that do exist (`tests/test_observability.py:139-140`) are intentional fixture data proving the event-log redaction feature works, not leaked secrets. |
| Secret/PII scan of git history | **NOT resolved** — every commit is attributed to a real name and two real email addresses (P0). No deeper history scan (e.g., for values later removed from HEAD) was run; per this audit's own instructions, absence of secrets in HEAD is not evidence the full history is clean. **Recommendation stands: publish as a fresh squashed history rather than certify the existing one.** |
| Internal example/reference scan | **Resolved** — the two flagged files now use the `emmany`/`EGW-142` example; `examples/emmany` and all other fixtures use `example.invalid`/`example.com`/`example.test`/`gitlab.example`-style placeholders correctly. |

## Licensing

- **Actual license: MIT**, applied this session (`LICENSE`, copyright "AI Engineering Factory contributors", 2026).
- **Third-party licensing considerations** (factual, not legal advice):
  - Runtime dependencies are declared, not vendored: `PyYAML>=6.0`, `jsonschema>=4.20` (both MIT-licensed per their own PyPI metadata), and `pytest>=8.0` as a dev dependency (MIT). None of their code is copied into this repository.
  - No vendored third-party code, templates, or assets were found anywhere in `core/`, `profiles/`, `organization/`, `integrations/`, `adapters/`, `templates/`, or `docs/`.
  - JSON Schema (`https://json-schema.org/draft/2020-12/schema`) is used as a specification reference, not copied code — no licensing implication.
  - No screenshots, binary assets, fonts, or icon sets were found in the repository.
  - The organization-specific `gad-digital` example catalog has been removed, resolving the disclosure question it raised; the remaining `factory-default` and `sample-organization` catalogs are generic, Factory-authored content.
  - **Conclusion**: no third-party licensing entanglement was identified.

## Security

No `SECURITY.md` exists. AIEF's actual attack surface is non-trivial and already partly mitigated in code (verified this session and in `docs/34-release-readiness.md`):

| Topic | Real mechanism | Evidence |
| --- | --- | --- |
| Command execution | Profile validation commands run as `shell=False` argv arrays only | `aief/capabilities.py` |
| Git / filesystem | Structured argv Git inspection; force-push, hard reset, clean, and branch deletion are rejected outright | `aief/workspace.py`, `tests/test_workspace.py` |
| Agent permissions | Native Claude/Codex permission files are reviewed/committed artifacts, not a replacement for PolicyDecision or gates | `docs/25-agent-permissions.md` |
| MCP / credentials | Secrets are never stored in `.ai/project.yaml` or generated adapter config; MCP grants connectivity, not authorization | `docs/13-agent-adapters-and-mcp.md`, `aief/mcp.py` |
| Human gates | Protected transitions block until an explicit approval is recorded | `aief/service.py`, `tests/test_observability.py` |
| Workspace isolation | Worktree-based isolation, dirty-workspace and poly-repo-drift detection | `tests/test_workspace.py`, harness scenario `dirty-workspace` |

**Gap, per this audit's own instruction not to invent one**: there is no disclosed vulnerability-reporting channel, no stated supported-version policy, and no explicit disclosure timeline. **A decision is required**: designate a real contact (a security-specific email alias or GitHub private vulnerability reporting), state that only the latest `1.x` line is supported pre-`1.0` stabilization, and state plainly that GitHub Issues is not the channel for a suspected vulnerability. No placeholder address was published in the README or elsewhere.

## Documentation

- 35 numbered documents (`docs/00` through `docs/34`), all internally cross-linked; a full link-integrity pass over every `docs/*.md`, `README.md`, and this file found **zero broken relative links**.
- Information architecture already follows README → Installation (`docs/22`) → First steps (`docs/23`) → Concepts/Architecture (`docs/01-04`) → Advanced (`docs/05-21`, `docs/24-34`) — no restructuring needed.
- Two stale references found (P1-5); one stale root-level report found (`QA_REPORT.md`, P1-4).
- The two documents that previously leaked a real internal reference now follow the same "generic example" convention as the rest of the repository.

## Contribution Model

`CONTRIBUTING.md` does not exist. Once written, it must cover, in this order: clone (a plain `git clone` — no submodule remains after this session's cleanup), Python `>=3.11`, install via `uv tool install --editable .` or `pip install -e '.[dev]'`, `pytest`, and — since there is no linter configured today — either add one first or say explicitly that none is enforced yet. It must also state the Core-agnosticism invariants already declared in the README's "Core principles" and enforced by `tests/test_core_agnostic.py`:

```text
Core MUST NOT depend on: Claude Code, Codex, GitLab, GitHub, Jira, Confluence, Java, Spring, Node, Flutter, React, or any other agent/provider/stack.
Adapters MUST NOT duplicate: workflows, policies, or project context.
```

It should walk through adding one instance of each extension point (Core Skill, Workflow, Policy, Profile, Organization Catalog, Integration, Agent Adapter) by pointing at the closest existing example of each (`core/skills/understand-task/`, `core/workflows/analyze-task/`, `core/policies/risk-policy.yaml`, `profiles/generic/`, `organization/catalogs/factory-default.yaml`, `integrations/jira/`, `adapters/codex/`) rather than inventing a tutorial from scratch.

**Architecture decision guidance (mission §9)**: no `docs/adr/` is needed today. The project is young enough that the existing numbered `docs/` series already carries design rationale per increment (e.g. `docs/20`, `docs/21`, `docs/32`–`34`). Recommend a single line in `CONTRIBUTING.md` — *"A change to a Core contract (schema, workflow phase order, policy resolution) needs a GitHub Discussion or issue before a PR; a new `docs/NN-*.md` documents the outcome, in the same style as the existing series."* — instead of introducing a separate ADR process this project has no evidence of needing yet.

## Testing

195 tests collected, 194 passing (`pytest tests/ -q`, run this session). None of the passing tests require a Claude or Codex subscription, live GitLab/Jira access, or a real MCP server — external providers are exercised through fixtures using `*.invalid`/`*.example.test` endpoints and injected fake credentials (`tests/test_mcp.py`, `tests/test_tracking.py`). The suite already runs clean in a fresh environment with only `pip install -e '.[dev]'` and no network access, which is exactly the open-source contributor bar this mission asks for.

The 1 remaining failing test is diagnosed in `docs/34-release-readiness.md`: a stale MCP fixture unrelated to any external service. The 2 tests that previously depended on the private `gad-guidelines` submodule now pass, since that example was removed in favor of the fully self-contained `sample-organization` catalog.

## CI

`.github/workflows/quality.yml` is real and requires no organizational secret: checkout, Python 3.12, `pip install -e '.[dev]'`, `pytest`, `python tools/validate_package.py`. It is not disproportionate for the project's size.

Gaps: only one Python version is tested despite `requires-python = ">=3.11"` in `pyproject.toml` (3.11 itself is untested); no lint or type-check step exists because none is configured anywhere in the repository; no packaging/build-artifact step (e.g. `python -m build`) verifies the wheel actually installs cleanly, only that `pip install -e .` works from source.

## Packaging

`pyproject.toml` is a clean, standard `setuptools` project: `ai-engineering-factory` / `aief` console script / `PyYAML`, `jsonschema` runtime deps / `pytest` dev dep. The conceptual path (`uv tool install <path>` → `aief --help` → `aief validate` → `aief doctor`) matches what `docs/22` documents and what the README's Quick Start now synthesizes — both were checked against each other this session and agree. This was verified conceptually and via direct module invocation (`python -m aief.cli --help`) in this session; a true clean-environment `uv tool install` from a public URL was not exercised here (there is no public URL yet).

## Release

`VERSION`, `pyproject.toml`, and `factory.yaml` all agree at `1.15.0` today (a prior drift between them was self-corrected in the `1.15.0` CHANGELOG entry — the mechanism to notice such drift is manual review, not CI, per the CI gap above). `CHANGELOG.md` is detailed and current. Git tagging exists but is stale (`v1.14.0`, four commits behind). Recommended, minimal strategy, compatible with the current model:

```text
Semantic Versioning (already followed in CHANGELOG.md and VERSION)
A git tag per release (vX.Y.Z), created at the same commit as the CHANGELOG entry
A GitHub Release generated from that tag, body = the CHANGELOG section
No automatic publication to any package index until a distribution channel is decided (P2)
```

Breaking changes to schemas, `project.yaml`, workflow contracts, Skills, organization catalogs, or adapters must be called out explicitly in the CHANGELOG entry that introduces them — the current CHANGELOG already does this informally (e.g. the `1.15.0` entry on `Task`/`dependsOn`); formalize it as a required CHANGELOG heading (`### Breaking`) rather than free text.

## Compatibility policy

No explicit compatibility policy exists yet. Given the `v1alpha1` contract stability note already in the README, recommend stating, before `1.0`, the minimum honest promise:

```text
project.yaml / repository-map.yaml: may require manual migration between minor versions until 1.0
Runtime state (.ai/runtime/): not guaranteed to remain readable across a Factory version change
Schemas: additive changes preferred; a required-field addition or removal is a breaking change and must be in the CHANGELOG
Adapters: Claude Code and Codex must expose the same intents for the same Factory version
Organization catalogs: a pinned "id@version" reference must resolve to unchanged content, or fail closed
```

## Governance

No `GOVERNANCE.md`. For a young project, recommend exactly two sentences, not a foundation structure:

```text
Maintainers review any change that affects a Core contract (schema, workflow phase order, policy resolution, or an adapter's mapping to Core).
A significant change should be discussed in an issue or GitHub Discussion before a pull request implements it.
```

## Public/Internal Boundary

This is the section this audit exists to answer.

- The **Factory-provided example/default catalog** (`factory-default@1.0.0`, `organization/catalogs/factory-default.yaml`) is genuinely generic — secret management, testing baseline, code review, API design, hexagonal architecture — and appropriate to ship publicly as-is.
- **Resolved this session**: the organization-specific `gad-digital` catalog and its practices are removed. `organization/catalogs/sample-organization.yaml` now demonstrates a second, composable catalog with no organization-specific content and no external dependency. `organization/README.md` states explicitly that the Factory Core is agnostic of any single organization, and that these two shipped catalogs are illustration only.
- `templates/organization/` exists (a bare `catalog.yaml` scaffold, id `example-organization`, distinct from the newly-shipped `sample-organization`) so a company can start its **own, separately-maintained** catalog. `organization/README.md` now describes this model in prose; a dedicated walkthrough is still recommended (P1) but the concept is no longer undocumented.
- **Still open**: the `factory.gaddigital.io` schema namespace itself is Core infrastructure, not example content, and was deliberately left unchanged — see "Open decision, not a hygiene item" above.

## Repository name / naming consistency

`ai-engineering-factory` (repo, `pyproject.toml` `name`), `aief` (Python package, CLI, console script), "AI Engineering Factory" / "AIEF" (prose) are used consistently across README, docs, schemas, and code — no old or inconsistent project name was found. This is separate from, and unaffected by, the `gaddigital.io` schema-namespace decision above.

## Agent/trademark naming

Claude, Claude Code, Anthropic, Codex, OpenAI, GitHub, GitLab, Jira, and Confluence are referenced only descriptively (supported adapters and integrations). No wording suggesting partnership, endorsement, or affiliation was found in `README.md` or `docs/*.md` (checked explicitly this session).

## GitHub repository configuration (recommendations, not yet applied)

```text
Description: "Agent-independent engineering layer for governed, traceable AI-assisted software development."
Website: (none until docs are hosted separately; link to README otherwise)
Topics (12): ai-engineering, software-engineering, coding-agents, claude-code, codex, developer-tools,
             agentic-development, ai-governance, human-in-the-loop, python, developer-workflows, mcp
Discussions: enable (natural home for the architecture-decision-before-PR convention above)
Issues: enable
Wiki: disable (docs/ is already the source of truth; a wiki would fork it)
Projects: optional, not required at launch
Releases: enable once the first tag (P1-6) exists
Sponsorship: not recommended before Level 2
Default branch: main (rename from optimise-aief before or at publication)
Merge strategy: squash merge only, to keep history readable given the small, frequent commit style already in use
```

## Branch protection (minimal, for the default branch)

```text
Require a pull request before merging
Require the quality.yml check to pass
Require at least one review
Disallow force pushes
Disallow branch deletion
```

Nothing beyond this — no required number of reviewers greater than one, no code-owner enforcement, no signed-commit requirement — those are enterprise defaults disproportionate for a project with a single maintainer today.

## Dependency update automation

Choose **one**. Given the dependency surface is two runtime packages and one dev package, either is low-effort; Dependabot requires zero extra configuration file complexity (a single `.github/dependabot.yml`) and is native to GitHub — recommended over Renovate for this project's current size. Do not configure both.

## Release automation

Recommend automating only: run tests → build the package → attach it to a GitHub Release, triggered by a pushed tag. **Do not** wire automatic publication to PyPI or any other public index until the organization has decided on a distribution channel and ownership of the PyPI project name — that is a separate, later decision (P2), not a hygiene item.

## Public roadmap

Use the README's existing "Roadmap" section (Available / In progress / Exploration) as the single source of truth; do not also create a `ROADMAP.md` or a GitHub Project board until real external demand for one appears. This is the lightest mechanism that still satisfies the mission's requirement to separate available/planned/exploratory clearly.

## Competitor / related-project references

None exist in the current README or docs, and none should be added as a comparison table. If a specific project genuinely influenced a design decision, it belongs in a factual "Influences" note (not present today) — no such documented influence was found in this repository to report.

---

## Final Go / No-Go

> **Can AI Engineering Factory safely be made public on GitHub today?**

**YES, AS PUBLIC PREVIEW (Level 1)** — with one remaining decision, not a fix.

The real internal GitLab path and product codename are gone (replaced with the existing `emmany`/`EGW-142` example), a real MIT `LICENSE` is in place, and the organization-specific example catalog has been replaced with a fully self-contained generic one — which also fixed 2 of the 3 previously-known test failures. None of this required re-architecting the Runtime, and the engineering itself was already ready for a labeled preview.

**One item remains before the first public push**, and it is a decision for the organization rather than a fix this audit can apply on its own behalf: publish this repository's **existing git history** (which contains two real personal email addresses in every commit's authorship) or publish a **fresh, squashed initial commit** instead. This session did not rewrite history — that is a destructive, one-way action affecting shared state, and it was not explicitly requested.

**Minimum absolute remaining** (public repository readiness, deliberately narrower than product/production readiness — it does not require fixing the 1 known test failure, the unenforced policy files, the `gaddigital.io` namespace decision, or Level 3 evaluation, all legitimate to ship as documented "Alpha" limitations):

1. Decide how to handle git history authorship (squash-and-republish, or accept it as-is) before the first push.

Level 2 (contribution-ready) additionally needs the P1 list above; Level 3 (release-ready) is a materially larger step tied to the compatibility policy and the still-unenforced organization policies documented in `docs/34-release-readiness.md`, not to anything in this document.
