# 29 — Evidence Chain and Validation Replay

## Goal

Agent self-evaluation is not enough to declare a modification conforming. The
Factory requires a structured, persisted and replayable evidence chain before
submission.

```text
Need
  → acceptance criteria
  → plan
  → implementation
  → validation (Runtime-observed)
  → independent review with evidence matrix
  → submission authorized
```

## Acceptance Criteria

The plan must expose criteria in `planning.yaml`:

```yaml
details:
  acceptanceCriteria:
    - id: AC-001
      statement: "API contract remains compatible."
    - id: AC-002
      statement: "Reading respects the authenticated user."
```

A workflow that ends with submission refuses a completed plan without
criteria (`{id, statement}`, unique ids), so a missing criterion is caught at
planning rather than at submission.

### Bound plan

A plan prepared and reviewed before the execution can be bound to it:

```bash
aief run "/implement TASK-42" --bound-plan plan.md --bound-verification verification.yaml
```

The Runtime copies both files unchanged into `bound-plan/` in the execution
directory and records their SHA-256 in `planBinding`, in the reproducibility
record (`boundPlanFingerprint`, `boundVerificationFingerprint`) and in the
`contextFingerprints` of every Governed Execution Plan. The bound plan can be
any text file. The bound verification is a YAML mapping. In a workflow that
ends with submission, it must list `acceptanceCriteria` as `{id, statement}`.
The binding is refused before the execution starts when a file is missing,
when the workflow has no `create-plan` phase, or when the criteria are missing.

When `aief execution next` reaches `planning`, the Runtime performs the phase
itself, as it does for validation. `planning.yaml` references the bound files
by path and hash and copies their acceptance criteria verbatim. No agent writes
a plan: an agent output for `create-plan` is refused. A bound file changed after
binding is refused by its hash. Policy reassessment after planning and the plan
gate apply unchanged. Every phase brief lists the bound files and their hashes,
so the agent reads the plan and verification it was given.

Each criterion must be covered by the independent review, in
`review.yaml` `details.evidenceMatrix`:

```yaml
details:
  evidenceMatrix:
    - id: AC-001
      status: verified
      evidence: [api:maven:test:exit-0]
    - id: AC-002
      status: verified
      evidence: ["review:the query filters on the authenticated user id"]
```

An evidence entry is either a successful command the Runtime observed during
validation (`<repository>:<profile>:<operation>:exit-0`) or an explicit
reviewer observation (`review:...`). The Runtime refuses an approving review
whose matrix misses a criterion or cites anything else: deciding which
evidence proves a criterion is a judgement, made by the independent reviewer,
while the evidence itself stays observed. A criterion without proof, or with
status other than `verified`, blocks submission. Executions recorded before
this rule may still carry the matrix in `validation.yaml`.

## Validation Evidence

`validate-change` preserves notably:

- `details.validationPlan`: exact commands and repositories involved;
- `details.results`: return code, output and error of each command;
- `details.commits`: Git commit tested per repository;

A successful validation must therefore be tied to the code actually tested,
not merely an agent assertion.

`aief execution evidence <execution-id>` derives an `EvidenceBundle` from the
persisted artifacts. `aief execution metrics <execution-id>` exports structured
observations keyed by task and execution; unavailable provider fields remain
explicitly unavailable rather than estimated.

## Independent Review

The review must be produced independently of implementation. Review output may
declare session labels, but declarations are not identity proof. The Runtime
stores producer and reviewer identities with source and assurance, then derives:

```yaml
review:
  independentRequired: true
  independence: INDEPENDENT # or NOT_INDEPENDENT / UNVERIFIED / NOT_REQUIRED
```

Distinct identities prove `INDEPENDENT` only when both are trusted and the
producer handed the execution off (`aief execution handoff`) before the
reviewer took it. A lease owner is a free label: one session can acquire a new
lease under another name, so distinct owners without that handoff produce
`UNVERIFIED`. Same reliable identity produces `NOT_INDEPENDENT`; missing,
declared-only or insufficiently comparable identity produces `UNVERIFIED`.
Required independent review fails closed for every state except `INDEPENDENT`,
and the Runtime checks it when the review phase completes, so workflows without
a submission phase are covered too. Review approval and
blocking findings remain separate required checks.

## Review Outcome and Rework

A review that does not approve the change ends the pass. When a completed
review has a decision other than `approved`, or any blocking finding, and the
workflow implements before it reviews, the Runtime returns to implementation
instead of advancing:

1. the review artifact is persisted, then the implementation, validation and
   review artifacts are kept under a `-rework-N` name
   (`review-rework-1.yaml`, ...);
2. those phases are reopened as `pending`, and `execution next` points to the
   implementation phase again;
3. the implementation phase brief gains a **Rework N** section with every
   blocking finding (severity, criterion, location, expected correction);
4. a proposal made below L2 is superseded: the next implementation proposes
   again, and a human approves `apply-proposal` again;
5. review independence is reset: after the new implementation, the producer
   hands off again and another session reviews.

Summary, traceability and the human submission gates are never reached with
a rejected change: a human is not asked to approve a submission the evidence
chain would refuse. Each return is recorded in `reworks` (number, time,
review, decision, findings, archived artifacts) and emitted as an
`execution.reworked` event.

Reworks are bounded: after `MAX_REWORKS` (3) returns, a further rejecting
review blocks the Execution (`review-rework-exhausted`) and the human decides
whether to cancel it and start again, for example with a revised task. A
review-only workflow, which implements nothing, reports its decision without
rework.

## Human Decisions on Review Findings

A review is an agent's assessment: its findings are evidence for the human,
not control authority (reference model, invariants 5 "isolation of
probabilistic reasoning from control authority" and 12 "explicit human
accountability"). The human may therefore decide that a blocking finding does
not block the change. Without that decision, a blocking finding keeps
blocking: nothing is waived implicitly.

The decision is made finding by finding, with a justification, through a
human channel the Runtime observes, exactly like a gate approval (see
[34 — Human Approval](34-human-approval.md)):

```text
/waive 1 the raw variable is out of scope for BK-02      # in the agent session ($waive in Codex)
```

```bash
aief execution waive-finding <execution-id> 1 \
  --reason "the raw variable is out of scope for BK-02" --approver alice   # in your own terminal
```

The finding number is its position in the review's `blockingFindings`. The
target is the review that triggered the latest rework, or the review that
blocked the Execution after the last allowed rework. An agent cannot decide:
a relayed decision is refused and recorded in `approvalRefusals`.

Each decision is kept in `findingDecisions`, bound to the exact review it
answers by the review artifact's SHA-256, with the finding summary, the
justification, the time and the human actor (`OBSERVED`); it is emitted as a
`review.finding-waived` event and included in the EvidenceBundle under
`verification.findingDecisions`.

When every blocking finding of that review is decided:

- if the rework it triggered has not started (its implementation phase was
  not prepared), the Runtime undoes it: the archived artifacts get their
  names back, the reopened phases are completed again, the rework is marked
  `overruledAt`, and the Execution continues towards submission;
- if the Execution was blocked after the last allowed rework, it resumes
  towards submission;
- if the rework already started, the decisions stand and are carried by the
  phase briefs: the implementation brief tells the producer not to address
  the waived findings, and the review brief tells the next reviewer not to
  raise them again as blocking unless the change made them materially worse.

At submission, a review whose decision is not `approved` is accepted only
when it has blocking findings and the human decided every one of them; all
other submission evidence checks still apply.

## Replay

Validations can be replayed with:

```bash
aief execution replay-validation <execution-id> \
  --project "<PROJECT_ROOT>" \
  --factory "<FACTORY_HOME>"
```

The Runtime rereads the recorded plan, verifies each repository is
still on the tested commit, then reruns commands without code modification.
The result is saved in:

```text
.ai/runtime/executions/<execution-id>/validation-replay.yaml
```

If the repository changed since initial validation, replay fails and
a new validation is needed.

## Submission Gate

`submit-change` requires the following:

```text
planning.yaml present
validation.yaml present and successful
complete evidence matrix
independent review approved
no blocking findings
policy gates satisfied
```

This check occurs before any commit, MR/PR or merge. Delivery mode choice
and authorization gates remain separate from technical proof.

## Evidence bundle

On completion, `evidence-bundle.yaml` indexes the Task, Execution,
GovernedExecutionPlan, PolicyDecision, EnforcementPoints, actor identities,
review independence, validation revision/results, gates, experimental metrics,
reproducibility metadata and final artifacts. It stores references and SHA-256
fingerprints instead of duplicating phase contents, and is itself fingerprinted.
