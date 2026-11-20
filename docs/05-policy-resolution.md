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

### Repository critical domains
A repository lists the domains it makes critical in `criticalDomains`. When the
impact analysis names the repository, the Runtime adds these domains to the
observed domains before evaluating risk.

```yaml
criticalDomains:
  - payment                              # every task touching the repository
  - domain: authentication               # only tasks touching these paths
    paths: [src/main/java/**/security/, "**/*Token*.java"]
```

Paths are globs relative to the repository path (`*`, `?`, `**`); a match also
covers what lies below it. `analyze-impact` lists the paths it expects to modify
in `details.paths`, relative to the project root. A scoped domain applies when:

- one of these paths matches a glob, or is a directory containing the scoped
  area (for example `app/src` for `src/security/`);
- or the analysis lists no path inside the repository: without paths the Runtime
  cannot show the area is untouched, so it fails closed.

A later reassessment (`create-plan`) without `paths` keeps the paths of the
analysis. Inherited domains appear in `matchedRules` as
`repository:<id>:criticalDomains:<domain>`, with a `:path` or `:no-path` suffix
for scoped entries. Scoping refines the repository layer's own constraint; it
does not weaken any other layer, and the Factory and catalog risk rules still
apply to the domains the analysis declares.

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

### Proposed changes

When the governed plan denies `modify-local-files` but allows
`propose-change` (L1), the implementation phase is prepared with
`action: propose-change`. The Runtime fingerprints every Git root of the
execution workspace (HEAD, status and diff, outside the Runtime state store)
when the phase starts, and `complete-phase` rejects the output if the
workspace changed. The agent writes its change as unified diffs inside the
execution directory and lists them in `details.proposal.patches` as
`{repository, path}`; the Runtime checks that each one applies.

Before submitting, the agent may ask the Runtime for a dry run:
`aief execution check-proposal <id> --output <draft> --owner <owner>`. The
Runtime exports the execution revision (`git archive HEAD`) into a disposable
directory, without writing into the repository's `.git`, applies the patches
there, runs the repositories' profile validation commands in it,
returns exit codes and output tails, then deletes the copy. The execution
workspace is never modified, so the denial of `modify-local-files` holds; the
agent sees mechanical failures (compilation, formatting) before proposing.
Each run is recorded as a `proposal-check-NNN.yaml` artifact and a
`proposal.checked` event. It is feedback, not validation evidence: only the
validation phase, on the applied proposal, produces evidence.

The proposal then holds every later phase behind the `apply-proposal` policy
gate. When a human approves it (`aief execution approve-policy <id>
apply-proposal`), the Runtime verifies that neither the workspace nor the
patches changed and applies them itself. Validation below L2 is allowed only
for such an applied proposal: the human approved the change, and the Runtime,
not the agent, executes the profile commands. Both the denial and the
application are recorded as enforcement points.

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
