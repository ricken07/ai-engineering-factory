from __future__ import annotations
from pathlib import Path
from typing import Any
import os, yaml

def resolve_bindings(factory: Path, project: dict[str, Any], environment: dict[str,str] | None = None) -> list[dict[str, Any]]:
    env = environment if environment is not None else os.environ
    providers: dict[str, set[str]] = {}
    for capability, provider in project.get("integrations", {}).items(): providers.setdefault(provider, set()).add(capability)
    bindings = []
    for provider, requested in sorted(providers.items()):
        path = factory / "integrations" / provider / "mcp-binding.yaml"
        if not path.is_file(): raise FileNotFoundError(f"provider {provider} has no MCP binding")
        binding = yaml.safe_load(path.read_text(encoding="utf-8")); declared = set(binding["capabilities"])
        if not requested <= declared: raise ValueError(f"provider {provider} does not supply {sorted(requested-declared)}")
        transport = dict(binding["transport"]); url_env = transport.get("urlEnvironment")
        if url_env:
            if not env.get(url_env): raise EnvironmentError(f"required MCP endpoint variable {url_env} is not set")
            transport["url"] = env[url_env]
        bindings.append({"provider":provider,"capabilities":sorted(requested),"transport":transport,"toolHints":binding.get("toolHints",[])})
    return bindings

def render_codex(bindings: list[dict[str, Any]]) -> str:
    lines = ["# Merge into ~/.codex/config.toml. Secrets remain in the environment."]
    for binding in bindings:
        lines.extend(["",f"[mcp_servers.{binding['provider']}]",f"url = \"{binding['transport']['url']}\""])
    return "\n".join(lines)+"\n"

def render_claude(bindings: list[dict[str, Any]]) -> dict[str, Any]:
    return {"mcpServers":{binding["provider"]:{"type":"http","url":binding["transport"]["url"]} for binding in bindings}}
