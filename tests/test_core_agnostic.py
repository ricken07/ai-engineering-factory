from pathlib import Path
import re

CORE = Path(__file__).parents[1] / "core"
FORBIDDEN = {"emmany", "egw-", "java", "spring", "maven", "flutter", "react", "node", "gitlab", "github", "jira", "confluence", "claude", "codex", "openai", "anthropic"}

def test_core_has_no_project_stack_provider_or_agent_dependency():
    violations = []
    for path in CORE.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8").lower()
            for forbidden in FORBIDDEN:
                if re.search(rf"(?<![a-z0-9]){re.escape(forbidden)}(?![a-z0-9])", text):
                    violations.append(f"{path.relative_to(CORE)}: {forbidden}")
    assert violations == []
