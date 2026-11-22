#!/usr/bin/env python3
"""Check that treatment files carry no oracle content, without revealing it.

The L1 context, L2 plan and L2 verification of a task must be prepared blind
to the hidden oracle: the gold patch and the `FAIL_TO_PASS`/`PASS_TO_PASS`
tests (RC2 §7.4, §8). This check runs unattended in the evaluator environment,
where the oracle files live, and compares every treatment file with them.

Forbidden content is the set of significant lines of the oracle files:
- for a unified diff (gold or test patch), the lines it adds (`+`), not its context;
- for any other file, every line.
A treatment line leaks when it contains an oracle line, after whitespace
normalization (an oracle line quoted inside a sentence still counts); lines shorter than
`--min-length` characters are ignored (blank lines, braces, keywords). A line
already present in the repository at the base revision (`--base-dir`) is not
oracle content: the treatment may legitimately quote existing code.

The report never repeats a forbidden line: it gives, per treatment file, the
number of matches and their positions (treatment line, oracle file name and
line number), so that whoever reads it learns where a leak is, not what the
oracle contains. The full report stays in the evaluator area; treatment
authors receive only `--verdict-only` output: CLEAN or LEAK and the treatment
line numbers, without oracle file names or line numbers. Exit status 1 when
any treatment file matches.

Usage: check_leakage.py --treatment FILE... --forbidden FILE... [--base-dir DIR] [--min-length N] [--verdict-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_MIN_LENGTH = 20
TEXT_SUFFIXES_SKIPPED = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".pyc", ".so", ".bin"}


def normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _is_diff(text: str) -> bool:
    return text.startswith(("diff --git", "--- ", "Index: ")) or "\n+++ " in text


def oracle_lines(path: Path, min_length: int) -> dict[str, int]:
    """Significant oracle lines of a file -> their first line number in that file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    diff = _is_diff(text)
    lines: dict[str, int] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        if diff:
            if not raw.startswith("+") or raw.startswith("+++"):
                continue
            raw = raw[1:]
        line = normalize(raw)
        if len(line) >= min_length:
            lines.setdefault(line, number)
    return lines


def base_lines(base_dir: Path | None, min_length: int) -> set[str]:
    """Significant lines already present in the repository at the base revision."""
    if base_dir is None:
        return set()
    present: set[str] = set()
    for path in base_dir.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() in TEXT_SUFFIXES_SKIPPED:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        present.update(line for line in map(normalize, text.splitlines()) if len(line) >= min_length)
    return present


def check(treatments: list[Path], forbidden: list[Path], base_dir: Path | None = None,
          min_length: int = DEFAULT_MIN_LENGTH) -> dict[str, Any]:
    allowed = base_lines(base_dir, min_length)
    oracle: dict[str, tuple[str, int]] = {}
    for path in forbidden:
        for line, number in oracle_lines(path, min_length).items():
            if line not in allowed:
                oracle.setdefault(line, (path.name, number))
    files = []
    for path in treatments:
        matches = []
        for number, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            line = normalize(raw)
            for content, (name, oracle_number) in oracle.items():
                if content in line:
                    matches.append({"treatmentLine": number, "oracleFile": name, "oracleLine": oracle_number})
        files.append({"file": str(path), "matches": len(matches), "positions": matches})
    return {"minLength": min_length, "oracleLinesChecked": len(oracle), "baseLinesExcluded": len(allowed),
            "files": files, "leak": any(item["matches"] for item in files)}


def verdict(report: dict[str, Any]) -> dict[str, Any]:
    """What a treatment author may see: no oracle file name, no oracle line number, no oracle size."""
    return {"verdict": "LEAK" if report["leak"] else "CLEAN", "leak": report["leak"],
            "files": [{"file": item["file"], "treatmentLines": sorted({p["treatmentLine"] for p in item["positions"]})}
                      for item in report["files"]]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--treatment", type=Path, nargs="+", required=True, help="treatment files to check")
    parser.add_argument("--forbidden", type=Path, nargs="+", required=True, help="oracle files (gold patch, test patch, tests)")
    parser.add_argument("--base-dir", type=Path, help="repository at the base revision: its lines are not oracle content")
    parser.add_argument("--min-length", type=int, default=DEFAULT_MIN_LENGTH)
    parser.add_argument("--verdict-only", action="store_true",
                        help="author-facing output: verdict and treatment line numbers only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.treatment, args.forbidden, args.base_dir, args.min_length)
    if args.verdict_only:
        report = verdict(report)
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.verdict_only:
        print(report["verdict"])
        for item in report["files"]:
            print(f"  {item['file']}: lines {item['treatmentLines'] or 'none'}")
    else:
        print(f"{'LEAK' if report['leak'] else 'CLEAN'}: {report['oracleLinesChecked']} oracle line(s) checked")
        for item in report["files"]:
            where = ", ".join(f"line {p['treatmentLine']} ~ {p['oracleFile']}:{p['oracleLine']}" for p in item["positions"][:10])
            print(f"  {item['file']}: {item['matches']} match(es){' (' + where + ')' if where else ''}")
    return 1 if report["leak"] else 0


if __name__ == "__main__":
    sys.exit(main())
