# 05 — Policy Resolution

Policies may come from multiple layers:

```text
Factory
  ↓
Organization
  ↓
Profile
  ↓
Project
  ↓
Repository
  ↓
Task
```

## Resolution invariants

### Risk
The highest applicable risk wins.

The Factory risk policy (`core/policies/risk-policy.yaml`) only knows generic
domains such as `authentication` or `payment`. An organization catalog, a
project or a repository can add its own domain knowledge with `riskRules` in
its `policy` block:

```yaml
policy:
  riskRules:
    - id: identity-is-high
      when: {domains: {containsAny: [identity]}}
      effect: {riskAtLeast: high}
```

A rule matches on `domains` or `changeTypes` (`containsAny`) and its only
effect is `riskAtLeast`: it can raise the effective risk, never lower it.
Matched rules appear in the `PolicyDecision` as `<layer>:<rule id>`, for
example `organization:acme:identity-is-high`.

### Maximum autonomy
The lowest applicable maximum autonomy wins.

```text
authorized = min(requested, factoryMax, profileMax, projectMax, repositoryMax, riskMax)
```

### Required gates
Required gates are additive. A lower layer may add gates but cannot remove a stronger gate.

### Denied actions
Denied actions are additive and override allowed actions.

### Allowed actions
An action is executable only when it is within the effective autonomy level, required capability is available, and no applicable policy denies it.

## Output

Policy resolution produces a `PolicyDecision` containing:

- effective risk,
- authorized autonomy,
- allowed actions,
- denied actions,
- required gates,
- reasons/rules that produced the decision.

This decision is referenced by the execution for auditability.

Each effective decision also produces a fingerprinted
`GovernedExecutionPlan` carrying the effective permissions, gates,
repositories and referenced decision. Policy intent is distinct from
enforcement assurance:
the Runtime persists provider-neutral `EnforcementPoint` artifacts whose status
is `ENFORCED`, `ENFORCEABLE`, `UNAVAILABLE` or `UNVERIFIED`. A strict
enforcement requirement is satisfied only by `ENFORCED`; the other states fail
closed until an active mechanism is proven. A prompt is never enforcement.
