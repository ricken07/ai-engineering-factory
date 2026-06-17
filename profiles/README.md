# Profiles

Profiles extend the agnostic Core with reusable technology/practice knowledge. They are composable. Project-specific rules do not belong here.

Examples in V0.1 are reference profiles and may be refined independently of Core contracts.

Commands use argv arrays and are executed without a shell. The shared Runtime resolves them only for impacted repositories whose discovery files match. See `docs/15-profile-runtime.md`.
