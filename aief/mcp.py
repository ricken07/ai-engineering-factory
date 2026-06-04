from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from typing import Any
import json, os, yaml

def provider_for(value: Any) -> str:
    if isinstance(value,str): return value
    if isinstance(value,dict) and isinstance(value.get("provider"),str): return value["provider"]
    raise ValueError("integration binding must be a provider string or {provider: id}")

def project_bindings(project: dict[str,Any]) -> dict[str,str]:
    return {capability:provider_for(value) for capability,value in project.get("integrations",{}).items()}

def load_provider(factory: Path, provider: str) -> tuple[dict[str,Any],dict[str,Any]]:
    root=factory/"integrations"/provider
    if not root.is_dir(): raise FileNotFoundError(f"unknown integration provider {provider}")
    manifest=yaml.safe_load((root/"integration.yaml").read_text(encoding="utf-8"))
    mcp=yaml.safe_load((root/"mcp.yaml").read_text(encoding="utf-8"))
    return manifest,mcp

def resolve_capability(factory: Path, project: dict[str,Any], capability: str, operation: str | None=None, environment: dict[str,str] | None=None) -> dict[str,Any]:
    bindings=project_bindings(project)
    if capability not in bindings: raise KeyError(f"project does not bind capability {capability}")
    provider=bindings[capability]; manifest,mcp=load_provider(factory,provider)
    declared={item["id"]:set(item["operations"]) for item in manifest["capabilities"]}
    if capability not in declared: raise ValueError(f"provider {provider} does not provide {capability}")
    if operation and operation not in declared[capability]: raise ValueError(f"provider {provider} does not declare {capability}.{operation}")
    if capability not in set(mcp["capabilities"]): raise ValueError(f"MCP {provider} does not expose {capability}")
    transport=dict(mcp["transport"]); env=environment if environment is not None else os.environ
    url_env=transport.get("urlEnvironment")
    if url_env:
        if not env.get(url_env): raise EnvironmentError(f"required MCP endpoint variable {url_env} is not set")
        transport["url"]=env[url_env]
    return {"provider":provider,"capability":capability,"operation":operation,"version":manifest["metadata"]["version"],"transport":transport,"toolHints":mcp.get("toolHints",[])}

def resolve_bindings(factory: Path, project: dict[str,Any], environment: dict[str,str] | None=None) -> list[dict[str,Any]]:
    grouped: dict[str,dict[str,Any]]={}
    for capability in project_bindings(project):
        item=resolve_capability(factory,project,capability,environment=environment); provider=item["provider"]
        grouped.setdefault(provider,{**item,"capabilities":[]})["capabilities"].append(capability)
    return [{**item,"capabilities":sorted(item["capabilities"])} for item in grouped.values()]

def integration_lock(factory: Path, project: dict[str,Any]) -> dict[str,Any]:
    grouped: dict[str,set[str]]={}
    for capability,provider in project_bindings(project).items(): grouped.setdefault(provider,set()).add(capability)
    values=[]
    for provider,capabilities in sorted(grouped.items()):
        manifest,mcp=load_provider(factory,provider)
        canonical=json.dumps({"manifest":manifest,"mcp":mcp},sort_keys=True,separators=(",",":"))
        values.append({"provider":provider,"version":manifest["metadata"]["version"],"capabilities":sorted(capabilities),"mcp":{"id":mcp["metadata"]["id"],"transport":mcp["transport"]["type"]},"contentHash":sha256(canonical.encode()).hexdigest()})
    return {"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"IntegrationLock","metadata":{"id":project["metadata"]["id"]+"-integrations"},"factoryVersion":project["factory"]["version"],"integrations":values}

def render_codex(bindings: list[dict[str,Any]]) -> str:
    lines=["# BEGIN AIEF MANAGED MCP","# Secrets remain in the environment."]
    for binding in sorted(bindings,key=lambda item:item["provider"]): lines.extend(["",f"[mcp_servers.{binding['provider']}]",f"url = \"{binding['transport']['url']}\""])
    return "\n".join(lines)+"\n# END AIEF MANAGED MCP\n"

def render_claude(bindings: list[dict[str,Any]]) -> dict[str,Any]:
    return {"mcpServers":{item["provider"]:{"type":"http","url":item["transport"]["url"]} for item in sorted(bindings,key=lambda value:value["provider"])}}
