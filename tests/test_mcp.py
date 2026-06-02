from pathlib import Path
from aief.adapter_install import adapter_plan, install_adapter
from aief.mcp import render_claude, render_codex, resolve_bindings

ROOT=Path(__file__).parents[1]
PROJECT={"integrations":{"source-control":"github","task-provider":"jira","knowledge-base":"confluence"}}
ENV={"GITHUB_MCP_URL":"https://github.invalid/mcp","JIRA_MCP_URL":"https://jira.invalid/mcp","CONFLUENCE_MCP_URL":"https://confluence.invalid/mcp"}

def test_project_provider_selection_resolves_mcp_bindings():
    values=resolve_bindings(ROOT,PROJECT,ENV)
    assert {v["provider"] for v in values}=={"github","jira","confluence"}
    assert "[mcp_servers.github]" in render_codex(values)
    assert set(render_claude(values)["mcpServers"])=={"github","jira","confluence"}

def test_adapter_install_is_plannable_and_idempotent(tmp_path):
    assert len(adapter_plan(ROOT,"codex",tmp_path))==8
    installed=install_adapter(ROOT,"codex",tmp_path)
    assert len(installed)==8
    assert install_adapter(ROOT,"codex",tmp_path)==installed
