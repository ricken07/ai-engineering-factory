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
  --owner codex:session-42
```

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
