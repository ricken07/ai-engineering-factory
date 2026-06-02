from __future__ import annotations
import argparse, json
from pathlib import Path
import yaml
from .project import find_project, initialize, load_project
from .validation import validate_package
from .policy import resolve_policy
from .adapter_install import adapter_plan, install_adapter
from .mcp import render_claude, render_codex, resolve_bindings

def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aief")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate"); validate.add_argument("path", nargs="?", default=".")
    doctor = sub.add_parser("doctor"); doctor.add_argument("path", nargs="?", default=".")
    inspect = sub.add_parser("inspect"); inspect.add_argument("path", nargs="?", default="."); inspect.add_argument("--json", action="store_true")
    init = sub.add_parser("init"); init.add_argument("destination"); init.add_argument("--template"); init.add_argument("--force", action="store_true")
    resolve = sub.add_parser("resolve"); resolve.add_argument("decision"); resolve.add_argument("--json", action="store_true")
    setup = sub.add_parser("setup-adapter"); setup.add_argument("agent", choices=["codex","claude-code"]); setup.add_argument("--factory", default="."); setup.add_argument("--target"); setup.add_argument("--copy", action="store_true"); setup.add_argument("--execute", action="store_true")
    mcp = sub.add_parser("mcp-config"); mcp.add_argument("agent", choices=["codex","claude-code"]); mcp.add_argument("project", nargs="?", default="."); mcp.add_argument("--factory", default=".")
    return root

def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "resolve":
        data = yaml.safe_load(Path(args.decision).read_text(encoding="utf-8"))
        result = resolve_policy(data.get("requestedAutonomy", "L1"), data.get("constraints", [])).as_dict()
        print(json.dumps(result, indent=2) if args.json else yaml.safe_dump(result, sort_keys=False)); return 0
    if args.command == "setup-adapter":
        factory, target = Path(args.factory).resolve(), Path(args.target).expanduser() if args.target else None
        if args.execute:
            for path in install_adapter(factory,args.agent,target,args.copy): print(f"Installed {path}")
        else:
            for source,destination in adapter_plan(factory,args.agent,target): print(f"PLAN {source} -> {destination}")
        return 0
    if args.command == "mcp-config":
        project_root=find_project(Path(args.project)); bindings=resolve_bindings(Path(args.factory).resolve(),load_project(project_root))
        print(render_codex(bindings) if args.agent=="codex" else json.dumps(render_claude(bindings),indent=2)); return 0
    if args.command == "validate":
        path = Path(args.path); issues = validate_package(path)
        for issue in issues: print(f"ERROR {issue.path}: {issue.message}")
        print(f"Validation: {'FAILED' if issues else 'OK'} ({len(issues)} issue(s))")
        return bool(issues)
    if args.command == "init":
        package = Path(__file__).resolve().parents[1]
        initialize(Path(args.template) if args.template else package / "templates/project", Path(args.destination), args.force)
        print(f"Initialized {Path(args.destination).resolve()}"); return 0
    try: root = find_project(Path(args.path))
    except FileNotFoundError as exc: print(f"ERROR: {exc}"); return 1
    project = load_project(root)
    if args.command == "inspect":
        print(json.dumps(project, indent=2) if args.json else yaml.safe_dump(project, sort_keys=False)); return 0
    errors = []
    for key in ("project", "architecture", "domain", "conventions"):
        target = project.get("context", {}).get(key)
        if not target or not (root / target).exists(): errors.append(f"missing context: {key}")
    for repo in project.get("repositories", []):
        if not (root / repo["path"]).exists(): errors.append(f"missing repository: {repo['id']}")
    for error in errors: print(f"ERROR: {error}")
    print(f"Doctor: {'FAILED' if errors else 'OK'}"); return bool(errors)

if __name__ == "__main__": raise SystemExit(main())
