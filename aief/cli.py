from __future__ import annotations
import argparse, json
from pathlib import Path
import yaml
from .yamlio import load_yaml
from .project import find_project, initialize, load_project
from .validation import validate_package, validate_project
from .policy import resolve_policy
from .adapter_install import adapter_plan, install_adapter
from .mcp import render_claude, render_codex, resolve_bindings
from .integration_manager import doctor as integration_doctor, sync_agent, write_lock
from .intake import MUTATING, TaskRegistry
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
    intake=sub.add_parser("intake"); intake.add_argument("request"); intake.add_argument("--project",default="."); intake.add_argument("--factory",default="."); intake.add_argument("--agent",choices=["codex","claude-code"]); intake.add_argument("--intent",choices=["analyze","implement","fix","refactor","test","review","document","promote"]); intake.add_argument("--expect-workflow"); intake.add_argument("--json",action="store_true")
    run=sub.add_parser("run"); run.add_argument("request"); run.add_argument("--project",default="."); run.add_argument("--factory",default="."); run.add_argument("--agent",choices=["codex","claude-code"]); run.add_argument("--intent",choices=["analyze","implement","fix","refactor","test","review","document","promote"]); run.add_argument("--expect-workflow")
    task=sub.add_parser("task"); task_sub=task.add_subparsers(dest="task_command",required=True); task_inspect=task_sub.add_parser("inspect"); task_inspect.add_argument("id"); task_inspect.add_argument("--project",default="."); task_inspect.add_argument("--factory",default="."); task_inspect.add_argument("--json",action="store_true")
    task_log=task_sub.add_parser("log"); task_log.add_argument("id"); task_log.add_argument("--project",default="."); task_log.add_argument("--factory",default="."); task_log.add_argument("--json",action="store_true")
    task_list=task_sub.add_parser("list"); task_list.add_argument("--ready",action="store_true"); task_list.add_argument("--project",default="."); task_list.add_argument("--factory",default="."); task_list.add_argument("--json",action="store_true")
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
    backlog=sub.add_parser("backlog"); backlog_sub=backlog.add_subparsers(dest="backlog_command",required=True)
    backlog_import=backlog_sub.add_parser("import"); backlog_import.add_argument("--source",required=True); backlog_import.add_argument("--provider",required=True); backlog_import.add_argument("--config"); backlog_import.add_argument("--project",default="."); backlog_import.add_argument("--factory",default="."); backlog_import.add_argument("--json",action="store_true")
    backlog_inspect=backlog_sub.add_parser("inspect"); backlog_inspect.add_argument("id"); backlog_inspect.add_argument("--project",default="."); backlog_inspect.add_argument("--factory",default="."); backlog_inspect.add_argument("--json",action="store_true")
    backlog_draft=backlog_sub.add_parser("complete-draft"); backlog_draft.add_argument("id"); backlog_draft.add_argument("--result",required=True); backlog_draft.add_argument("--project",default="."); backlog_draft.add_argument("--factory",default="."); backlog_draft.add_argument("--json",action="store_true")
    backlog_dup=backlog_sub.add_parser("complete-duplicate-search"); backlog_dup.add_argument("id"); backlog_dup.add_argument("--result",required=True); backlog_dup.add_argument("--project",default="."); backlog_dup.add_argument("--factory",default="."); backlog_dup.add_argument("--json",action="store_true")
    backlog_preview=backlog_sub.add_parser("preview"); backlog_preview.add_argument("id"); backlog_preview.add_argument("--project",default="."); backlog_preview.add_argument("--factory",default="."); backlog_preview.add_argument("--json",action="store_true")
    backlog_apply=backlog_sub.add_parser("apply"); backlog_apply.add_argument("id"); backlog_apply.add_argument("--approve",action="store_true"); backlog_apply.add_argument("--project",default="."); backlog_apply.add_argument("--factory",default="."); backlog_apply.add_argument("--json",action="store_true")
    backlog_approval=backlog_sub.add_parser("operation-approval"); backlog_approval.add_argument("id"); backlog_approval.add_argument("operation"); backlog_approval.add_argument("decision",choices=["approve","reject"]); backlog_approval.add_argument("--project",default="."); backlog_approval.add_argument("--factory",default="."); backlog_approval.add_argument("--json",action="store_true")
    backlog_complete_op=backlog_sub.add_parser("complete-operation"); backlog_complete_op.add_argument("id"); backlog_complete_op.add_argument("operation"); backlog_complete_op.add_argument("--result",required=True); backlog_complete_op.add_argument("--project",default="."); backlog_complete_op.add_argument("--factory",default="."); backlog_complete_op.add_argument("--json",action="store_true")
    execution=sub.add_parser("execution"); execution_sub=execution.add_subparsers(dest="execution_command",required=True)
    for name in ("inspect","next","handoff"):
        command=execution_sub.add_parser(name); command.add_argument("id"); command.add_argument("--project",default="."); command.add_argument("--factory",default="."); command.add_argument("--json",action="store_true")
        if name == "handoff": command.add_argument("--owner")
    complete=execution_sub.add_parser("complete-phase"); complete.add_argument("id"); complete.add_argument("--output",required=True); complete.add_argument("--operation-id"); complete.add_argument("--owner"); complete.add_argument("--project",default="."); complete.add_argument("--factory",default="."); complete.add_argument("--json",action="store_true")
    approve_execution=execution_sub.add_parser("approve"); approve_execution.add_argument("id"); approve_execution.add_argument("--operation-id"); approve_execution.add_argument("--owner"); approve_execution.add_argument("--project",default="."); approve_execution.add_argument("--factory",default="."); approve_execution.add_argument("--json",action="store_true")
    approve_policy=execution_sub.add_parser("approve-policy"); approve_policy.add_argument("id"); approve_policy.add_argument("gate"); approve_policy.add_argument("--owner"); approve_policy.add_argument("--project",default="."); approve_policy.add_argument("--factory",default="."); approve_policy.add_argument("--json",action="store_true")
    lease=execution_sub.add_parser("lease"); lease.add_argument("action",choices=["acquire","renew","release","status"]); lease.add_argument("id"); lease.add_argument("--owner"); lease.add_argument("--ttl",type=int,default=300); lease.add_argument("--project",default="."); lease.add_argument("--factory",default="."); lease.add_argument("--json",action="store_true")
    profile_validation=execution_sub.add_parser("profile-validation"); profile_validation.add_argument("id"); profile_validation.add_argument("--project",default="."); profile_validation.add_argument("--factory",default="."); profile_validation.add_argument("--execute",action="store_true"); profile_validation.add_argument("--json",action="store_true")
    replay_validation=execution_sub.add_parser("replay-validation"); replay_validation.add_argument("id"); replay_validation.add_argument("--project",default="."); replay_validation.add_argument("--factory",default="."); replay_validation.add_argument("--json",action="store_true")
    engineering_context=execution_sub.add_parser("engineering-context"); engineering_context.add_argument("id"); engineering_context.add_argument("--repository",required=True); engineering_context.add_argument("--project",default="."); engineering_context.add_argument("--factory",default="."); engineering_context.add_argument("--json",action="store_true")
    engineering=sub.add_parser("engineering-context"); engineering.add_argument("repository"); engineering.add_argument("skill"); engineering.add_argument("--task"); engineering.add_argument("--project",default="."); engineering.add_argument("--factory",default="."); engineering.add_argument("--json",action="store_true")
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
        data=RuntimeService(Path(args.project),Path(args.factory)).resolve_repository_context(args.repository,args.skill,args.task)
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
    if args.command in {"intake", "run"}:
        service = RuntimeService(Path(args.project), Path(args.factory))
        if args.command == "intake":
            result = service.intake(args.request, args.agent, args.intent, args.expect_workflow)
            result = {key:value for key,value in result.items() if key != "path"} | {"taskFile": result["path"]}
            print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else yaml.safe_dump(result, sort_keys=False, allow_unicode=True))
        else:
            execution = service.start(args.request, args.agent, args.intent, args.expect_workflow)
            task = TaskRegistry(service.project_root).load(execution.data["task"])
            print(yaml.safe_dump({"runtimeReceipt":"created","execution":execution.data["metadata"]["id"],"status":execution.data["status"],"intent":task["intent"]["type"],"mutating":task["intent"]["type"] in MUTATING,"workflow":execution.data["workflow"],"task":execution.data["task"],"nextPhase":execution.next_phase()["id"],"taskLog":str(service.project_root/".ai"/"runtime"/"tasks"/task["metadata"]["id"]/"events.jsonl")},sort_keys=False))
        return 0
    if args.command == "task":
        project_root=find_project(Path(args.project))
        service=RuntimeService(project_root,Path(getattr(args,"factory",".")))
        if args.task_command=="log": data=service.task_events(args.id)
        elif args.task_command=="list": data=service.task_backlog(args.ready)
        elif args.task_command=="assess-tracking":
            impact=load_yaml(Path(args.impact))
            if not isinstance(impact,dict): raise ValueError("impact must be an object")
            data=service.reassess_tracking(args.id,impact)
        elif args.task_command=="tracking": data=service.tracking._read(args.id,"tracking.yaml")
        elif args.task_command=="resolve-provider": data=service.tracking.resolve_provider(args.id,agent=args.agent)
        elif args.task_command=="search-external": data=service.tracking.prepare_search(args.id)
        elif args.task_command=="complete-search":
            result=load_yaml(Path(args.result)); matches=result.get("matches",[]) if isinstance(result,dict) else result
            data=service.tracking.complete_search(args.id,matches)
        elif args.task_command=="propose-external":
            data=load_yaml(Path(args.proposal)); service.tracking.write_proposal(args.id,data)
        elif args.task_command=="create-external": data=service.tracking.prepare_create(args.id,args.approve)
        elif args.task_command=="link": data=service.tracking.prepare_link(args.id,args.reference,args.approve)
        elif args.task_command=="operation-approval": data=service.tracking.approve(args.id,args.operation,args.decision=="approve")
        elif args.task_command=="complete-operation":
            result=load_yaml(Path(args.result)); data=service.execute_tracking_operation(args.id,args.operation,lambda operation:result)
        else: data=TaskRegistry(project_root).load(args.id)
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
    if args.command == "backlog":
        project_root=find_project(Path(args.project))
        service=RuntimeService(project_root,Path(getattr(args,"factory",".")))
        if args.backlog_command=="import": data=service.backlog.start(args.source,args.provider,args.config)
        elif args.backlog_command=="inspect": data=service.backlog._read(args.id,"plan.yaml")
        elif args.backlog_command=="complete-draft":
            result=load_yaml(Path(args.result))
            candidates=result.get("candidates",[]) if isinstance(result,dict) else result
            open_questions=result.get("openQuestions",[]) if isinstance(result,dict) else []
            data=service.backlog.complete_draft(args.id,candidates,open_questions)
        elif args.backlog_command=="complete-duplicate-search":
            result=load_yaml(Path(args.result)); matches=result.get("matches",result) if isinstance(result,dict) else result
            data=service.backlog.complete_duplicate_search(args.id,matches)
        elif args.backlog_command=="preview": data=service.backlog.preview(args.id)
        elif args.backlog_command=="apply": data=service.backlog.apply(args.id,args.approve)
        elif args.backlog_command=="operation-approval": data=service.backlog.approve(args.id,args.operation,args.decision=="approve")
        elif args.backlog_command=="complete-operation":
            result=load_yaml(Path(args.result)); data=service.execute_backlog_operation(args.id,args.operation,lambda operation:result)
        else: raise ValueError(f"unknown backlog command: {args.backlog_command}")
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
    if args.command == "execution":
        service=RuntimeService(Path(args.project),Path(args.factory)); execution=service.execution(args.id)
        if args.execution_command=="engineering-context":
            data=service.engineering_context(args.id,args.repository)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="profile-validation":
            data=service.run_profile_validation(args.id) if args.execute else {"mode":"plan","commands":service.profile_validation_plan(args.id)}
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="replay-validation":
            data=service.replay_validation(args.id)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="complete-phase":
            output=load_yaml(Path(args.output))
            if not isinstance(output,dict): raise ValueError("phase output must be an object")
            execution=service.complete_phase(args.id,output,args.operation_id,args.owner)
        if args.execution_command=="approve": execution=service.approve_execution(args.id,args.operation_id,args.owner)
        if args.execution_command=="approve-policy": execution=service.approve_policy_gate(args.id,args.gate,args.owner)
        if args.execution_command=="lease":
            data=service.lease(args.id,args.action,args.owner,args.ttl)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="handoff": service.handoff_execution(args.id,args.owner)
        if args.execution_command=="next":
            data=service.prepare_phase(args.id)
        else: data=execution.data
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
    if args.command == "resolve":
        data = load_yaml(Path(args.decision))
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
