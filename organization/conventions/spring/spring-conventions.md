# Spring conventions

- Use constructor injection for required dependencies.
- Keep transaction boundaries explicit and located at application-service boundaries.
- Do not expose persistence entities through public APIs.
- Keep framework annotations out of domain objects when the project architecture permits it.
