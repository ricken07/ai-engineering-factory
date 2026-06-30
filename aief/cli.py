from __future__ import annotations
import argparse, json
from pathlib import Path
import yaml
from .project import find_project, initialize, load_project
from .validation import validate_package, validate_project
from .policy import resolve_policy
from .adapter_install import adapter_plan, install_adapter
from .mcp import render_claude, render_codex, resolve_bindings
from .integration_manager import doctor as integration_doctor, sync_agent, write_lock
from .intake import TaskRegistry
from .service import RuntimeService

def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aief")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate"); validate.add_argument("path", nargs="?", default="."); validate.add_argument("--factory",default=".")
    doctor = sub.add_parser("doctor"); doctor.add_argument("path", nargs="?", default=".")
    inspect = sub.add_parser("inspect"); inspect.add_argument("path", nargs="?", default="."); inspect.add_argument("--json", action="store_true")
    init = sub.add_parser("init"); init.add_argument("destination"); init.add_argument("--template"); init.add_argument("--force", action="store_true")
    resolve = sub.add_parser("resolve"); resolve.add_argument("decision"); resolve.add_argument("--json", action="store_true")
    setup = sub.add_parser("setup-adapter"); setup.add_argument("agent", choices=["codex","claude-code"]); setup.add_argument("--factory", default="."); setup.add_argument("--target"); setup.add_argument("--copy", action="store_true"); setup.add_argument("--execute", action="store_true")
    mcp = sub.add_parser("mcp-config"); mcp.add_argument("agent", choices=["codex","claude-code"]); mcp.add_argument("project", nargs="?", default="."); mcp.add_argument("--factory", default=".")
    integrations=sub.add_parser("integrations"); integration_sub=integrations.add_subparsers(dest="integration_command",required=True)
    for name in ("doctor","lock"):
        command=integration_sub.add_parser(name); command.add_argument("project",nargs="?",default="."); command.add_argument("--factory",default=".")
    sync=integration_sub.add_parser("sync"); sync.add_argument("agent",choices=["codex","claude-code"]); sync.add_argument("project",nargs="?",default="."); sync.add_argument("--factory",default="."); sync.add_argument("--scope",choices=["user","project"],default="project"); sync.add_argument("--execute",action="store_true")
    intake=sub.add_parser("intake"); intake.add_argument("request"); intake.add_argument("--project",default="."); intake.add_argument("--factory",default="."); intake.add_argument("--agent",choices=["codex","claude-code"]); intake.add_argument("--json",action="store_true")
    run=sub.add_parser("run"); run.add_argument("request"); run.add_argument("--project",default="."); run.add_argument("--factory",default="."); run.add_argument("--agent",choices=["codex","claude-code"])
    task=sub.add_parser("task"); task_sub=task.add_subparsers(dest="task_command",required=True); task_inspect=task_sub.add_parser("inspect"); task_inspect.add_argument("id"); task_inspect.add_argument("--project",default="."); task_inspect.add_argument("--json",action="store_true")
    task_assess=task_sub.add_parser("assess-tracking"); task_assess.add_argument("id"); task_assess.add_argument("--impact",required=True); task_assess.add_argument("--project",default="."); task_assess.add_argument("--factory",default="."); task_assess.add_argument("--json",action="store_true")
    for name in ("tracking","resolve-provider","search-external"):
        command=task_sub.add_parser(name); command.add_argument("id"); command.add_argument("--project",default="."); command.add_argument("--factory",default="."); command.add_argument("--json",action="store_true")
        if name=="resolve-provider": command.add_argument("--agent",choices=["codex","claude-code"])
    complete_search=task_sub.add_parser("complete-search"); complete_search.add_argument("id"); complete_search.add_argument("--result",required=True); complete_search.add_argument("--project",default="."); complete_search.add_argument("--factory",default="."); complete_search.add_argument("--json",action="store_true")
    proposal=task_sub.add_parser("propose-external"); proposal.add_argument("id"); proposal.add_argument("--proposal",required=True); proposal.add_argument("--project",default="."); proposal.add_argument("--factory",default="."); proposal.add_argument("--json",action="store_true")
    create=task_sub.add_parser("create-external"); create.add_argument("id"); create.add_argument("--approve",action="store_true"); create.add_argument("--project",default="."); create.add_argument("--factory",default="."); create.add_argument("--json",action="store_true")
    link=task_sub.add_parser("link"); link.add_argument("id"); link.add_argument("reference"); link.add_argument("--approve",action="store_true"); link.add_argument("--project",default="."); link.add_argument("--factory",default="."); link.add_argument("--json",action="store_true")
    approval=task_sub.add_parser("operation-approval"); approval.add_argument("id"); approval.add_argument("operation"); approval.add_argument("decision",choices=["approve","reject"]); approval.add_argument("--project",default="."); approval.add_argument("--factory",default="."); approval.add_argument("--json",action="store_true")
    complete_operation=task_sub.add_parser("complete-operation"); complete_operation.add_argument("id"); complete_operation.add_argument("operation"); complete_operation.add_argument("--result",required=True); complete_operation.add_argument("--project",default="."); complete_operation.add_argument("--factory",default="."); complete_operation.add_argument("--json",action="store_true")
    execution=sub.add_parser("execution"); execution_sub=execution.add_subparsers(dest="execution_command",required=True)
    for name in ("inspect","next","approve","handoff"):
        command=execution_sub.add_parser(name); command.add_argument("id"); command.add_argument("--project",default="."); command.add_argument("--factory",default="."); command.add_argument("--json",action="store_true")
    complete=execution_sub.add_parser("complete-phase"); complete.add_argument("id"); complete.add_argument("--output",required=True); complete.add_argument("--project",default="."); complete.add_argument("--factory",default="."); complete.add_argument("--json",action="store_true")
    profile_validation=execution_sub.add_parser("profile-validation"); profile_validation.add_argument("id"); profile_validation.add_argument("--project",default="."); profile_validation.add_argument("--factory",default="."); profile_validation.add_argument("--execute",action="store_true"); profile_validation.add_argument("--json",action="store_true")
    engineering_context=execution_sub.add_parser("engineering-context"); engineering_context.add_argument("id"); engineering_context.add_argument("--repository",required=True); engineering_context.add_argument("--project",default="."); engineering_context.add_argument("--factory",default="."); engineering_context.add_argument("--json",action="store_true")
    engineering=sub.add_parser("engineering-context"); engineering.add_argument("repository"); engineering.add_argument("skill"); engineering.add_argument("--project",default="."); engineering.add_argument("--factory",default="."); engineering.add_argument("--json",action="store_true")
    workspace=sub.add_parser("workspace"); workspace_sub=workspace.add_subparsers(dest="workspace_command",required=True)
    for name in ("inspect","prepare","verify","status","rollback"):
        command=workspace_sub.add_parser(name); command.add_argument("id"); command.add_argument("--project",default="."); command.add_argument("--factory",default="."); command.add_argument("--json",action="store_true")
        if name in {"prepare","rollback"}: command.add_argument("--execute",action="store_true")
    return root

def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "workspace":
        service=RuntimeService(Path(args.project),Path(args.factory))
        data=service.workspace(args.id,args.workspace_command,getattr(args,"execute",False))
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
    if args.command == "engineering-context":
        data=RuntimeService(Path(args.project),Path(args.factory)).resolve_repository_context(args.repository,args.skill)
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
    if args.command in {"intake", "run"}:
        service = RuntimeService(Path(args.project), Path(args.factory))
        if args.command == "intake":
            result = service.intake(args.request, args.agent)
            result = {key:value for key,value in result.items() if key != "path"} | {"taskFile": result["path"]}
            print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else yaml.safe_dump(result, sort_keys=False, allow_unicode=True))
        else:
            execution = service.start(args.request, args.agent)
            print(yaml.safe_dump({"execution":execution.data["metadata"]["id"],"status":execution.data["status"],"workflow":execution.data["workflow"],"task":execution.data["task"],"nextPhase":execution.next_phase()["id"]},sort_keys=False))
        return 0
    if args.command == "task":
        project_root=find_project(Path(args.project))
        service=RuntimeService(project_root,Path(getattr(args,"factory",".")))
        if args.task_command=="assess-tracking":
            impact=yaml.safe_load(Path(args.impact).read_text(encoding="utf-8"))
            if not isinstance(impact,dict): raise ValueError("impact must be an object")
            data=service.reassess_tracking(args.id,impact)
        elif args.task_command=="tracking": data=service.tracking._read(args.id,"tracking.yaml")
        elif args.task_command=="resolve-provider": data=service.tracking.resolve_provider(args.id,agent=args.agent)
        elif args.task_command=="search-external": data=service.tracking.prepare_search(args.id)
        elif args.task_command=="complete-search":
            result=yaml.safe_load(Path(args.result).read_text(encoding="utf-8")); matches=result.get("matches",[]) if isinstance(result,dict) else result
            data=service.tracking.complete_search(args.id,matches)
        elif args.task_command=="propose-external":
            data=yaml.safe_load(Path(args.proposal).read_text(encoding="utf-8")); service.tracking.write_proposal(args.id,data)
        elif args.task_command=="create-external": data=service.tracking.prepare_create(args.id,args.approve)
        elif args.task_command=="link": data=service.tracking.prepare_link(args.id,args.reference,args.approve)
        elif args.task_command=="operation-approval": data=service.tracking.approve(args.id,args.operation,args.decision=="approve")
        elif args.task_command=="complete-operation":
            result=yaml.safe_load(Path(args.result).read_text(encoding="utf-8")); data=service.execute_tracking_operation(args.id,args.operation,lambda operation:result)
        else: data=TaskRegistry(project_root).load(args.id)
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
    if args.command == "execution":
        service=RuntimeService(Path(args.project),Path(args.factory)); execution=service.execution(args.id)
        if args.execution_command=="engineering-context":
            data=service.engineering_context(args.id,args.repository)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="profile-validation":
            data=service.run_profile_validation(args.id) if args.execute else {"mode":"plan","commands":service.profile_validation_plan(args.id)}
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="complete-phase":
            output=yaml.safe_load(Path(args.output).read_text(encoding="utf-8"))
            if not isinstance(output,dict): raise ValueError("phase output must be an object")
            execution=service.complete_phase(args.id,output)
        if args.execution_command=="approve": execution.advance(approved=True)
        if args.execution_command=="handoff": execution.handoff()
        if args.execution_command=="next":
            data=service.prepare_phase(args.id)
        else: data=execution.data
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
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
    if args.command == "integrations":
        project_root=find_project(Path(args.project)); project=load_project(project_root); factory=Path(args.factory).resolve()
        if args.integration_command=="doctor": print(yaml.safe_dump(integration_doctor(factory,project_root,project,["codex","claude-code"]),sort_keys=False)); return 0
        if args.integration_command=="lock": print(f"Wrote {write_lock(factory,project_root,project)}"); return 0
        path,content=sync_agent(factory,project_root,project,args.agent,args.scope,args.execute)
        print(f"{'Wrote' if args.execute else 'PLAN'} {path}\n{content}"); return 0
    if args.command == "validate":
        path = Path(args.path); issues = validate_package(path) if (path / "core" / "schemas").is_dir() else validate_project(find_project(path), Path(args.factory))
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
