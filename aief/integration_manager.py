from __future__ import annotations
from pathlib import Path
from typing import Any
import json, os, yaml
from .mcp import integration_lock, load_provider, render_claude, render_codex, resolve_bindings

def target_path(agent: str, project_root: Path, scope: str) -> Path:
    if scope=="project": return project_root/(".codex/config.toml" if agent=="codex" else ".mcp.json")
    if scope=="user": return Path.home()/(".codex/config.toml" if agent=="codex" else ".claude.json")
    raise ValueError("scope must be project or user")

def doctor(factory: Path, project_root: Path, project: dict[str,Any], agents: list[str], environment: dict[str,str]|None=None) -> dict[str,Any]:
    env=environment if environment is not None else os.environ; checks=[]
    try: bindings=resolve_bindings(factory,project,env); checks.append({"check":"catalog-resolution","status":"ok","providers":sorted(b["provider"] for b in bindings)})
    except Exception as exc: bindings=[]; checks.append({"check":"catalog-resolution","status":"error","message":str(exc)})
    expected=integration_lock(factory,project); lock_path=project_root/project.get("integrationLock",".ai/integration-lock.yaml")
    actual=yaml.safe_load(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else None
    checks.append({"check":"integration-lock","status":"ok" if actual==expected else "missing" if actual is None else "stale","path":str(lock_path)})
    providers=sorted({provider for provider in (item.get("provider") for item in bindings) if provider})
    for provider in providers:
        _,mcp=load_provider(factory,provider)
        missing=[key for key in mcp["transport"].get("environment",[]) if not env.get(key)]
        checks.append({"check":"authentication-environment","provider":provider,"status":"ok" if not missing else "missing","missing":missing})
    for agent in agents:
        paths=[target_path(agent,project_root,"project"),target_path(agent,project_root,"user")]
        contents="\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())
        missing=[provider for provider in providers if provider not in contents]
        checks.append({"check":"agent-mcp","agent":agent,"status":"configured" if not missing else "missing","missingProviders":missing})
    return {"project":project["metadata"]["id"],"factory":project["factory"]["version"],"checks":checks}

def write_lock(factory: Path, project_root: Path, project: dict[str,Any]) -> Path:
    path=project_root/project.get("integrationLock",".ai/integration-lock.yaml"); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(yaml.safe_dump(integration_lock(factory,project),sort_keys=False),encoding="utf-8"); return path

def sync_agent(factory: Path, project_root: Path, project: dict[str,Any], agent: str, scope: str, execute: bool=False, environment: dict[str,str]|None=None) -> tuple[Path,str]:
    bindings=resolve_bindings(factory,project,environment); path=target_path(agent,project_root,scope)
    content=render_codex(bindings) if agent=="codex" else json.dumps(render_claude(bindings),indent=2)+"\n"
    final=content
    if path.exists():
        existing=path.read_text(encoding="utf-8")
        if agent=="codex":
            begin="# BEGIN AIEF MANAGED MCP"; end="# END AIEF MANAGED MCP"
            if begin in existing and end in existing:
                prefix=existing.split(begin,1)[0]; suffix=existing.split(end,1)[1].lstrip("\n")
                final=prefix+content+(suffix if not suffix else "\n"+suffix)
            else: final=existing.rstrip()+"\n\n"+content
        else:
            try: current=json.loads(existing)
            except json.JSONDecodeError as exc: raise ValueError(f"cannot safely merge invalid Claude JSON {path}: {exc}") from exc
            desired=json.loads(content); servers=current.setdefault("mcpServers",{})
            for provider,value in desired["mcpServers"].items():
                if provider in servers and servers[provider]!=value: raise FileExistsError(f"unmanaged Claude MCP collision for {provider}")
                servers[provider]=value
            final=json.dumps(current,indent=2)+"\n"
    if not execute: return path,final
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(final,encoding="utf-8"); return path,final
