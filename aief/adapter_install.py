from __future__ import annotations
from pathlib import Path
import shutil, yaml

def adapter_plan(factory: Path, agent: str, target: Path | None = None) -> list[tuple[Path,Path]]:
    config = yaml.safe_load((factory/"adapters"/agent/"adapter.yaml").read_text(encoding="utf-8"))
    destination = target or Path(config["installation"]["userSkillsDirectory"]).expanduser()
    source = factory/"adapters"/agent/"skills"
    return [(skill, destination/skill.name) for skill in sorted(source.iterdir()) if (skill/"SKILL.md").is_file()]

def install_adapter(factory: Path, agent: str, target: Path | None = None, copy: bool = False) -> list[Path]:
    installed=[]
    for source,destination in adapter_plan(factory,agent,target):
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() and destination.resolve()==source.resolve(): installed.append(destination); continue
            raise FileExistsError(f"refusing to replace {destination}")
        shutil.copytree(source,destination) if copy else destination.symlink_to(source, target_is_directory=True)
        installed.append(destination)
    return installed

def adapter_status(factory: Path, agent: str, target: Path | None = None) -> list[dict]:
    """Per-skill installation status, without touching the filesystem."""
    statuses=[]
    for source,destination in adapter_plan(factory,agent,target):
        if destination.is_symlink():
            state = "linked" if destination.resolve()==source.resolve() else "broken"
        elif destination.is_dir():
            state = "copied"
        elif destination.exists():
            state = "conflict"
        else:
            state = "absent"
        statuses.append({"skill":source.name,"source":str(source),"destination":str(destination),"status":state})
    return statuses

def uninstall_adapter(factory: Path, agent: str, target: Path | None = None, copy: bool = False) -> list[Path]:
    """Remove only entries this Factory installed: a symlink resolving to its
    source, or, with `copy`, a directory previously installed by `--copy`.
    Refuses to touch anything else, mirroring `install_adapter`'s refusal to
    replace an unrelated path."""
    removed=[]
    for source,destination in adapter_plan(factory,agent,target):
        if not destination.exists() and not destination.is_symlink(): continue
        if destination.is_symlink():
            if destination.resolve()!=source.resolve(): raise FileExistsError(f"refusing to remove {destination}: not linked to {source}")
            destination.unlink(); removed.append(destination); continue
        if copy and destination.is_dir():
            shutil.rmtree(destination); removed.append(destination); continue
        raise FileExistsError(f"refusing to remove {destination}: pass --copy to remove a copied installation")
    return removed
