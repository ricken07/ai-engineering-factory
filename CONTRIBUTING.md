# Contributing

Contributions are welcome. Please discuss a significant change in an issue or GitHub Discussion before opening a pull request.

## Development setup

Requirements: Python 3.11 or newer.

```bash
git clone <REPOSITORY_URL>
cd ai-engineering-factory
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

The Core must remain independent of coding agents, providers and technology stacks. Changes to schemas, workflow phase order, policy resolution or adapter mappings require particular care and accompanying tests.

Before submitting a pull request:

- explain the problem and the proposed change;
- include or update tests;
- update documentation and schemas when applicable;
- confirm that Core agnosticism is preserved;
- describe compatibility and security implications.

## Extension points

Use the existing examples when adding a Core Skill, Workflow, Policy, Profile, Organization Catalog, Integration or Agent Adapter. Extensions should reuse Core contracts instead of duplicating their behavior.
