# Module conventions

- Adapters to external services use one explicit suffix per kind of adapter.
- External statuses and errors are normalized before crossing the application boundary.
- Domain logic must not depend directly on a concrete external adapter.
