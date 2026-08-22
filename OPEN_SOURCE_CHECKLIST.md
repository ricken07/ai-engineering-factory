# Open Source Checklist

Actionable companion to [`OPEN_SOURCE_READINESS.md`](OPEN_SOURCE_READINESS.md). Each item links to the finding that justifies it — this checklist does not introduce any new claim.

## Before making the repository public

- [x] Replace the real internal reference in `tests/test_intake.py` and `docs/28-gitlab-issues-and-board.md` with the existing `emmany` / `EGW-142` example. — done.
- [x] Apply a real license. — MIT applied.
- [x] Resolve the organization-specific example catalog and its submodule dependency. — `gad-digital`/`gad-guidelines` removed, replaced by the fully self-contained `sample-organization` catalog; a plain `git clone` now suffices (no `--recurse-submodules` needed).
- [ ] Decide whether `factory.gaddigital.io` remains the public schema/API namespace (Core infrastructure, not example content — left unchanged pending this decision).
- [ ] Publish as a fresh, squashed initial commit rather than pushing this repository's existing git history (removes personal email exposure from authorship metadata) — **or** explicitly accept publishing the existing history as-is.
- [ ] Re-run the secret scan performed in this audit (emails, tokens, private IPs, internal URLs) against the exact commit that will become the public initial commit — not against a prior state.
- [ ] Rename the default branch to `main` (or the organization's chosen convention) before or at the moment of publication.

## Before announcing the project

- [ ] Add `CONTRIBUTING.md` (clone, install, Python version, test, and one example per extension point — see `OPEN_SOURCE_READINESS.md` § Contribution Model).
- [ ] Add `SECURITY.md` with a real reporting contact, a stated supported-version policy, and an explicit "do not file a public issue for a suspected vulnerability" statement.
- [ ] Add `.github/ISSUE_TEMPLATE/bug_report.yml`, `feature_request.yml`, `documentation.yml`.
- [ ] Add `.github/PULL_REQUEST_TEMPLATE.md` (Problem, Change, Tests, Documentation, Backward compatibility, Schemas/contracts affected, Security implications, Agent-specific dependency introduced?, Core agnosticism preserved?).
- [ ] Add `GOVERNANCE.md` (two sentences — see `OPEN_SOURCE_READINESS.md` § Governance; do not build more than that).
- [ ] Reconcile or retire `QA_REPORT.md` (currently states `1.11.0`/95 tests against an actual `1.15.0`/195-test reality).
- [ ] Fix the two stale "`task.normalized` is the first event" mentions in `docs/22-project-installation-guide.md` and `docs/23-first-steps.md`.
- [ ] Tag `v1.15.0` (the only existing tag, `v1.14.0`, is four commits behind `HEAD`).
- [ ] Configure the GitHub repository: description, topics (see `OPEN_SOURCE_READINESS.md` § GitHub repository configuration), Discussions enabled, Wiki disabled, squash-merge only.
- [ ] Configure branch protection on the default branch: PR required, CI check required, one review required, no force-push, no deletion.
- [ ] Add exactly one dependency-update bot — Dependabot recommended given the current dependency surface — not both Dependabot and Renovate.

## Before accepting external contributions

- [x] Document that the Factory Core is organization-agnostic and how a company maintains its own catalog separately — `organization/README.md` now states this in prose; a dedicated step-by-step walkthrough is still optional, not required.
- [ ] Add a lint/type-check step to `.github/workflows/quality.yml` (none exists today — `ruff`/`mypy` are configured nowhere in `pyproject.toml`).
- [ ] Test CI against every Python version declared supported (`requires-python = ">=3.11"`; CI currently only runs `3.12`).
- [ ] State the compatibility policy explicitly (project configuration, Runtime state, schemas, adapters, organization catalogs — see `OPEN_SOURCE_READINESS.md` § Compatibility policy) so a contributor knows what a breaking change actually is.
- [ ] Confirm the CI workflow requires no organizational secret to pass for an external contributor's fork/PR (already true today — re-verify after any CI change).

## Before the first stable release

- [ ] Formalize a required `### Breaking` heading in `CHANGELOG.md` entries that touch schemas, `project.yaml`, workflow contracts, Skills, organization catalogs, or adapters.
- [ ] Automate release packaging (tests → build → attach to GitHub Release on tag push) without automatic publication to any public package index until a distribution channel and package-name ownership are explicitly decided.
- [ ] Resolve the three known test failures documented in `docs/34-release-readiness.md` (two of which are likely already resolved by the public/internal boundary decision above) or explicitly re-document them as accepted, supported-version exceptions.
- [ ] Complete enforcement of the organization policies currently schema-defined but not code-enforced (`change-policy`, `context-policy`, `external-action-policy`, `traceability-policy`, `recovery-policy`, `memory-policy` — see `docs/34-release-readiness.md`), or explicitly scope them out of `1.0`.
- [ ] Add a lock file (`uv.lock` or equivalent) once CI reproducibility matters more than the current minimal dependency surface warrants today.
