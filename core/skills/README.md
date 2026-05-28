# Core Skills

A skill is a reusable capability contract. Core skills must remain stack/provider/agent agnostic.

`Workflow = orchestration`  
`Skill = capability`

A skill may require an abstract external capability such as `source-control`; it must not name the provider in Core.

Knowledge lifecycle deliberately separates proposal from durable mutation:

- `promote-memory` evaluates verified task evidence and proposes candidates;
- `record-project-knowledge` records only an approved candidate whose content and target still match the approval.
