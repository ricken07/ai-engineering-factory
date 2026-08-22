# Sample organization guidelines

This document illustrates a second, independent organization catalog composed
on top of `factory-default`. It carries no real organizational content.

- Replace this document with your own organization's architecture guidance.
- A project selects this catalog only if it explicitly opts in
  (`organizationCatalogs: [sample-organization@1.0.0]`); nothing in the Core
  or in any Profile references it.
- This demonstrates that a project may select more than one
  `OrganizationCatalog` at once (`extends: [factory-default@1.0.0]`), without
  requiring any external or private dependency.
