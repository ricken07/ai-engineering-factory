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

Short identifiers (researcher decision A1.4). A new function, class, test or
constant name introduced by the oracle is shorter than `--min-length` but can
still give the fix away. When `--base-dir` is given, every code-shaped
identifier (snake_case, digits, camelCase, UPPER_CASE; plain words are left to
the human provenance review) of the oracle lines that exists nowhere in the base repository and not in the task's
own allowed text (`--allowed`, for example the issue statement) is
oracle-only; a treatment line naming one leaks. Without `--base-dir` the
identifier check is skipped and reported as such.

Bounded revision cycles (A1.4, A1.7). With `--attempt-log FILE`, every check is
recorded (time, SHA-256 of the treatment files, verdict; never oracle content).
Once `--max-attempts` checks are recorded, the tool refuses further checks and
answers ESCALATE (exit status 2): the remaining findings go to independent
escalation instead of further feedback, so that repeated verdicts cannot be
used to probe the oracle. Re-checking unchanged files repeats the last
recorded verdict without consuming an attempt.

Usage: check_leakage.py --treatment FILE... --forbidden FILE... [--base-dir DIR] [--allowed FILE...]
       [--min-length N] [--attempt-log FILE] [--max-attempts N] [--verdict-only] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MIN_LENGTH = 20
DEFAULT_MAX_ATTEMPTS = 3
MIN_IDENTIFIER_LENGTH = 3
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
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


def _text_files(base_dir: Path):
    for path in base_dir.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() in TEXT_SUFFIXES_SKIPPED:
            continue
        try:
            yield path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def _code_shaped(name: str) -> bool:
    """snake_case, digits, camelCase/CamelCase or UPPER_CASE; plain words are left to the human provenance review."""
    return bool(re.search(r"[_0-9]|[A-Z]", name[1:])) or (name.isupper() and len(name) >= MIN_IDENTIFIER_LENGTH)


def identifiers(text: str) -> set[str]:
    return {name for name in IDENTIFIER.findall(text) if len(name) >= MIN_IDENTIFIER_LENGTH}


def oracle_identifiers(forbidden: list[Path], base_dir: Path, allowed_text: list[Path]) -> dict[str, str]:
    """Identifiers introduced by the oracle (absent from the base repository and the allowed text) -> oracle file name."""
    known: set[str] = set()
    for text in _text_files(base_dir):
        known |= identifiers(text)
    for path in allowed_text:
        known |= identifiers(path.read_text(encoding="utf-8", errors="replace"))
    found: dict[str, str] = {}
    for path in forbidden:
        text = path.read_text(encoding="utf-8", errors="replace")
        diff = _is_diff(text)
        for raw in text.splitlines():
            if diff:
                if not raw.startswith("+") or raw.startswith("+++"):
                    continue
                raw = raw[1:]
            for name in {word for word in identifiers(raw) - known if _code_shaped(word)}:
                found.setdefault(name, path.name)
    return found


def check(treatments: list[Path], forbidden: list[Path], base_dir: Path | None = None,
          min_length: int = DEFAULT_MIN_LENGTH, allowed_text: list[Path] | None = None) -> dict[str, Any]:
    allowed = base_lines(base_dir, min_length)
    new_names = oracle_identifiers(forbidden, base_dir, allowed_text or []) if base_dir is not None else None
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
            for word in sorted(identifiers(raw) & set(new_names or ())):
                matches.append({"treatmentLine": number, "oracleFile": new_names[word], "kind": "identifier"})
        files.append({"file": str(path), "matches": len(matches), "positions": matches})
    return {"minLength": min_length, "oracleLinesChecked": len(oracle), "baseLinesExcluded": len(allowed),
            "identifierCheck": "skipped-no-base-dir" if new_names is None else "done",
            "oracleIdentifiersChecked": len(new_names or ()),
            "files": files, "leak": any(item["matches"] for item in files)}


def verdict(report: dict[str, Any]) -> dict[str, Any]:
    """What a treatment author may see: no oracle file name, no oracle line number, no oracle size."""
    return {"verdict": "LEAK" if report["leak"] else "CLEAN", "leak": report["leak"],
            "files": [{"file": item["file"], "treatmentLines": sorted({p["treatmentLine"] for p in item["positions"]})}
                      for item in report["files"]]}


def _fingerprint(treatments: list[Path]) -> dict[str, str]:
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in treatments}


def attempts(log: Path) -> list[dict[str, Any]]:
    return json.loads(log.read_text()) if log.exists() else []


def record_attempt(log: Path, treatments: list[Path], verdict_value: str) -> None:
    entries = attempts(log)
    entries.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "treatment": _fingerprint(treatments), "verdict": verdict_value})
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps(entries, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--treatment", type=Path, nargs="+", required=True, help="treatment files to check")
    parser.add_argument("--forbidden", type=Path, nargs="+", required=True, help="oracle files (gold patch, test patch, tests)")
    parser.add_argument("--base-dir", type=Path, help="repository at the base revision: its lines are not oracle content")
    parser.add_argument("--allowed", type=Path, nargs="*", default=[],
                        help="task text the treatment may quote (issue statement): its identifiers are not oracle-only")
    parser.add_argument("--min-length", type=int, default=DEFAULT_MIN_LENGTH)
    parser.add_argument("--attempt-log", type=Path, help="custodian log of checks for this task (no oracle content)")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--verdict-only", action="store_true",
                        help="author-facing output: verdict and treatment line numbers only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.attempt_log is not None:
        previous = attempts(args.attempt_log)
        if previous and previous[-1]["treatment"] == _fingerprint(args.treatment) and not args.verdict_only:
            pass  # the custodian may re-read the full report of unchanged files
        elif previous and previous[-1]["treatment"] == _fingerprint(args.treatment):
            print(json.dumps({"verdict": previous[-1]["verdict"], "unchanged": True}) if args.json
                  else f"{previous[-1]['verdict']} (unchanged files, attempt not counted)")
            return {"CLEAN": 0, "LEAK": 1}.get(previous[-1]["verdict"], 2)
        elif len(previous) >= args.max_attempts:
            print(json.dumps({"verdict": "ESCALATE", "attempts": len(previous)}) if args.json
                  else f"ESCALATE: {len(previous)} attempt(s) recorded, limit {args.max_attempts}; independent escalation required")
            return 2
    report = check(args.treatment, args.forbidden, args.base_dir, args.min_length, args.allowed)
    if args.attempt_log is not None and (not attempts(args.attempt_log)
                                         or attempts(args.attempt_log)[-1]["treatment"] != _fingerprint(args.treatment)):
        record_attempt(args.attempt_log, args.treatment, "LEAK" if report["leak"] else "CLEAN")
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
            where = ", ".join(f"line {p['treatmentLine']} ~ {p['oracleFile']}:{p.get('oracleLine', 'identifier')}"
                              for p in item["positions"][:10])
            print(f"  {item['file']}: {item['matches']} match(es){' (' + where + ')' if where else ''}")
    return 1 if report["leak"] else 0


if __name__ == "__main__":
    sys.exit(main())
