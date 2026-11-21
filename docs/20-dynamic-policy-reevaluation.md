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

A gate approval carries human accountability, so the Runtime records how it
established who approved, on the gate's `actor`, instead of assuming a
`human`:

| Channel | When | Assurance |
|---|---|---|
| `interactive-terminal` | the command has a controlling terminal, outside an agent harness; the Runtime asks there to retype the gate id | `OBSERVED` |
| `agent-relay` | `--owner` names the agent session holding the lease, or the command runs inside an agent harness (`CLAUDECODE`, `CODEX_SANDBOX`) | `DECLARED` |
| `non-interactive` | any other call without a terminal | `DECLARED` |

`--approver` names the person; without it, an interactive approval records
the operating-system account and a relayed one records `human`. The account,
the detected harness and the relaying session are kept as observations.
`OBSERVED` is not authentication: it shows that someone typed the
confirmation at a terminal the agent sessions do not have, not who it was.
Whatever the channel, an agent identity of the execution (producer,
reviewer, lease owner, handoff sender) is refused as approver, so a session
cannot record its own decision as a human one.

The human approval policy sets the minimum assurance. At `critical` risk
(`approvalAssurance: OBSERVED` in `core/policies/human-approval-policy.yaml`),
every human approval of the execution, phase approvals and policy gates
alike, must be typed at a terminal: a relayed or non-interactive approval is
refused and the gate stays pending. The requirement is carried by the
`PolicyDecision` (`gates.approvalAssurance`) and the `GovernedExecutionPlan`
(`requirements.approvalAssurance`), so a reassessment that raises the risk to
`critical` applies it to the gates still pending. Below `critical`, a
`DECLARED` approval is accepted and recorded as such.

`before-implementation` protects the implementation phase. `before-commit` and `before-submission` protect submission. Merge remains outside the current local Runtime and therefore cannot be implicitly authorized.

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
