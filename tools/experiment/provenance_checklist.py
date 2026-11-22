#!/usr/bin/env python3
"""Deterministic provenance checklist for the delayed self-review of a treatment.

Protocol v2.3.1 §5.2: every file path, module, symbol, command and test target
named in a treatment artifact (L1 bundle, L2 plan, L2 verification) is listed
and classified against the author's allowed sources only:

- `found`: exists in the base repository (`--base-dir`, the task's base
  revision, or R for an L1 bundle) or occurs in the allowed task text
  (`--allowed`, the issue statement; none for an L1 bundle);
- `absent`: exists in neither;
- `unverifiable`: cannot be decided statically (an attribute of a module that
  exists, an external tool, a behaviour).

Where it was found is a fact, not a provenance: the author fills in, for every
entry, the allowed source and the location it was taken from, and removes
entries without one. The tool never reads an oracle and never decides what to
keep; it is a deterministic validation tool permitted by decision A1.2.

Usage: provenance_checklist.py --treatment FILE... --base-dir DIR [--allowed FILE...] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SKIPPED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".pyc", ".so", ".bin", ".npy", ".pkl"}
EXTERNAL_COMMANDS = {"python", "python3", "pytest", "pip", "make", "tox", "nox", "git", "flake8", "ruff", "mypy",
                     "black", "isort", "sh", "bash", "uv", "conda", "pre-commit"}
PATH = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]*|[\w-]+\.(?:py|pyx|pxd|cfg|toml|ini|rst|md|txt|yml|yaml|c|h|cpp))(?![\w/])")
TEST_TARGET = re.compile(r"((?:[\w.-]+/)*[\w.-]+\.py)::([\w:\[\]-]+)")
DOTTED = re.compile(r"(?<![\w.])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)(?![\w(]*\.\w)")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _code_shaped(name: str) -> bool:
    return len(name) >= 3 and (bool(re.search(r"[_0-9]|[A-Z]", name[1:])) or name.isupper())


class Repository:
    """Static view of the base repository: file paths and the identifiers each file contains."""

    def __init__(self, root: Path):
        self.root = root
        self.files: set[str] = set()
        self.dirs: set[str] = set()
        self.words: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if ".git" in path.relative_to(root).parts:
                continue
            rel = path.relative_to(root).as_posix()
            if path.is_dir():
                self.dirs.add(rel)
                continue
            self.files.add(rel)
            if path.suffix.lower() in SKIPPED_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for word in IDENTIFIER.findall(text):
                self.words.setdefault(word, rel)

    def path(self, ref: str) -> str | None:
        ref = ref.strip().lstrip("./").rstrip("/")
        return ref if ref in self.files or ref in self.dirs else None

    def module(self, dotted: str) -> tuple[str | None, list[str]]:
        """Longest importable prefix of a dotted name -> (its file, remaining attribute names)."""
        parts = dotted.split(".")
        for k in range(len(parts), 0, -1):
            base = "/".join(parts[:k])
            for root in ("", "src/", "lib/"):
                for candidate in (f"{root}{base}.py", f"{root}{base}/__init__.py", f"{root}{base}.pyx"):
                    if candidate in self.files:
                        return candidate, parts[k:]
        return None, parts

    def defines(self, file: str, name: str) -> bool:
        try:
            text = (self.root / file).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return False
        return re.search(rf"^\s*(?:async\s+def|def|class)\s+{re.escape(name)}\b|^\s*{re.escape(name)}\s*[:=]", text, re.M) is not None


def _entry(kind: str, value: str, file: Path, line: int, status: str, found_in: str | None) -> dict[str, Any]:
    return {"kind": kind, "entry": value, "file": str(file), "line": line, "status": status, "foundIn": found_in,
            "provenance": None, "location": None}


def classify(kind: str, value: str, repo: Repository, allowed: str) -> tuple[str, str | None]:
    in_issue = "issue text" if value in allowed else None
    if kind == "path":
        return ("found", repo.path(value)) if repo.path(value) else (("found", in_issue) if in_issue else ("absent", None))
    if kind == "test target":
        path, _, name = value.partition("::")
        func = re.split(r"[:\[]", name)[0]
        if not repo.path(path):
            return ("found", in_issue) if in_issue else ("absent", None)
        return ("found", path) if repo.defines(path, func) else ("absent", None)
    if kind == "module":
        file, rest = repo.module(value)
        if file and not rest:
            return "found", file
        if file and len(rest) == 1 and repo.defines(file, rest[0]):
            return "found", file
        if file:
            return "unverifiable", file
        return ("found", in_issue) if in_issue else ("absent", None)
    if kind == "symbol":
        if value in repo.words:
            return "found", repo.words[value]
        return ("found", in_issue) if in_issue else ("absent", None)
    if kind == "command":
        program = value.split()[0]
        if repo.path(program):
            return "found", repo.path(program)
        return "unverifiable", None
    raise ValueError(kind)


def _clean_target(value: str) -> str:
    while value.endswith("]") and value.count("]") > value.count("["):
        value = value[:-1]
    return value.rstrip(".,;:")


def _text_entries(path: Path, text: str) -> list[tuple[str, str, int]]:
    found: list[tuple[str, str, int]] = []
    for number, line in enumerate(text.splitlines(), 1):
        targets = {_clean_target(m.group(0)) for m in TEST_TARGET.finditer(line)}
        found += [("test target", t, number) for t in sorted(targets)]
        stripped = TEST_TARGET.sub(" ", line)
        paths = {m.group(1).rstrip(".,;:") for m in PATH.finditer(stripped)
                 if not m.group(1).startswith(("http", "www.")) and "//" not in m.group(1)}
        paths.discard("")
        found += [("path", p, number) for p in sorted(paths)]
        for dotted in sorted(set(DOTTED.findall(stripped))):
            if dotted in paths or any(dotted in p for p in paths) or re.fullmatch(r"[\w-]+\.(py|md|rst|txt|cfg|toml|ini|yml|yaml)", dotted):
                continue
            found.append(("module", dotted, number))
        for span in CODE_SPAN.findall(stripped):
            for word in sorted(set(IDENTIFIER.findall(span))):
                if _code_shaped(word) and not any(word in d for k, d, n in found if n == number and k != "symbol"):
                    found.append(("symbol", word, number))
    return found


def _verification_entries(path: Path, text: str) -> list[tuple[str, str, int]]:
    found = _text_entries(path, text)
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return found
    lines = text.splitlines()
    for command in data.get("commands") or []:
        argv = [str(item) for item in (command.get("command") or [])]
        if not argv:
            continue
        joined = " ".join(argv)
        line = next((i for i, l in enumerate(lines, 1) if str(command.get("id")) in l), 0)
        found.append(("command", joined, line))
        if argv[0] in ("python", "python3") and len(argv) > 2 and argv[1] == "-m":
            found.append(("module", argv[2], line))
    return found


def checklist(treatments: list[Path], base_dir: Path, allowed: list[Path]) -> dict[str, Any]:
    repo = Repository(base_dir)
    allowed_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in allowed)
    entries = []
    for path in treatments:
        text = path.read_text(encoding="utf-8", errors="replace")
        raw = _verification_entries(path, text) if path.suffix in (".yaml", ".yml") else _text_entries(path, text)
        seen = set()
        for kind, value, line in raw:
            if (kind, value, line) in seen:
                continue
            seen.add((kind, value, line))
            status, where = classify(kind, value, repo, allowed_text)
            entries.append(_entry(kind, value, path, line, status, where))
    entries.sort(key=lambda e: (e["file"], e["line"], e["kind"], e["entry"]))
    summary = {status: sum(e["status"] == status for e in entries) for status in ("found", "absent", "unverifiable")}
    return {"treatment": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in treatments},
            "allowed": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in allowed},
            "baseDir": str(base_dir), "summary": summary, "entries": entries}


def markdown(result: dict[str, Any]) -> str:
    rows = ["# Provenance checklist", "",
            "Fill in, for every entry, the allowed source (issue text, base repository, L1 bundle) and the location it was "
            "taken from. Remove entries without an authorized provenance. `found` is not a provenance.", "",
            f"Base: `{result['baseDir']}` · found {result['summary']['found']} · absent {result['summary']['absent']} · "
            f"unverifiable {result['summary']['unverifiable']}", "",
            "| File:line | Kind | Entry | Status | Found in | Authorized provenance | Location |", "|---|---|---|---|---|---|---|"]
    for e in result["entries"]:
        rows.append(f"| `{Path(e['file']).name}:{e['line']}` | {e['kind']} | `{e['entry']}` | {e['status']} | "
                    f"{e['foundIn'] or '—'} | | |")
    rows += ["", "Treatment SHA-256: " + ", ".join(f"`{Path(k).name}` {v}" for k, v in result["treatment"].items())]
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--treatment", type=Path, nargs="+", required=True)
    parser.add_argument("--base-dir", type=Path, required=True, help="repository at the base revision (R for an L1 bundle)")
    parser.add_argument("--allowed", type=Path, nargs="*", default=[], help="allowed task text (issue statement)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = checklist(args.treatment, args.base_dir, args.allowed)
    print(json.dumps(result, indent=2) if args.json else markdown(result), end="" if not args.json else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
