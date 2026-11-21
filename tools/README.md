# Tooling

The Factory contracts are runtime-agnostic. This directory contains optional maintainer tooling only.

`validate_package.py` validates JSON Schema syntax, YAML parsing, selected manifest schemas and workflow-to-skill references. It is not required by projects at runtime.

## Publish the GitHub wiki

`export_wiki.py` exports tracked Markdown files in `docs/`, plus the organization
catalog guide and YAML template referenced by those pages. It generates `Home`,
`_Sidebar` and `_Footer`, converts relative documentation links to wiki links and
checks page destinations before writing. Fenced code examples remain unchanged.
Local archives and other untracked files are excluded.

Clone the initialized wiki outside the Factory checkout:

```sh
git clone https://github.com/ricken07/ai-engineering-factory.wiki.git ../aief-wiki
python3 tools/export_wiki.py ../aief-wiki
```

Review and publish from the wiki checkout:

```sh
git -C ../aief-wiki diff
git -C ../aief-wiki config user.name "Ricken Bazolo"
git -C ../aief-wiki config user.email "ricken.bazolo@gmail.com"
git -C ../aief-wiki add -- '*.md'
git -C ../aief-wiki commit -m "docs: update Factory wiki"
git -C ../aief-wiki push origin master
```

For subsequent updates, first pull the wiki with `git -C ../aief-wiki pull --ff-only`,
then run the export, review and publish steps again. Edit the source documents
rather than generated pages. The exporter does not commit, push or delete files;
review and remove obsolete generated pages explicitly when renaming source files.
Publication is manual; no automatic synchronization is configured.
