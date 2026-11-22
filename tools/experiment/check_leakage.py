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

Bounded revision cycles (A1.4, A1.7; protocol v2.1 §5.3–5.4). With
`--attempt-log FILE --task ID --register FILE`, every check is recorded (time,
SHA-256 of the treatment files, verdict; never oracle content). Once
`--max-attempts` checks are recorded, a new version of the files gets ESCALATE
(exit status 2) and no verdict. Re-checking unchanged files repeats the last
recorded verdict without consuming an attempt.

Custody is fail-closed. Every write to an attempt or exception log is entered
in a protected reference register, a hash chain over all tasks. A check runs
only when the task's log exists and matches its last register entry (hash and
number of entries) and the chain is intact; otherwise the tool answers
CUSTODY_ERROR (exit status 3) and runs nothing. A log is created only by
`--init-attempt-log`, once per task. Recording the register head outside the
custody area lets a joint reset of a log and the register be detected.

The new register head is printed after every custody write
(`REGISTER_HEAD <task> <kind> <hash>` on stderr) for export to an anchor kept
outside custody; `--anchor FILE` is required with every custody option, and
every head listed there must still be in the chain, otherwise CUSTODY_ERROR.
Custody operations on a register are serialized by an exclusive inter-process
lock (`<register>.lock`). The escalation reviewer is the effective account of
the process (effective uid), never a name taken from `LOGNAME` or `USER`. Unreadable or malformed custody files are
custody errors, never crashes. `--verdict-only` (author-facing) runs only
through the custody circuit, so the attempt limit cannot be bypassed.

Repository-level L1 custody (protocol v2.3.1 §5.1, §5.5). The common L1 bundle
of a repository uses its own circuit (`--task L1-<repository>`): one check
compares the bundle with the union of the oracle files of every task of the
repository (`--forbidden` lists them all), with `--base-dir` at the source
revision R and no `--allowed` text, and yields a single verdict, never one per
task or oracle. Each recorded attempt keeps the SHA-256 of the oracle files
used, so that the check can be reproduced in custody.

Exception check (§5.4 b). The escalation reviewer records the authorization
under their own account: `--authorize-exception --reviewers FILE` checks that
the effective account running it is listed for the task in the protected reviewer list
and enters the authorization (issuer, list hash, file hashes) in the register.
The custodian then runs `--exception-log FILE` once per task, on exactly the
authorized files; the result goes to the exception log only, and the output
and exit status carry no verdict.

Usage: check_leakage.py --treatment FILE... --forbidden FILE... [--base-dir DIR] [--allowed FILE...]
       [--min-length N] [--task ID --register FILE [--attempt-log FILE [--init-attempt-log] [--max-attempts N]]
       [--authorize-exception --reviewers FILE] [--exception-log FILE] [--anchor FILE]] [--verdict-only] [--json]
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import pwd
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry_hash(entry: dict[str, Any]) -> str:
    body = {key: value for key, value in entry.items() if key != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


class CustodyError(Exception):
    """The custody records are missing, truncated or inconsistent: no check runs."""


def _load_json(path: Path, what: str, kind: type = list) -> Any:
    """Read a custody file; any unreadable, malformed or mistyped content is a custody error."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CustodyError(f"{what} is unreadable ({type(error).__name__})") from None
    if not isinstance(value, kind):
        raise CustodyError(f"{what} has an unexpected structure")
    return value


def read_register(register: Path) -> list[dict[str, Any]]:
    """The protected reference register: a hash chain over every custody write, all tasks."""
    if not register.exists():
        return []
    entries = _load_json(register, "reference register")
    previous = None
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get("prev") != previous or entry.get("hash") != _entry_hash(entry):
            raise CustodyError(f"reference register broken at entry {index + 1}")
        previous = entry["hash"]
    return entries


def verify_anchor(register: Path, anchor: Path | None) -> None:
    """Every head recorded outside custody must still be in the register chain (detects a joint reset)."""
    if anchor is None or not anchor.exists():
        raise CustodyError("register anchor is missing")
    try:
        heads = [line.split()[-1] for line in anchor.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError):
        raise CustodyError("register anchor is unreadable") from None
    chain = {entry["hash"] for entry in read_register(register)}
    if any(head not in chain for head in heads):
        raise CustodyError("register does not contain a head recorded in the anchor")


def register_head(register: Path) -> str | None:
    entries = read_register(register)
    return entries[-1]["hash"] if entries else None


def _append_register(register: Path, entry: dict[str, Any]) -> str:
    entries = read_register(register)
    entry = {**entry, "at": _now(), "prev": entries[-1]["hash"] if entries else None}
    entry["hash"] = _entry_hash(entry)
    entries.append(entry)
    register.parent.mkdir(parents=True, exist_ok=True)
    register.write_text(json.dumps(entries, indent=2) + "\n")
    # exported after every write, to be appended to the anchor kept outside custody
    print(f"REGISTER_HEAD {entry['task']} {entry['kind']} {entry['hash']}", file=sys.stderr)
    return entry["hash"]


def _write_log(log: Path, entries: list[dict[str, Any]]) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps(entries, indent=2) + "\n")


def init_attempt_log(log: Path, register: Path, task: str) -> str:
    """Explicit, traceable first use: refused if the task already has custody records."""
    if log.exists() or any(e["task"] == task for e in read_register(register)):
        raise CustodyError(f"task {task} already has custody records; an attempt log is never re-initialized")
    _write_log(log, [])
    return _append_register(register, {"task": task, "kind": "init", "log": log.name, "entries": 0, "logSha256": _sha256(log)})


def attempts(log: Path, register: Path, task: str) -> list[dict[str, Any]]:
    """The task's attempt log, verified against the last register entry for it (fail-closed)."""
    recorded = [e for e in read_register(register) if e["task"] == task and e["kind"] in ("init", "attempt")]
    if not recorded:
        raise CustodyError(f"task {task} has no initialized attempt log (use --init-attempt-log)")
    if not log.exists():
        raise CustodyError(f"attempt log of task {task} is missing")
    entries = _load_json(log, f"attempt log of task {task}")
    if _sha256(log) != recorded[-1]["logSha256"] or len(entries) != recorded[-1]["entries"]:
        raise CustodyError(f"attempt log of task {task} does not match the reference register")
    return entries


def record_attempt(log: Path, register: Path, task: str, treatments: list[Path], verdict_value: str,
                   forbidden: list[Path] | None = None) -> str:
    entries = attempts(log, register, task)
    entry = {"at": _now(), "treatment": _fingerprint(treatments), "verdict": verdict_value}
    if forbidden:  # reproducibility: which oracle files were used (hashes only, custody-side)
        entry["forbiddenSha256"] = sorted(_sha256(path) for path in forbidden)
    entries.append(entry)
    _write_log(log, entries)
    return _append_register(register, {"task": task, "kind": "attempt", "log": log.name,
                                       "entries": len(entries), "logSha256": _sha256(log)})


def effective_account() -> str:
    """The authenticated account of this process (effective uid), never a name taken from LOGNAME or USER."""
    return pwd.getpwuid(os.geteuid()).pw_name


class _RegisterLock:
    """Exclusive inter-process lock: custody operations on one register are serialized."""

    def __init__(self, register: Path):
        self.path = register.with_name(register.name + ".lock")

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a")
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


def authorize_exception(args: argparse.Namespace) -> str:
    """Run by the escalation reviewer under their own account: the authorization lives in the register."""
    issuer = effective_account()
    reviewers = _load_json(args.reviewers, "reviewer list", dict)
    if issuer not in reviewers.get(args.task, []):
        raise CustodyError(f"account {issuer} is not an escalation reviewer of task {args.task}")
    entries = read_register(args.register)
    if not any(e["task"] == args.task and e["kind"] in ("init", "attempt") for e in entries):
        raise CustodyError(f"task {args.task} has no custody records to escalate")
    if any(e["task"] == args.task and e["kind"] in ("exception-authorization", "exception") for e in entries):
        raise CustodyError(f"the exception of task {args.task} has already been authorized")
    return _append_register(args.register, {"task": args.task, "kind": "exception-authorization", "issuer": issuer,
                                            "reviewersSha256": _sha256(args.reviewers),
                                            "treatment": _fingerprint(args.treatment)})


def exception_check(args: argparse.Namespace) -> str:
    """The one check the reviewer authorized; its result goes to the exception log only."""
    entries = [e for e in read_register(args.register) if e["task"] == args.task]
    authorizations = [e for e in entries if e["kind"] == "exception-authorization"]
    if not authorizations:
        raise CustodyError(f"no exception authorization for task {args.task} in the register")
    if any(e["kind"] == "exception" for e in entries) or args.exception_log.exists():
        raise CustodyError(f"the exception check of task {args.task} has already been used")
    if authorizations[-1]["treatment"] != _fingerprint(args.treatment):
        raise CustodyError("treatment files differ from those the exception authorization names")
    report = check(args.treatment, args.forbidden, args.base_dir, args.min_length, args.allowed)
    _write_log(args.exception_log, [{"at": _now(), "task": args.task, "issuer": authorizations[-1]["issuer"],
                                     "authorization": authorizations[-1]["hash"],
                                     "treatment": _fingerprint(args.treatment), "result": report}])
    return _append_register(args.register, {"task": args.task, "kind": "exception", "log": args.exception_log.name,
                                            "authorization": authorizations[-1]["hash"],
                                            "logSha256": _sha256(args.exception_log)})


def _custody_run(args: argparse.Namespace) -> dict[str, Any] | int:
    """Custody operations, run under the register lock; an int is an exit status already reported."""
    verify_anchor(args.register, args.anchor)
    if args.authorize_exception:
        authorize_exception(args)
        print(f"EXCEPTION AUTHORIZED for task {args.task}")
        return 0
    if args.exception_log is not None:
        head = exception_check(args)
        print(f"EXCEPTION CHECK RECORDED in {args.exception_log} for the escalation reviewer only; register head {head}")
        return 0
    if args.init_attempt_log:
        init_attempt_log(args.attempt_log, args.register, args.task)
    previous = attempts(args.attempt_log, args.register, args.task)
    unchanged = bool(previous) and previous[-1]["treatment"] == _fingerprint(args.treatment)
    if unchanged and args.verdict_only:
        print(json.dumps({"verdict": previous[-1]["verdict"], "unchanged": True}) if args.json
              else f"{previous[-1]['verdict']} (unchanged files, attempt not counted)")
        return {"CLEAN": 0, "LEAK": 1}.get(previous[-1]["verdict"], 2)
    if not unchanged and len(previous) >= args.max_attempts:
        print(json.dumps({"verdict": "ESCALATE", "attempts": len(previous)}) if args.json
              else f"ESCALATE: {len(previous)} attempt(s) recorded, limit {args.max_attempts}; independent escalation required")
        return 2
    report = check(args.treatment, args.forbidden, args.base_dir, args.min_length, args.allowed)
    if not unchanged:
        record_attempt(args.attempt_log, args.register, args.task, args.treatment,
                       "LEAK" if report["leak"] else "CLEAN", args.forbidden)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--treatment", type=Path, nargs="+", required=True, help="treatment files to check")
    parser.add_argument("--forbidden", type=Path, nargs="+", required=True, help="oracle files (gold patch, test patch, tests)")
    parser.add_argument("--base-dir", type=Path, help="repository at the base revision: its lines are not oracle content")
    parser.add_argument("--allowed", type=Path, nargs="*", default=[],
                        help="task text the treatment may quote (issue statement): its identifiers are not oracle-only")
    parser.add_argument("--min-length", type=int, default=DEFAULT_MIN_LENGTH)
    parser.add_argument("--task", help="task identifier (required with any custody option)")
    parser.add_argument("--register", type=Path, help="protected reference register of custody writes")
    parser.add_argument("--attempt-log", type=Path, help="custodian log of checks for this task (no oracle content)")
    parser.add_argument("--init-attempt-log", action="store_true", help="create the task's attempt log (first use only)")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--exception-log", type=Path, help="run the single reviewer-approved exception check")
    parser.add_argument("--authorize-exception", action="store_true",
                        help="escalation reviewer: record in the register the exception for these exact files")
    parser.add_argument("--reviewers", type=Path, help="protected list {task: [reviewer accounts]}")
    parser.add_argument("--anchor", type=Path,
                        help="register heads recorded outside custody, one per line (required with custody options)")
    parser.add_argument("--verdict-only", action="store_true",
                        help="author-facing output: verdict and treatment line numbers only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    custody = args.attempt_log is not None or args.exception_log is not None or args.authorize_exception
    if custody and (not args.task or args.register is None or args.anchor is None):
        parser.error("custody options need --task, --register and --anchor")
    if args.authorize_exception and args.reviewers is None:
        parser.error("--authorize-exception needs --reviewers")
    if args.verdict_only and args.attempt_log is None:
        parser.error("--verdict-only is author-facing and runs only through the custody circuit (--attempt-log)")
    try:
        if custody:
            with _RegisterLock(args.register):
                outcome = _custody_run(args)
            if isinstance(outcome, int):
                return outcome
            report = outcome
        else:
            report = check(args.treatment, args.forbidden, args.base_dir, args.min_length, args.allowed)
    except CustodyError as error:
        print(f"CUSTODY_ERROR: {error}; no check was run, escalate", file=sys.stderr)
        return 3
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
