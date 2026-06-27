from __future__ import annotations

from pathlib import Path
from typing import Any
import os

from .integration_manager import target_path
from .mcp import load_provider, project_bindings


class ProviderResolutionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


def resolve_task_provider(factory: Path, project_root: Path, project: dict[str, Any], required_operations: list[str], agent: str | None = None, environment: dict[str, str] | None = None) -> dict[str, Any]:
    bindings = project_bindings(project)
    if "task-provider" not in bindings:
        raise ProviderResolutionError("PROVIDER_NOT_CONFIGURED", "project does not bind task-provider")
    provider = bindings["task-provider"]
    try: manifest, mcp = load_provider(factory, provider)
    except FileNotFoundError as exc: raise ProviderResolutionError("PROVIDER_UNAVAILABLE", str(exc)) from exc
    capabilities = {item["id"]:set(item["operations"]) for item in manifest.get("capabilities", [])}
    if "task-provider" not in capabilities:
        raise ProviderResolutionError("CAPABILITY_UNSUPPORTED", f"provider {provider} does not expose task-provider")
    missing_operations = sorted(set(required_operations) - capabilities["task-provider"])
    if missing_operations:
        raise ProviderResolutionError("CAPABILITY_UNSUPPORTED", f"provider {provider} lacks operations: {', '.join(missing_operations)}")
    if "task-provider" not in set(mcp.get("capabilities", [])):
        raise ProviderResolutionError("MCP_NOT_CONFIGURED", f"MCP {provider} does not expose task-provider")
    env = environment if environment is not None else os.environ
    transport = mcp.get("transport", {})
    endpoint_key = transport.get("urlEnvironment")
    if endpoint_key and not env.get(endpoint_key):
        raise ProviderResolutionError("MCP_NOT_CONFIGURED", f"required MCP endpoint {endpoint_key} is missing")
    credential_keys = [key for key in transport.get("environment", []) if key != endpoint_key]
    missing_credentials = [key for key in credential_keys if not env.get(key)]
    if missing_credentials:
        raise ProviderResolutionError("AUTHENTICATION_REQUIRED", f"missing provider credentials: {', '.join(missing_credentials)}")
    if agent:
        paths = [target_path(agent, project_root, "project"), target_path(agent, project_root, "user")]
        configured = any(path.is_file() and provider in path.read_text(encoding="utf-8") for path in paths)
        if not configured: raise ProviderResolutionError("MCP_NOT_CONFIGURED", f"provider {provider} is not configured for adapter {agent}")
    return {"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"IntegrationResolution","metadata":{"id":f"task-provider-{provider}"},"capability":"task-provider","provider":{"id":provider,"version":manifest["metadata"]["version"]},"status":"available","operations":sorted(capabilities["task-provider"]),"mcp":{"status":"available","transport":transport["type"],"toolHints":mcp.get("toolHints",[])}}
