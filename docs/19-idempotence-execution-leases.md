# Idempotence & Execution Leases

Version 1.9.0 prevents duplicate Runtime transitions and concurrent writes by different coding-agent sessions. It remains a local deterministic mechanism: no scheduler, daemon, database or distributed lock is introduced.

## Execution ownership

Before mutating an Execution, an adapter acquires a lease with a session-specific owner:

```bash
aief execution lease acquire <execution-id> --owner codex:session-42 --ttl 300
aief execution lease renew <execution-id> --owner codex:session-42 --ttl 300
aief execution lease status <execution-id>
aief execution lease release <execution-id> --owner codex:session-42
```

The acquisition uses atomic file creation. Another owner is rejected until the lease is released or expires. The active lease is persisted as `lease.yaml` under the Execution directory and validates against `ExecutionLease`.

When a lease exists, mutating calls must present the matching owner. Existing projects without an acquired lease remain compatible, while adapters are expected to acquire one before engineering execution.

## Replay-safe transitions

Adapters provide a stable operation ID for every retriable transition:

```bash
aief execution complete-phase <execution-id> \
  --output understanding.yaml \
  --operation-id complete-understand-001 \
  --owner codex:session-42

aief execution approve <execution-id> \
  --operation-id approve-plan-001 \
  --owner codex:session-42
```

The first call records a `RuntimeOperation`. Repeating the same operation ID with identical input returns the recorded result without advancing again. Reusing it with different input fails with an idempotency conflict. Failed operations retain their ID and may be retried; an operation still marked `running` cannot execute concurrently.

Provider operations keep their existing stable operation IDs. Repeating the same approval decision is now harmless; attempting to reverse a persisted approval through replay is rejected.

## Claude to Codex handoff

```text
Claude owns lease
  -> persists artifacts and handoff
  -> handoff releases lease
  -> Codex acquires lease with a new owner
  -> Runtime verifies persisted state
  -> Codex resumes the next phase
```

Use:

```bash
aief execution handoff <execution-id> --owner claude-code:session-7
aief execution lease acquire <execution-id> --owner codex:session-42
```

Conversation state is never used to establish ownership or decide whether an operation already completed.

## Failure behavior

- active lease owned by another session: `BLOCK`;
- expired lease: new owner may acquire it;
- missing owner while a lease is active: `FAIL`;
- same operation ID and same input: `RECOVER` by replaying the result;
- same operation ID and different input: `FAIL`;
- concurrent operation still marked running: `BLOCK`;
- identical repeated approval: return the persisted decision;
- contradictory repeated approval: `FAIL`.

This increment intentionally does not add distributed scheduling, background workers, automatic agent routing or cross-machine locking.
