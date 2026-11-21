# Dynamic Policy Re-evaluation

Version 1.10.0 turns policy evaluation into a bounded Runtime loop. Decisions are no longer assumed to remain valid after the initial task analysis.

## Evaluation points

The Runtime automatically re-evaluates after successful execution of:

- `analyze-impact`;
- `create-plan`.

Skills provide observations; the deterministic Runtime applies Factory policies and project constraints:

```text
observed repositories, domains and change types
  + previous task classification
  + repository critical domains
  + project requested/maximum autonomy
  + Factory risk, autonomy and approval policies
  -> effective PolicyDecision
```

Risk and scope are monotonic during one Task: new evidence can increase them but cannot silently remove previously established repositories, domains, change types or risk.

## Example: escalation after impact analysis

```text
Initial task: MEDIUM / L3
  -> analyze-impact finds payment + two repositories
  -> risk HIGH
  -> autonomy L2
  -> external tracking REQUIRED
  -> before-commit and before-submission gates
```

The decision is persisted in the Execution as `policy-decision-001.yaml`. The Task receives the effective classification and authorized autonomy.

## Example: destructive migration discovered in planning

```text
Current decision: HIGH / L2
  -> create-plan discovers destructive-migration
  -> risk CRITICAL
  -> autonomy L1
  -> before-implementation gate added
  -> workflow waits for human approval
```

The second decision is stored as `policy-decision-002.yaml`; the earlier artifact remains available for audit.

## Pre-phase gates

Dynamic gates are stored independently from workflow completion gates. This prevents a governed skill from running before approval:

```bash
aief execution next <execution-id>
# status: waiting-approval
# requiredPolicyGates: [before-implementation]

aief execution approve-policy <execution-id> before-implementation \
  --approver alice
```

### Approver identity

Policy decides which gates require a human; it never relaxes how the approval
reaches the Runtime. Every human approval must be `OBSERVED`: typed as
`/approve` in an agent session with the approval hook installed, or in the
human's own terminal. An approval relayed by an agent is refused at every
risk level and recorded as evidence. See [34 — Human Approval](34-human-approval.md).

## Resolution rules

- highest applicable risk wins;
- previous risk is retained when new evidence is less restrictive;
- lowest autonomy ceiling wins;
- denied actions are all actions above the authorized autonomy;
- required gates accumulate and approved gates remain approved;
- repository critical domains participate even when omitted by agent output;
- schema-invalid phase output never triggers re-evaluation;
- unresolved tracking and workspace safety remain independent mandatory checks.

The agent still performs semantic impact and planning analysis. It never decides the effective autonomy or removes a required human gate.

Each decision revision produces a corresponding fingerprinted governed plan.
Required gates also receive Runtime `EnforcementPoint` records. Their assurance
describes the active phase-transition guard only; it does not claim control of
parallel commands outside Runtime. Gate waiting starts once when requested and
ends on the persisted decision, including after a resumed execution.
