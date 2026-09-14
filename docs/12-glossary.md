# 12 — Glossary

- **Core**: provider/stack/agent-agnostic Factory layer.
- **Profile**: reusable technology/practice extension.
- **Integration**: external provider mapping to abstract Factory capabilities.
- **Adapter**: agent-runtime mapping.
- **Task**: unit of engineering work.
- **Workflow**: process orchestration.
- **Skill**: reusable capability.
- **Policy**: permission/obligation constraint.
- **Standard**: quality expectation.
- **Gate**: required checkpoint.
- **Execution**: runtime instance of a workflow for a task.
- **GovernedExecutionPlan**: fingerprinted binding of an Execution, Workflow,
  PolicyDecision and execution requirements.
- **EnforcementPoint**: execution-specific record of a decision, neutral
  mechanism, assurance status and supporting evidence.
- **Enforcement assurance**: `ENFORCED`, `ENFORCEABLE`, `UNAVAILABLE` or
  `UNVERIFIED`; only `ENFORCED` satisfies a strict requirement.
- **Actor assurance**: provenance strength of an identity: `DECLARED`,
  `OBSERVED`, `TRUSTED` or `UNVERIFIED`.
- **Review independence**: `INDEPENDENT`, `NOT_INDEPENDENT`, `UNVERIFIED` or
  `NOT_REQUIRED`, derived from Runtime-held identities rather than review text.
- **EvidenceBundle**: fingerprinted index of evidence references, governance,
  identities, verification, gates, metrics and reproducibility metadata.
- **Artifact**: output produced during execution.
- **Handoff**: portable execution state between agents/sessions.
- **Workspace**: local project/system view where an agent operates.
- **Project memory**: durable validated project-wide knowledge.
