# Payment module conventions

- Provider implementations use the `ProviderClient` suffix.
- Provider-specific statuses and errors are normalized before crossing the application boundary.
- Payment orchestration must not depend directly on a concrete provider adapter.
