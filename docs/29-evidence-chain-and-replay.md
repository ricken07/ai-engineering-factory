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
  → validation
  → evidence matrix
  → independent review
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

Each criterion must be covered in `validation.yaml` by an item in
`details.evidenceMatrix`:

```yaml
details:
  evidenceMatrix:
    - id: AC-001
      status: verified
      evidence: [EV-001]
```

A criterion without proof, or with status other than `verified`, blocks
submission.

## Validation Evidence

`validate-change` preserves notably:

- `details.validationPlan`: exact commands and repositories involved;
- `details.results`: return code, output and error of each command;
- `details.commits`: Git commit tested per repository;
- `details.evidenceMatrix`: coverage of criteria.

A successful validation must therefore be tied to the code actually tested,
not merely an agent assertion.

## Independent Review

The review must be produced independently of implementation. It must
contain:

```yaml
details:
  independent: true
  implementationSession: implementation-123
  reviewerSession: review-456
  decision: approved
  blockingFindings: []
```

The Runtime refuses submission if sessions are identical, if review is
not approved, or if blocking findings remain open.

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
