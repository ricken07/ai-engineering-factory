# Research decision record — 2026-11-21

Status: **ACCEPTED; implementation verification pending**.
The scientific model stays fixed. This record is an *internal research archive*, not a narrative intended for a Stage-1 manuscript.

## Agreed decisions

1. Re-freeze the implementation, treatments, environment and confirmatory protocol once stable. Report only the final exact tag, SHA, Git tree SHA and observed checks in the Stage-1 manuscript.
2. Preserve historical research baselines, reports and supersession reasons in versioned internal archives; do not destroy prior evidence and do not discuss previous baselines in the submitted Stage-1 manuscript.
3. Rename the audit-response section to **“Bound plan in `create-plan` (implemented in `c10ee6d`)”**. RF-06 is implemented but requires clean-checkout tests; whether bound verification commands replace or supplement profile validation remains open.
4. RF-05 shall audit **rendered** agent-visible payloads, not merely input fingerprints; include phase briefs, skill contracts, rework findings and human waivers.
5. Keep optional human review finding waiver support for ordinary AIEF operation, but configure **`review.waivers: disabled`** for each primary scored L3 experiment.
6. The Runtime, not a prompt, must refuse waiver attempts, persist refusal evidence, and expose the execution-time waiver policy under `Execution.reproducibility.reviewWaivers`. Its value is independent of `experimentalCondition` and autonomy.
7. The study runner validates explicit disabled configuration, no successful waiver decisions and all refusal/events. A missing project configuration does **not** prove waivers were disabled.
8. Keep `MAX_REWORKS = 3`; `review-rework-exhausted` is a study-defined failed outcome and cannot be overridden in scored runs. The Runtime's recorded state is `blocked` until evaluation.
9. An independent SWE-bench oracle judges outcomes without consulting waivers; contamination from waiver usage principally affects the L3 trajectory, evidence completeness (H3) and time/effort (H4), and can affect rework and submission status. H2 relies on independently evaluated task outcomes.
10. RF-07 must predefine human gate actors, response rules and timing/timeout. No fabricated human approvals.
11. Waiver-enabled runs, if any, belong to exploratory studies outside confirmatory H1–H4.

## Traceability and expected proof

- RF-06 source: `c10ee6dfcf1361e65c1be10174f89ce81659c4d8`. Status: `IMPLEMENTED / PENDING INDEPENDENT VERIFICATION`.
- Waiver restriction: this branch (not merged or frozen merely because code exists).
- Evidence needed: project schema, Runtime denial, `approvalRefusals`, `gate.approval-refused`, immutable run-policy snapshot, tests, clean checkout and hashed logs.
- Remaining blocking work: RF-05 rendered-payload ledger, RF-07 human gate rules, dependency lock and full preflight.
