from pathlib import Path
import re
from urllib.parse import unquote


ROOT = Path(__file__).parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def test_internal_markdown_links_resolve():
    broken: list[str] = []
    for document in sorted(ROOT.rglob("*.md")):
        if any(part in {".git", ".venv", "build"} for part in document.parts):
            continue
        for raw in LINK.findall(document.read_text(encoding="utf-8")):
            target = raw.strip().strip("<>").split()[0]
            if not target or target.startswith(("#", "/", "mailto:")) or "://" in target:
                continue
            relative = unquote(target.split("#", 1)[0])
            if relative and not (document.parent / relative).resolve().exists():
                broken.append(f"{document.relative_to(ROOT)} -> {target}")
    assert broken == [], "broken internal Markdown links:\n" + "\n".join(broken)
