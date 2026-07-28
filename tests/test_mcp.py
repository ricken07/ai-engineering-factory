from pathlib import Path
from aief.adapter_install import adapter_plan, install_adapter
from aief.mcp import integration_lock, render_claude, render_codex, resolve_bindings, resolve_capability
from aief.integration_manager import doctor, sync_agent, write_lock

ROOT=Path(__file__).parents[1]
PROJECT={"integrations":{"source-control":"github","task-provider":"jira","knowledge-base":"confluence"}}
ENV={"GITHUB_MCP_URL":"https://github.invalid/mcp","JIRA_MCP_URL":"https://jira.invalid/mcp","CONFLUENCE_MCP_URL":"https://confluence.invalid/mcp"}

def test_project_provider_selection_resolves_mcp_bindings():
    values=resolve_bindings(ROOT,PROJECT,ENV)
    assert {v["provider"] for v in values}=={"github","jira","confluence"}
    assert "[mcp_servers.github]" in render_codex(values)
    assert set(render_claude(values)["mcpServers"])=={"github","jira","confluence"}
    assert resolve_capability(ROOT,PROJECT,"task-provider","get-task",ENV)["provider"]=="jira"

def test_gitlab_uses_codex_stdio_oauth_proxy_and_claude_native_oauth():
    project={"integrations":{"source-control":"gitlab"}}
    env={"GITLAB_MCP_URL":"https://gitlab.example/mcp"}
    values=resolve_bindings(ROOT,project,env)
    codex=render_codex(values)
    claude=render_claude(values)["mcpServers"]["gitlab"]
    assert 'command = "npx"' in codex
    assert 'mcp-remote@0.1.26' in codex
    assert '\\"scope\\":\\"mcp\\"' in codex
    assert 'bearer_token_env_var' not in codex
    assert "headers" not in claude
    assert values[0]["authentication"]["type"]=="oauth"

def test_bearer_authentication_is_rendered_by_reference_without_secret_value():
    values=[{"provider":"private","transport":{"url":"https://private.invalid/mcp"},"authentication":{"type":"bearer","tokenEnvironment":"PRIVATE_TOKEN"}}]
    codex=render_codex(values)
    claude=render_claude(values)["mcpServers"]["private"]
    assert 'bearer_token_env_var = "PRIVATE_TOKEN"' in codex
    assert claude["headers"]["Authorization"]=="Bearer ${PRIVATE_TOKEN}"

def test_integration_lock_is_deterministic_and_secret_free(tmp_path):
    project={**PROJECT,"metadata":{"id":"demo"},"factory":{"version":"1.3.0"},"integrationLock":".ai/integration-lock.yaml"}
    first=integration_lock(ROOT,project); second=integration_lock(ROOT,project)
    assert first==second
    assert "TOKEN" not in str(first)
    path=write_lock(ROOT,tmp_path,project)
    assert path.is_file()

def test_sync_is_dry_run_and_preserves_unmanaged_codex_configuration(tmp_path):
    project={**PROJECT,"metadata":{"id":"demo"},"factory":{"version":"1.3.0"}}
    path,content=sync_agent(ROOT,tmp_path,project,"codex","project",environment=ENV)
    assert not path.exists() and "mcp_servers.github" in content
    sync_agent(ROOT,tmp_path,project,"codex","project",execute=True,environment=ENV)
    assert path.exists()
    path.write_text('model = "example"\n')
    sync_agent(ROOT,tmp_path,project,"codex","project",execute=True,environment=ENV)
    merged=path.read_text()
    assert 'model = "example"' in merged and "BEGIN AIEF MANAGED MCP" in merged

def test_doctor_reports_lock_authentication_and_agent_configuration(tmp_path):
    project={**PROJECT,"metadata":{"id":"demo"},"factory":{"version":"1.3.0"}}
    report=doctor(ROOT,tmp_path,project,["codex"],ENV)
    statuses={item["check"]:item["status"] for item in report["checks"] if item["check"]!="authentication-environment"}
    assert statuses=={"catalog-resolution":"ok","integration-lock":"missing","agent-mcp":"missing"}

def test_adapter_install_is_plannable_and_idempotent(tmp_path):
    assert len(adapter_plan(ROOT,"codex",tmp_path))==8
    installed=install_adapter(ROOT,"codex",tmp_path)
    assert len(installed)==8
    assert install_adapter(ROOT,"codex",tmp_path)==installed

def test_every_adapter_skill_enters_the_shared_runtime_protocol():
    for agent, identity in (("codex", "--agent codex"), ("claude-code", "--agent claude-code")):
        adapter=ROOT / "adapters" / agent
        protocol=(adapter / "runtime-protocol.md").read_text(encoding="utf-8")
        assert "aief run" in protocol
        assert "aief execution next" in protocol
        assert "aief execution complete-phase" in protocol
        assert identity in protocol
        skills=sorted((adapter / "skills").glob("*/SKILL.md"))
        assert len(skills)==8
        for skill in skills:
            content=skill.read_text(encoding="utf-8")
            assert "Runtime Protocol" in content
            assert "user request" in content
            assert "aief run" in content
