# Changelog

## Unreleased

- `check_leakage.py`: the escalation reviewer is the process's effective account (effective uid), not `LOGNAME`/`USER`; `--anchor` is required with every custody option; custody operations are serialized by an inter-process lock on the register.
- The launcher's isolated `HOME` can link from a study home (`isolation.homeSource`) and per group (`homeLinks` under `plain`/`governed`), so governed runs receive only the AIEF adapter skills of the frozen Factory and no entry of the operator's real home; `run.yaml` records the group links.
- `check_leakage.py`: every custody write exports the new register head and `--anchor` checks heads recorded outside custody; unreadable custody files are `CUSTODY_ERROR`; the exception is authorized in the register by a listed reviewer account (`--authorize-exception --reviewers`) instead of an authorization file; `--verdict-only` requires the custody circuit.
- `check_leakage.py` custody is fail-closed: attempt and exception logs are checked against a hash-chained reference register (`--task`, `--register`), created only with `--init-attempt-log`, and a missing, truncated or inconsistent log stops the check (`CUSTODY_ERROR`, exit 3). The single reviewer-approved exception check (`--exception-log`, `--exception-authorization`) records its result for the escalation reviewer only.
- `check_leakage.py` flags code-shaped identifiers the oracle introduces (absent from the base repository and the `--allowed` issue text) and bounds revision cycles with `--attempt-log`/`--max-attempts`, answering ESCALATE beyond the limit (researcher decisions A1.4, A1.7).
- The launcher charges its active budget as RC2 §9.4 defines active time: elapsed time since the first agent step minus the union of human-gate waits read from the execution record (researcher decision A9). Time between steps that is not a gate wait now counts; `run.yaml` records `activeSeconds` and `agentSeconds`.
- `check_leakage.py --verdict-only` gives treatment authors the verdict and the treatment line numbers only.
- Added study tools after the 1.15.0 freeze: `check_leakage.py` (treatment files against the hidden oracle, reporting counts and positions only) and the scorer skeletons `score_h2.py` (D_group with the missing-component rule), `score_h3.py` (E01–E12 evidence completeness, built-in verifiers for launcher-captured items) and `score_h4.py` (wall-clock, union of gate waits, active wall-clock). The Runtime is unchanged.

## 1.15.0

- The experiment launcher enforces an active budget per run (`activeBudgetMinutes`, 120 by default): agent steps run with the remaining budget as timeout, waits on human gates do not count, and reaching it records `RESOURCE_LIMIT_REACHED`, mapped to `execution-failure` by `study_outcome.py`. `tests/test_gate_bound.py` derives the upper bound on human gate requests per run (10 requests, 9 waits for `implement-task`).
- The CI checks that `uv.lock` matches `pyproject.toml` (`uv lock --check`) and installs with `uv sync --locked`.
- `compare_payloads.py` reports forbidden content by count and line number only, never repeating it.
- Fixed `aief execution gate-check` listing the plan gate of a cancelled execution (rejected or expired) as still waiting.
- Tests set a neutral Git identity, so that their commits and the Runtime's integration merge do not depend on the machine's Git configuration (a CI runner has none); the quality workflow can also be run manually.
- Added an integration test of the payload comparison on a ledger the Runtime wrote: bound L2 files, two review rework loops and an L1 context rendered by the launcher; the review feedback is counted against the rework budget and reported as intervention.
- Added negative tests for every gate comparator (`tests/test_comparator_negatives.py`): each check of `bound-plan-hashes`, `plan-criteria`, `governed-plan`, `proposal`, `submission-evidence` and `integration` is broken on its own and must leave `match`; a coverage test fails when a comparator emits a check without a negative case.
- The CI installs exactly the committed `uv.lock` (`uv sync --frozen`, uv 0.9.28, Python 3.12) and runs the suite and the package validation through `uv run --frozen`.
- `compare_payloads.py` accepts the L3-only `## Repositories` brief section as procedural and lists it.
- Added `tools/experiment/compare_payloads.py`, which compares the payload ledger of an L3 execution with the frozen L1/L2 treatment (same plan, verification and practices; no extra task facts, forbidden content or decision rationale delivered; review feedback within the rework budget).
- Fixed test imports that broke collection under a plain `pytest` invocation, as the CI runs it.
- The study tools default to `--rule-version v4`, the decision rule pinned for scored runs.
- The decision validator and the study outcome mapping take `--rule-version v3|v4`: under gate-rule-v4 a `verification:frozen` mismatch is setup-invalid like `plan:frozen`, and refused attempts are attributed to the agent (counted in H1) or to an operator (protocol deviation). The study outcome of a run still waiting at collection is now `unfinished` (mapping version 2).
- The commands of a bound verification (`commands: [{id, command, cwd?, repository?}]`) run during `validate-change` together with the profile commands; each result is evidence `<repository>:bound-verification:<id>:exit-<code>`, and malformed commands are refused before the execution starts.
- Added `tools/experiment/study_outcome.py`, which maps the Runtime facts of an L3 run to its study outcome in a separate `study-outcome.yaml`, without rewriting the Runtime records.
- Added plan revision: at the plan gate a human asks for changes with `/revise <changes>` (`$revise` in Codex) through the approval hook, or `aief execution revise-plan` at the terminal. The decision is recorded as `changes-requested` (`OBSERVED`), the plan is archived as `-revision-N`, and the planning phase reopens with the feedback in its brief; the revised plan waits at the same gate. At most three revisions; refused for a bound plan.
- Added `tools/experiment/check_decisions.py`, an independent validator of human gate decisions: it checks each recorded decision against the pinned decision rule (decision, rationale, rule hash, approver, channel) and classifies rejections as the study rule states.
- The terminal confirmation of a human gate decision names the decision (approval, rejection or waiver) in its prompt and in its refusal message.
- Fixed `aief execution approve` on an execution with no phase gate waiting: it is refused instead of completing the execution again, which recorded an approval and restarted the integration wait of `before-merge`.
- Fixed `before-merge` decisions on a completed execution: a human at the terminal decides without `--owner` while an agent holds the lease, and the response limit runs from the integration request (`integration.requestedAt`) rather than from the moment the policy first required the gate.
- Fixed the recorded human wait of `before-merge`: an approval or a rejection records the wait from the integration request to the decision as `DERIVED`, and an approval keeps its wait start although the merge ends the integration wait.
- Applied the response limit to `before-merge` after completion: the merge gate waits from the moment the Runtime requests the integration, expires at its deadline and can be rejected; both keep the execution `completed` and set the integration to `expired` or `rejected`. `aief execution gate-check` now applies a passed deadline, and the experiment launcher polls through it.
- Added the `integration` comparator for `before-merge`: completed execution awaiting integration, submission evidence, existing branches, task branch containing the validated revision, clean base branch and a clean merge checked with `git merge-tree` before the Runtime merges; `aief execution gate-check` now also shows `before-merge` on a completed execution.
- Added comparator evidence for every study gate: `plan-criteria` (plan gate without bound plan), `governed-plan` (`before-implementation`), `proposal` (`apply-proposal`) and `submission-evidence` (`before-commit`, `before-submission`, submission gate), computed before the decision changes the execution and shown by `aief execution gate-check`.
- Made the gate decision rule verifiable: `humanGates.decisionRule` is a rule document hashed (optionally pinned by `decisionRuleSha256`) and copied into each execution, and plan gate decisions store the `bound-plan-hashes` comparator evidence (expected frozen hashes from `--expect-plan-sha256` / `--expect-verification-sha256`, bound hashes, file integrity, planning reference); `aief execution gate-check` shows the approver the same evidence.
- Added the human gate protocol: `humanGates` (approvers, response limit, decision rule) is snapshotted per execution. Every gate decision is recorded in `gateDecisions`, a gate past its response limit expires and cancels the execution, and `aief execution reject` lets a human refuse a gate with a rationale through an `OBSERVED` channel.
- Added the payload ledger: each phase preparation records what the agent received (phase brief and `execution next` snapshots, Core Skill files, bound plan files) with SHA-256 and a classification per item and brief section; `aief execution payload-ledger` reports it and fails on any gap.
- Added bound plans: `aief run --bound-plan --bound-verification` fixes the task plan and verification before the execution starts; the Runtime records the `planning` phase from them, unchanged and verified by SHA-256, and refuses an agent-written plan.
- Fixed `aief setup-adapter --execute` crashing with `AttributeError: 'Namespace' object has no attribute 'path'` after a successful install; the command now exits 0 in both dry-run and execute modes.

## 1.0.0 — First release

- Established an agent-agnostic core based on contracts, schemas and deterministic policies.
- Added reusable workflows, skills, technology profiles and agent adapters.
- Added request intake, task registry and resumable execution runtime.
- Added capability, integration, provider and MCP binding resolution.
- Added profile-driven validation with structured reports and blocking checks.
- Added inherited engineering contexts, mandatory practices and traceability.
- Added task tracking, duplicate detection and controlled external operations.
- Added workspace and Git safety, including drift detection and protection against destructive operations.
- Added idempotence, execution leases, controlled recovery and handoff between agents.
- Added dynamic policy re-evaluation and the most-restrictive-constraint rule.
- Added runtime governance, replayable evidence, observability and scenario evaluation.
- Added backlog import with dependencies, parent-child relationships and idempotent operations.
- Added task ordering and the `ready`, `blocked`, `active` and `done` readiness states.
- Added documentation, consistency checks, tests and the associated CLI commands.
