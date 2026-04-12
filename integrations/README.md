# Integration Model

Core workflows request abstract capabilities. Integrations map those capabilities to providers or MCP/tool surfaces.

## Standard capabilities

### source-control
Operations: inspect-status, create-branch, commit, push, get-diff, submit-change, get-change, comment-change, merge.

### task-provider
Operations: get-task, search-task, comment-task, update-task, link-change.

### knowledge-base
Operations: search-knowledge, get-document, update-document.

### continuous-integration
Operations: get-pipeline, run-validation, get-validation-result.

An integration manifest declares capability mappings. Actual MCP tool names remain deployment/runtime configuration and are hints, not Core contracts.
