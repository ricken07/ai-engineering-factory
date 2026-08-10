# Core Workflows

V0.1 includes:

- `analyze-task`
- `implement-task`
- `review-change`
- `fix-bug`
- `refactor-code`
- `add-tests`
- `update-documentation`

The first three are the minimum pilot set; the others are composed from the same Core skills.

`import-backlog` (added in 1.14.0) is not driven by the generic Execution engine above — its two Skills document the agentic contract, but `aief backlog import|preview|apply` (see `docs/17-task-tracking-provider-runtime.md`) drives it directly, the same way Task Tracking drives external task creation outside of any Workflow.
