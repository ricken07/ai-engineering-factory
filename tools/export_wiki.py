#!/usr/bin/env python3
"""Export tracked documentation to a GitHub wiki checkout; never commit or push."""
import argparse
from pathlib import Path
import re
import subprocess
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WIKI = 'https://github.com/ricken07/ai-engineering-factory/wiki'
LINK = re.compile(r'(!?\[[^\]\n]*\]\()([^\s)]+)(\))')
EXCLUDED = {
    'RESEARCH-BASELINE-FREEZE-REPORT.md', 'RESEARCH-BASELINE-HARDENING-AUDIT.md',
    'RESEARCH-BASELINE-HARDENING-REPORT.md', 'RESEARCH-READINESS-DESIGN.md',
    'RESEARCH-READINESS-REPORT.md', 'SECURITY.md', 'understand.md',
    'FINAL-RESEARCH-BASELINE-AUDIT.md', 'CURRENT-STATE-AUDIT.md',
}


def export(destination):
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('Use a separate wiki checkout outside the source repository.')
    tracked = subprocess.check_output(
        ['git', '-C', str(ROOT), 'ls-files', '-z'], text=True
    ).split('\0')
    sources = sorted(ROOT / p for p in tracked if p.startswith('docs/') and p.endswith('.md'))
    sources += [ROOT / 'organization/README.md', ROOT / 'templates/organization/catalog.yaml']
    assert all(p.name not in EXCLUDED and str(p.relative_to(ROOT)) in tracked for p in sources)
    pages = {p.resolve(): p.stem for p in sources}
    pages[(ROOT / 'organization/README.md').resolve()] = 'Organization-Catalog'
    pages[(ROOT / 'templates/organization/catalog.yaml').resolve()] = 'Organization-Catalog-Template'
    assert len(set(pages.values())) == len(pages), 'Duplicate wiki page names'

    def convert(target, source):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return target
        path = (source.parent / unquote(parsed.path)).resolve()
        if path not in pages:
            raise ValueError(f'Unpublished link in {source}: {target}')
        return WIKI + '/' + quote(pages[path]) + ('#' + parsed.fragment if parsed.fragment else '')

    def rewrite(content, source):
        # Preserve fenced examples verbatim.
        lines, fence = [], None
        for line in content.splitlines(keepends=True):
            marker = re.match(r'^\s*(`{3,}|~{3,})', line)
            if marker:
                token = marker[1]
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = None
                lines.append(line)
                continue
            if fence is None:
                line = LINK.sub(lambda m: m[1] + convert(m[2], source) + m[3], line)
            lines.append(line)
        return ''.join(lines)

    generated = {}
    for source in sources:
        content = source.read_text()
        if source.suffix == '.yaml':
            content = '# Organization Catalog Template\n\nCopy and adapt this template for your organization.\n\n```yaml\n' + content + '```\n'
        else:
            content = rewrite(content, source)
        generated[pages[source.resolve()] + '.md'] = content

    def link(title, slug):
        return f'[{title}]({WIKI}/{slug})'

    generated['Home.md'] = '''# AI Engineering Factory

AIEF turns developer intent into contextualized, governed and traceable engineering workflows executed by coding agents.

## Start here

| Your goal | Read first |
| --- | --- |
| Understand AIEF | [Reference architecture](WIKI/00-factory-reference-architecture) |
| Install the Factory | [Installation guide](WIKI/22-project-installation-guide) |
| Run your first workflow | [First steps](WIKI/23-first-steps) |
| Configure governance | [Policy resolution](WIKI/05-policy-resolution) |
| Extend the Factory | [Extension model](WIKI/07-extension-model) |
| Troubleshoot an execution | [Execution log](WIKI/26-task-execution-log) |

## Explore the documentation

- [Documentation index](WIKI/INDEX): browse all guides by topic.
- [Reading guide](WIKI/00-HOW-TO-USE-THESE-DOCS): choose a path for your role.
- [Glossary](WIKI/12-glossary): understand the core vocabulary.
- [Organization catalog](WIKI/Organization-Catalog) and [YAML template](WIKI/Organization-Catalog-Template).

## Contributing to these pages

The source documentation lives in `docs/` in the Factory repository. Update the source files, then regenerate this wiki with `tools/export_wiki.py`. The organization guide and template are included so their links remain usable here.

Local research archives are not part of this wiki.
'''.replace('WIKI/', WIKI + '/')
    sidebar = [link('Home', 'Home'), link('Documentation index', 'INDEX'), link('Reading guide', '00-HOW-TO-USE-THESE-DOCS'), '']
    seen = set()
    section = None
    for line in (ROOT / 'docs/INDEX.md').read_text().splitlines():
        if line.startswith('## '):
            section = line[3:]
        if line.startswith('| ['):
            match = re.search(r'\[([^]]+)\]\(([^)]+)\)', line)
            if match and match[2] not in seen:
                if section:
                    sidebar += ['', '**' + section + '**', '']
                    section = None
                seen.add(match[2])
                sidebar.append('- ' + link(match[1], Path(match[2]).stem))
    sidebar += ['', '**Additional references**', '', '- ' + link('Organization catalog', 'Organization-Catalog'), '- ' + link('Catalog template', 'Organization-Catalog-Template')]
    generated['_Sidebar.md'] = '\n'.join(sidebar) + '\n'
    generated['_Footer.md'] = link('Home', 'Home') + ' · ' + link('Documentation index', 'INDEX') + '\n'
    # Validate all wiki page destinations before writing anything.
    for name, content in generated.items():
        for target in re.findall(re.escape(WIKI) + r'/([^\s)#]+)', content):
            assert unquote(target) + '.md' in generated, (name, target)
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in generated.items():
        (destination / name).write_text(content)
    print(f'Exported {len(sources)} source documents and 3 navigation pages to {destination}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, help='Separate wiki checkout directory')
    export(parser.parse_args().destination)
