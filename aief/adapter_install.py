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
