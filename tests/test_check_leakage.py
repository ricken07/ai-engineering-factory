"""Oracle-safe leakage check (tools/experiment/check_leakage.py)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("check_leakage", ROOT / "tools" / "experiment" / "check_leakage.py")
tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

GOLD_PATCH = """diff --git a/pkg/units.py b/pkg/units.py
--- a/pkg/units.py
+++ b/pkg/units.py
@@ -1,3 +1,4 @@
 def convert(value, unit):
-    return value
+    return value * FACTORS[unit]  # the hidden fix
+    # short
"""
TEST_FILE = "def test_convert_uses_the_factor_table():\n    assert convert(2, 'km') == 2000\n"
SECRET = "return value * FACTORS[unit]  # the hidden fix"


def files(tmp_path: Path, plan_text: str) -> tuple[Path, Path, Path]:
    oracle = tmp_path / "oracle"; oracle.mkdir()
    (oracle / "gold.patch").write_text(GOLD_PATCH); (oracle / "test_units.py").write_text(TEST_FILE)
    treatment = tmp_path / "treatment"; treatment.mkdir()
    (treatment / "plan.md").write_text(plan_text)
    return treatment / "plan.md", oracle / "gold.patch", oracle / "test_units.py"


def test_clean_treatment_passes(tmp_path: Path):
    plan, gold, tests = files(tmp_path, "# Plan\n1. Make convert honour the unit argument.\n")
    report = tool.check([plan], [gold, tests])
    assert report["leak"] is False and report["files"][0]["matches"] == 0


def test_a_leaked_patch_line_or_test_line_is_found_but_never_repeated(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, f"# Plan\n1. Write   {SECRET}\n2. assert convert(2, 'km') == 2000\n")
    report = tool.check([plan], [gold, tests])
    assert report["leak"] is True and report["files"][0]["matches"] == 2
    positions = {(item["treatmentLine"], item["oracleFile"]) for item in report["files"][0]["positions"]}
    assert positions == {(2, "gold.patch"), (3, "test_units.py")}
    assert tool.main(["--treatment", str(plan), "--forbidden", str(gold), str(tests), "--json"]) == 1
    output = capsys.readouterr().out
    assert "hidden fix" not in output and "2000" not in output and json.loads(output)["leak"] is True


def test_diff_context_and_short_lines_are_not_oracle_content(tmp_path: Path):
    plan, gold, tests = files(tmp_path, "def convert(value, unit):\n    # short\n")
    assert tool.check([plan], [gold])["leak"] is False


def test_lines_present_at_the_base_revision_are_allowed(tmp_path: Path):
    plan, gold, tests = files(tmp_path, "assert convert(2, 'km') == 2000\n")
    base = tmp_path / "repo"; base.mkdir(); (base / "docs.md").write_text("Example: assert convert(2, 'km') == 2000\nassert convert(2, 'km') == 2000\n")
    assert tool.check([plan], [tests])["leak"] is True
    assert tool.check([plan], [tests], base_dir=base)["leak"] is False


def test_the_author_facing_verdict_names_no_oracle_file_or_line(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, f"# Plan\n1. Write {SECRET}\n")
    output = tool.verdict(tool.check([plan], [gold, tests]))
    assert output == {"verdict": "LEAK", "leak": True, "files": [{"file": str(plan), "treatmentLines": [2]}]}
    assert tool.main(custody(tmp_path, plan, gold, tests, "--init-attempt-log")) == 1
    text = capsys.readouterr().out
    assert "gold" not in text and "hidden fix" not in text and "LEAK" in text


def test_a_new_short_identifier_from_the_oracle_leaks_but_existing_or_issue_names_do_not(tmp_path: Path):
    base = tmp_path / "base"; (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "units.py").write_text("def convert(value, unit):\n    return value\n")
    issue = tmp_path / "issue.txt"; issue.write_text("convert ignores the unit argument")
    plan, gold, tests = files(tmp_path, "# Plan\n1. Add FACTORS.\n2. Change convert for the unit.\n")
    report = tool.check([plan], [gold, tests], base, allowed_text=[issue])
    positions = report["files"][0]["positions"]
    assert report["leak"] and report["identifierCheck"] == "done"
    assert {p["treatmentLine"] for p in positions} == {2} and positions[0]["kind"] == "identifier"
    assert "FACTORS" not in json.dumps(tool.verdict(report))
    plan.write_text("# Plan\nThe hidden part is short.\n")  # plain words from oracle comments are not identifiers
    assert not tool.check([plan], [gold, tests], base, allowed_text=[issue])["leak"]
    assert tool.check([plan], [gold, tests])["identifierCheck"] == "skipped-no-base-dir"


def custody(tmp_path: Path, plan: Path, gold: Path, tests: Path, *extra: str) -> list[str]:
    root = tmp_path / "custody"
    anchor = tmp_path / "anchor.txt"
    if not anchor.exists():
        anchor.write_text("")
    return ["--treatment", str(plan), "--forbidden", str(gold), str(tests), "--verdict-only", "--task", "C01",
            "--register", str(root / "register.json"), "--attempt-log", str(root / "C01-attempts.json"),
            "--max-attempts", "2", "--anchor", str(anchor), *extra]


def test_revision_attempts_are_bounded_and_unchanged_files_do_not_consume_one(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, f"# Plan\n{SECRET}\n")
    argv = custody(tmp_path, plan, gold, tests)
    assert tool.main(argv) == 3  # no log yet: refused until explicitly initialized
    assert tool.main(argv + ["--init-attempt-log"]) == 1
    assert tool.main(argv) == 1 and "not counted" in capsys.readouterr().out
    plan.write_text("# Plan\nstill wrong: " + SECRET + "\n")
    assert tool.main(argv) == 1
    plan.write_text("# Plan\nMake convert honour the unit.\n")
    assert tool.main(argv) == 2 and "ESCALATE" in capsys.readouterr().out
    log = tmp_path / "custody" / "C01-attempts.json"
    assert len(json.loads(log.read_text())) == 2 and SECRET not in log.read_text()
    assert tool.main(argv + ["--init-attempt-log"]) == 3  # never re-initialized


def test_a_missing_truncated_or_reset_log_stops_every_check(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, "# Plan\nMake convert honour the unit.\n")
    argv = custody(tmp_path, plan, gold, tests)
    assert tool.main(argv + ["--init-attempt-log"]) == 0
    root = tmp_path / "custody"; log = root / "C01-attempts.json"; register = root / "register.json"
    saved = log.read_text()
    log.write_text("[]\n")  # truncated
    assert tool.main(argv) == 3 and "does not match" in capsys.readouterr().err
    log.unlink()
    assert tool.main(argv) == 3 and "missing" in capsys.readouterr().err
    log.write_text(saved)
    entries = json.loads(register.read_text()); entries[0]["entries"] = 5
    register.write_text(json.dumps(entries))  # register edited without its chain
    assert tool.main(argv) == 3 and "register broken" in capsys.readouterr().err


def test_the_verdict_for_authors_cannot_bypass_the_custody_circuit(tmp_path: Path):
    plan, gold, tests = files(tmp_path, "# Plan\n")
    import pytest
    with pytest.raises(SystemExit):
        tool.main(["--treatment", str(plan), "--forbidden", str(gold), "--verdict-only"])


def test_unreadable_custody_files_are_custody_errors(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, "# Plan\nMake convert honour the unit.\n")
    argv = custody(tmp_path, plan, gold, tests)
    assert tool.main(argv + ["--init-attempt-log"]) == 0
    root = tmp_path / "custody"
    (root / "C01-attempts.json").write_text("{not json")
    assert tool.main(argv) == 3 and "unreadable" in capsys.readouterr().err
    (root / "register.json").write_text("{not json")
    assert tool.main(argv) == 3 and "unreadable" in capsys.readouterr().err
    (root / "register.json").write_text('{"a": 1}')
    assert tool.main(argv) == 3 and "unexpected structure" in capsys.readouterr().err
    (root / "register.json").write_bytes(b"\xff\xfe")
    assert tool.main(argv) == 3


def test_every_write_exports_the_head_and_the_anchor_detects_a_joint_reset(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, "# Plan\nMake convert honour the unit.\n")
    root = tmp_path / "custody"; anchor = tmp_path / "audit" / "anchor.txt"; anchor.parent.mkdir()
    argv = custody(tmp_path, plan, gold, tests) + ["--anchor", str(anchor)]
    anchor.write_text("")
    assert tool.main(argv + ["--init-attempt-log"]) == 0
    heads = [line for line in capsys.readouterr().err.splitlines() if line.startswith("REGISTER_HEAD")]
    assert [h.split()[1:3] for h in heads] == [["C01", "init"], ["C01", "attempt"]]
    anchor.write_text("\n".join(heads) + "\n")
    plan.write_text("# Plan\nMake convert honour the unit argument.\n")
    assert tool.main(argv) == 0
    assert [l.split()[2] for l in capsys.readouterr().err.splitlines() if l.startswith("REGISTER_HEAD")] == ["attempt"]
    (root / "register.json").unlink(); (root / "C01-attempts.json").unlink()  # joint reset
    assert tool.main(argv + ["--init-attempt-log"]) == 3 and "anchor" in capsys.readouterr().err
    assert tool.main(custody(tmp_path, plan, gold, tests) + ["--anchor", str(tmp_path / "none")]) == 3


def test_the_exception_is_authorized_by_the_effective_reviewer_account_and_runs_once(tmp_path: Path, capsys, monkeypatch):
    plan, gold, tests = files(tmp_path, f"# Plan\n{SECRET}\n")
    root = tmp_path / "custody"
    assert tool.main(custody(tmp_path, plan, gold, tests, "--init-attempt-log")) == 1
    plan.write_text("# Plan\nMake convert honour the unit.\n")
    reviewers = root / "reviewers.json"; reviewers.write_text(json.dumps({"C01": ["reviewer-account"]}))
    base = ["--treatment", str(plan), "--forbidden", str(gold), str(tests), "--task", "C01",
            "--register", str(root / "register.json"), "--anchor", str(tmp_path / "anchor.txt")]
    authorize = base + ["--authorize-exception", "--reviewers", str(reviewers)]
    run = base + ["--exception-log", str(root / "C01-exception.json")]
    assert tool.main(run) == 3  # nothing authorized yet
    # a declared name is not an identity: LOGNAME/USER cannot impersonate the listed reviewer
    monkeypatch.setenv("LOGNAME", "reviewer-account"); monkeypatch.setenv("USER", "reviewer-account")
    assert tool.main(authorize) == 3 and "not an escalation reviewer" in capsys.readouterr().err
    reviewers.write_text(json.dumps({"C01": [tool.effective_account()]}))
    authorize[authorize.index("--reviewers") + 1] = str(reviewers)
    assert tool.main(authorize) == 0
    assert tool.main(authorize) == 3  # one authorization per task
    capsys.readouterr()
    assert tool.main(run) == 0
    out = capsys.readouterr().out
    assert "reviewer only" in out and "CLEAN" not in out and "LEAK" not in out
    record = json.loads((root / "C01-exception.json").read_text())[0]
    assert record["result"]["leak"] is False and record["issuer"] == tool.effective_account()
    assert tool.main(run) == 3  # once only
    (root / "C01-exception.json").unlink()
    assert tool.main(run) == 3  # the register still records the use


def test_custody_options_require_the_anchor(tmp_path: Path):
    import pytest
    plan, gold, tests = files(tmp_path, "# Plan\n")
    argv = custody(tmp_path, plan, gold, tests, "--init-attempt-log")
    without = argv[:argv.index("--anchor")] + argv[argv.index("--anchor") + 2:]
    with pytest.raises(SystemExit):
        tool.main(without)


def test_concurrent_custody_jobs_never_lose_register_entries(tmp_path: Path):
    import subprocess, sys
    plan, gold, tests = files(tmp_path, "# Plan\nMake convert honour the unit.\n")
    root = tmp_path / "custody"; anchor = tmp_path / "anchor.txt"; anchor.write_text("")
    script = ROOT / "tools" / "experiment" / "check_leakage.py"
    jobs = [subprocess.Popen([sys.executable, str(script), "--treatment", str(plan), "--forbidden", str(gold),
                              "--task", f"C0{i}", "--register", str(root / "register.json"), "--anchor", str(anchor),
                              "--attempt-log", str(root / f"C0{i}.json"), "--init-attempt-log"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(1, 9)]
    assert [job.wait() for job in jobs] == [0] * 8
    entries = tool.read_register(root / "register.json")  # chain intact
    assert len(entries) == 16 and {e["task"] for e in entries} == {f"C0{i}" for i in range(1, 9)}


def test_the_repository_l1_circuit_gives_one_verdict_against_the_union_of_the_task_oracles(tmp_path: Path, capsys):
    oracle1 = tmp_path / "oracle1"; oracle1.mkdir(); oracle2 = tmp_path / "oracle2"; oracle2.mkdir()
    (oracle1 / "gold.patch").write_text(GOLD_PATCH)
    (oracle2 / "gold.patch").write_text("diff --git a/pkg/io.py b/pkg/io.py\n--- a/pkg/io.py\n+++ b/pkg/io.py\n"
                                         "@@ -1 +1 @@\n+    return open(path, encoding='utf-8')  # second fix\n")
    base = tmp_path / "repo-at-R"; base.mkdir(); (base / "README.md").write_text("Units and io helpers.\n")
    bundle = tmp_path / "l1"; bundle.mkdir(); context = bundle / "context.md"
    context.write_text("# Context\nreturn open(path, encoding='utf-8')  # second fix\n")
    root = tmp_path / "custody"; anchor = tmp_path / "anchor.txt"; anchor.write_text("")
    argv = ["--treatment", str(context), "--forbidden", str(oracle1 / "gold.patch"), str(oracle2 / "gold.patch"),
            "--base-dir", str(base), "--task", "L1-pkg", "--register", str(root / "register.json"),
            "--anchor", str(anchor), "--attempt-log", str(root / "attempts" / "L1-pkg.json"), "--verdict-only", "--json"]
    assert tool.main(argv + ["--init-attempt-log"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out == {"verdict": "LEAK", "leak": True, "files": [{"file": str(context), "treatmentLines": [2]}]}  # no task named
    entry = json.loads((root / "attempts" / "L1-pkg.json").read_text())[0]
    assert len(entry["forbiddenSha256"]) == 2 and "second fix" not in json.dumps(entry)
