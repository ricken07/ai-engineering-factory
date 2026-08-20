# Open Source Readiness

Audit performed against the actual repository state (commands executed, files read — not documentation alone), for AI Engineering Factory `1.15.0`, ahead of a planned public GitHub release.

```text
OPEN_SOURCE_BLOCKER: LICENSE missing
```

`LICENSE` at the repository root contains only: *"Internal use template. Replace this file with the organization-approved license before external distribution."* There is no real open-source license in this repository today. Per the mission's own instruction, this repository must not be presented as ready for public contribution until this is resolved. No license was invented or assumed on its behalf.

## Community artifact status

| Open-source artifact | Status | Recommendation |
| --- | --- | --- |
| `README.md` | READY | Rewritten this session against verified repository state; see summary below. |
| `LICENSE` | MISSING | Placeholder text only, explicitly marked "internal use". **P0**: the organization must choose and apply a real license before any public push. |
| `CONTRIBUTING.md` | MISSING | Not present anywhere in the repository. **P0**: a public repository needs a contribution process (branch/PR conventions, review expectations, the non-negotiable Core-agnosticism invariants) before it can responsibly accept outside contributions. |
| `CODE_OF_CONDUCT.md` | MISSING | Not present. **P1**: standard for any public GitHub project accepting external participation; adopt a known template (e.g. Contributor Covenant) rather than drafting one from scratch. |
| `SECURITY.md` | MISSING | Not present. **P0**: this project handles autonomy, gates and integration credentials — a public repository without a vulnerability-disclosure path is a real gap, not a cosmetic one. |
| `CHANGELOG.md` | PARTIAL | Present and well-maintained through `1.15.0`, but not linked from the README before this session and not cross-checked against `VERSION`/`pyproject.toml` as part of any CI gate. **P1**: add a CI check that the three version sources agree (a real drift already happened once — see Findings). |
| Issue templates (`.github/ISSUE_TEMPLATE/`) | MISSING | Not present. **Later**: add a minimal bug-report/feature-request template once the project has external users. |
| PR template (`.github/PULL_REQUEST_TEMPLATE.md`) | MISSING | Not present. **Later**: add one referencing the Core-agnosticism invariants once `CONTRIBUTING.md` exists to point to. |

`.github/workflows/quality.yml` does exist and is real: it runs `pytest` and `tools/validate_package.py` on Python 3.12 for every push/PR. This is a genuine, working CI gate — worth keeping and eventually badging once the repository has a public GitHub location (the badge URL cannot be verified before that).

## Findings — documentation/code inconsistencies

1. **Stale QA report.** `QA_REPORT.md` at the repository root states `Version: 1.11.0` and *"the complete automated suite passes with 95 tests"*. The repository is at `1.15.0` with 195 tests (192 passing). This file predates four minor releases and, left as-is, misrepresents current QA status to a new reader. **P1**: regenerate it, fold it into `docs/34-release-readiness.md`, or delete it — do not publish it unchanged.
2. **Event-log documentation drift, introduced this session.** `docs/22-project-installation-guide.md` (checklist item, line ~883) and `docs/23-first-steps.md` (lines ~68 and ~311) both state the Runtime event log "starts with `task.normalized`". Since the Runtime Observability increment in this same series, the log actually starts with `request.created`, then `intent.resolved`, then `task.normalized` (see `docs/32-runtime-observability.md`, already updated). These two references were not updated in the same pass. **P1**: fix both mentions; low effort, currently misleading for anyone following the Go/No-Go checklist literally.
3. **Version drift previously self-corrected.** The former README referenced `~/.gad/ai-engineering-factory/0.1.0/` as an example install path — four minor versions behind `1.15.0` and inconsistent with every other document, which use `1.15.0` throughout. Corrected in the rewritten README (this session); no other document was found with the same stale value.
4. **`README.md` previously declared `Status: Stable`** directly above a "Stability" section stating `v1alpha1... may still evolve before a stable v1 contract" — a direct self-contradiction. Corrected to `Alpha` in the rewritten README, consistent with the `v1alpha1` API version, the 3 known test failures, and the several unenforced policy files documented in `docs/34-release-readiness.md`.

## Findings — structural blocker for external contributors

5. **The shipped example organization catalog references a private submodule.** `organization/catalogs/gad-guidelines` is a git submodule pointing at `gitlab.com/Gad-Digital-IT/shared/guidelines.git` — a private, organization-internal repository. Any external contributor cloning this project publicly will be unable to fetch it, reproducing the same two test failures already diagnosed in `docs/34-release-readiness.md` (`test_organization_catalog_selection_changes_effective_practices`, `test_package_is_valid`). The blast radius is limited — 192 of 195 tests, the shipped `templates/project` default, and the `examples/emmany` reference project (which only selects the public `factory-default` catalog) are entirely unaffected — but shipping a reference to private infrastructure inside a public open-source repository is not appropriate regardless of blast radius. **P0 before public push**: either make the submodule genuinely public, replace it with a fully public example catalog, or remove the `gad-digital`/`gad-guidelines` example content and keep only `factory-default`.

## Findings — minor hygiene

6. **`.idea/` is tracked despite being gitignored.** `.gitignore` excludes `.idea/`, but five files under it (`ai-engineering-factory.iml`, `awsToolkit.xml`, `misc.xml`, `modules.xml`, `.idea/.gitignore`) are already committed — gitignore does not retroactively untrack. Content checked: no secrets, only a maintainer's local AWS region preference. **Later**: `git rm -r --cached .idea` before public push; cosmetic, not a security issue.

## Recommendations

| Priority | Action |
| --- | --- |
| P0 | Apply a real, organization-approved LICENSE. |
| P0 | Resolve the private-submodule reference in the example organization catalog (make public, replace, or remove). |
| P0 | Add `CONTRIBUTING.md` and `SECURITY.md`. |
| P1 | Add `CODE_OF_CONDUCT.md` (adopt a standard template). |
| P1 | Fix the two stale `task.normalized`-first-event mentions in `docs/22` and `docs/23`. |
| P1 | Regenerate or retire `QA_REPORT.md`; it is four releases stale. |
| P1 | Add a CI check that `VERSION`, `pyproject.toml`, and `factory.yaml` versions agree (this exact drift already happened once, per `CHANGELOG.md` 1.15.0). |
| Later | Add `.github/ISSUE_TEMPLATE/` and `.github/PULL_REQUEST_TEMPLATE.md`. |
| Later | Untrack `.idea/`. |
| Later | Add a CI badge once the repository has a public GitHub location (URL cannot be verified before that). |

None of the P0/P1 items above were fixed as part of this session beyond the README itself — per the mission's instructions, community files are not created here except where required to repair a README link, and none were.
