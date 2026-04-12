# 06 — Context and Memory

## Mandatory bootstrap context

Always resolve:

- `.ai/project.yaml`,
- `.ai/repository-map.yaml`,
- active task,
- selected workflow,
- applicable Factory policies.

## Conditional context

Load only when relevant:

- architecture,
- domain model,
- conventions,
- ADRs,
- repository-specific docs,
- external knowledge-base content,
- selected technology profiles.

## Progressive loading

```text
Task
 ↓
Project identity
 ↓
Repository map
 ↓
Impact analysis
 ↓
Relevant repositories
 ↓
Relevant context + profiles
```

## Memory tiers

### Session memory
Ephemeral; owned by the current agent runtime.

### Task memory
Bounded to a specific task/execution. It may support handoff but is not automatically a durable project fact.

### Project memory
Durable, project-wide knowledge. Promotion requires explicit validation under the memory policy.

### Decision records
Durable approved decisions (e.g. ADRs). They are stronger than informal shared memory.

## Safety rules

Never persist credentials, tokens, private keys or secrets in project memory. Do not promote transient observations as durable facts without validation.
