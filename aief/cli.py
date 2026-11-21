from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
import yaml
from .yamlio import load_yaml
from .project import factory_home, find_project, initialize, load_project, runtime_root
from .validation import validate_package, validate_project
from .policy import resolve_policy
from .adapter_install import adapter_plan, adapter_status, install_adapter, uninstall_adapter
from .mcp import render_claude, render_codex, resolve_bindings
from .integration_manager import doctor as integration_doctor, sync_agent, write_lock
from .intake import MUTATING, TaskRegistry
from .service import RuntimeService

def resolve_factory(explicit: str | None, project_root: Path) -> Path:
    """--factory, else AI_FACTORY_HOME (itself, or its <version> child)."""
    if explicit: return Path(explicit)
    try: return factory_home(load_project(project_root))
    except (FileNotFoundError, KeyError):
        value = os.environ.get("AI_FACTORY_HOME")
        if value and (Path(value).expanduser() / "core" / "schemas").is_dir(): return Path(value).expanduser()
        raise FileNotFoundError("Factory not found: pass --factory or set AI_FACTORY_HOME to a Factory checkout")

def resolve_adapter_factory(explicit: str | None) -> Path:
    """--factory, else AI_FACTORY_HOME, else the current directory when it is a Factory."""
    if explicit: return Path(explicit).resolve()
    value = os.environ.get("AI_FACTORY_HOME")
    for candidate in ([Path(value).expanduser()] if value else []) + [Path(".")]:
        if (candidate / "adapters").is_dir() and (candidate / "factory.yaml").is_file(): return candidate.resolve()
    raise FileNotFoundError("Factory not found: pass --factory or set AI_FACTORY_HOME to a Factory checkout")

def resolve_project_factory(explicit: str | None, project: str) -> Path:
    """--factory, else AI_FACTORY_HOME for the project, else the current directory when it is a Factory."""
    if explicit: return Path(explicit)
    try: return resolve_factory(None, find_project(Path(project)))
    except FileNotFoundError:
        if (Path(".") / "factory.yaml").is_file() and (Path(".") / "core" / "schemas").is_dir(): return Path(".")
        raise

def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aief")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate"); validate.add_argument("path", nargs="?", default="."); validate.add_argument("--factory",default=None)
    doctor = sub.add_parser("doctor"); doctor.add_argument("path", nargs="?", default=".")
    inspect = sub.add_parser("inspect"); inspect.add_argument("path", nargs="?", default="."); inspect.add_argument("--json", action="store_true")
    init = sub.add_parser("init"); init.add_argument("destination"); init.add_argument("--template"); init.add_argument("--force", action="store_true")
    resolve = sub.add_parser("resolve"); resolve.add_argument("decision"); resolve.add_argument("--json", action="store_true")
    setup = sub.add_parser("setup-adapter"); setup.add_argument("agent", choices=["codex","claude-code"]); setup.add_argument("--factory", default=None); setup.add_argument("--target"); setup.add_argument("--copy", action="store_true"); setup.add_argument("--execute", action="store_true")
    uninstall = sub.add_parser("uninstall-adapter"); uninstall.add_argument("agent", choices=["codex","claude-code"]); uninstall.add_argument("--factory", default=None); uninstall.add_argument("--target"); uninstall.add_argument("--copy", action="store_true"); uninstall.add_argument("--execute", action="store_true")
    verify = sub.add_parser("verify-adapter"); verify.add_argument("agent", choices=["codex","claude-code"]); verify.add_argument("--factory", default=None); verify.add_argument("--target"); verify.add_argument("--json", action="store_true")
    mcp = sub.add_parser("mcp-config"); mcp.add_argument("agent", choices=["codex","claude-code"]); mcp.add_argument("project", nargs="?", default="."); mcp.add_argument("--factory", default=None)
    integrations=sub.add_parser("integrations"); integration_sub=integrations.add_subparsers(dest="integration_command",required=True)
    for name in ("doctor","lock"):
        command=integration_sub.add_parser(name); command.add_argument("project",nargs="?",default="."); command.add_argument("--factory",default=None)
    sync=integration_sub.add_parser("sync"); sync.add_argument("agent",choices=["codex","claude-code"]); sync.add_argument("project",nargs="?",default="."); sync.add_argument("--factory",default=None); sync.add_argument("--scope",choices=["user","project"],default="project"); sync.add_argument("--execute",action="store_true")
    intake=sub.add_parser("intake"); intake.add_argument("request"); intake.add_argument("--project",default="."); intake.add_argument("--factory",default=None); intake.add_argument("--agent",choices=["codex","claude-code"]); intake.add_argument("--intent",choices=["analyze","implement","fix","refactor","test","review","document","promote"]); intake.add_argument("--expect-workflow"); intake.add_argument("--activation-confirmed",action="store_true"); intake.add_argument("--json",action="store_true")
    run=sub.add_parser("run"); run.add_argument("request"); run.add_argument("--project",default="."); run.add_argument("--factory",default=None); run.add_argument("--agent",choices=["codex","claude-code"]); run.add_argument("--intent",choices=["analyze","implement","fix","refactor","test","review","document","promote"]); run.add_argument("--expect-workflow"); run.add_argument("--activation-confirmed",action="store_true"); run.add_argument("--agent-session"); run.add_argument("--model-identifier"); run.add_argument("--experiment-condition",choices=["L0","L1","L2","L3"]); run.add_argument("--repeat-index",type=int); run.add_argument("--environment-identifier"); run.add_argument("--bound-plan",type=Path); run.add_argument("--bound-verification",type=Path); run.add_argument("--expect-plan-sha256"); run.add_argument("--expect-verification-sha256")
    task=sub.add_parser("task"); task_sub=task.add_subparsers(dest="task_command",required=True); task_inspect=task_sub.add_parser("inspect"); task_inspect.add_argument("id"); task_inspect.add_argument("--project",default="."); task_inspect.add_argument("--factory",default=None); task_inspect.add_argument("--json",action="store_true")
    task_log=task_sub.add_parser("log"); task_log.add_argument("id"); task_log.add_argument("--project",default="."); task_log.add_argument("--factory",default=None); task_log.add_argument("--json",action="store_true")
    task_list=task_sub.add_parser("list"); task_list.add_argument("--ready",action="store_true"); task_list.add_argument("--project",default="."); task_list.add_argument("--factory",default=None); task_list.add_argument("--json",action="store_true")
    task_assess=task_sub.add_parser("assess-tracking"); task_assess.add_argument("id"); task_assess.add_argument("--impact",required=True); task_assess.add_argument("--project",default="."); task_assess.add_argument("--factory",default=None); task_assess.add_argument("--json",action="store_true")
    for name in ("tracking","resolve-provider","search-external"):
        command=task_sub.add_parser(name); command.add_argument("id"); command.add_argument("--project",default="."); command.add_argument("--factory",default=None); command.add_argument("--json",action="store_true")
        if name=="resolve-provider": command.add_argument("--agent",choices=["codex","claude-code"])
    complete_search=task_sub.add_parser("complete-search"); complete_search.add_argument("id"); complete_search.add_argument("--result",required=True); complete_search.add_argument("--project",default="."); complete_search.add_argument("--factory",default=None); complete_search.add_argument("--json",action="store_true")
    proposal=task_sub.add_parser("propose-external"); proposal.add_argument("id"); proposal.add_argument("--proposal",required=True); proposal.add_argument("--project",default="."); proposal.add_argument("--factory",default=None); proposal.add_argument("--json",action="store_true")
    create=task_sub.add_parser("create-external"); create.add_argument("id"); create.add_argument("--approve",action="store_true"); create.add_argument("--project",default="."); create.add_argument("--factory",default=None); create.add_argument("--json",action="store_true")
    link=task_sub.add_parser("link"); link.add_argument("id"); link.add_argument("reference"); link.add_argument("--approve",action="store_true"); link.add_argument("--project",default="."); link.add_argument("--factory",default=None); link.add_argument("--json",action="store_true")
    approval=task_sub.add_parser("operation-approval"); approval.add_argument("id"); approval.add_argument("operation"); approval.add_argument("decision",choices=["approve","reject"]); approval.add_argument("--project",default="."); approval.add_argument("--factory",default=None); approval.add_argument("--json",action="store_true")
    complete_operation=task_sub.add_parser("complete-operation"); complete_operation.add_argument("id"); complete_operation.add_argument("operation"); complete_operation.add_argument("--result",required=True); complete_operation.add_argument("--project",default="."); complete_operation.add_argument("--factory",default=None); complete_operation.add_argument("--json",action="store_true")
    backlog=sub.add_parser("backlog"); backlog_sub=backlog.add_subparsers(dest="backlog_command",required=True)
    backlog_import=backlog_sub.add_parser("import"); backlog_import.add_argument("--source",required=True); backlog_import.add_argument("--provider",required=True); backlog_import.add_argument("--config"); backlog_import.add_argument("--project",default="."); backlog_import.add_argument("--factory",default=None); backlog_import.add_argument("--json",action="store_true")
    backlog_inspect=backlog_sub.add_parser("inspect"); backlog_inspect.add_argument("id"); backlog_inspect.add_argument("--project",default="."); backlog_inspect.add_argument("--factory",default=None); backlog_inspect.add_argument("--json",action="store_true")
    backlog_draft=backlog_sub.add_parser("complete-draft"); backlog_draft.add_argument("id"); backlog_draft.add_argument("--result",required=True); backlog_draft.add_argument("--project",default="."); backlog_draft.add_argument("--factory",default=None); backlog_draft.add_argument("--json",action="store_true")
    backlog_dup=backlog_sub.add_parser("complete-duplicate-search"); backlog_dup.add_argument("id"); backlog_dup.add_argument("--result",required=True); backlog_dup.add_argument("--project",default="."); backlog_dup.add_argument("--factory",default=None); backlog_dup.add_argument("--json",action="store_true")
    backlog_preview=backlog_sub.add_parser("preview"); backlog_preview.add_argument("id"); backlog_preview.add_argument("--project",default="."); backlog_preview.add_argument("--factory",default=None); backlog_preview.add_argument("--json",action="store_true")
    backlog_apply=backlog_sub.add_parser("apply"); backlog_apply.add_argument("id"); backlog_apply.add_argument("--approve",action="store_true"); backlog_apply.add_argument("--project",default="."); backlog_apply.add_argument("--factory",default=None); backlog_apply.add_argument("--json",action="store_true")
    backlog_approval=backlog_sub.add_parser("operation-approval"); backlog_approval.add_argument("id"); backlog_approval.add_argument("operation"); backlog_approval.add_argument("decision",choices=["approve","reject"]); backlog_approval.add_argument("--project",default="."); backlog_approval.add_argument("--factory",default=None); backlog_approval.add_argument("--json",action="store_true")
    backlog_complete_op=backlog_sub.add_parser("complete-operation"); backlog_complete_op.add_argument("id"); backlog_complete_op.add_argument("operation"); backlog_complete_op.add_argument("--result",required=True); backlog_complete_op.add_argument("--project",default="."); backlog_complete_op.add_argument("--factory",default=None); backlog_complete_op.add_argument("--json",action="store_true")
    execution=sub.add_parser("execution"); execution_sub=execution.add_subparsers(dest="execution_command",required=True)
    for name in ("inspect","next","handoff","evidence","metrics","payload-ledger","gate-check"):
        command=execution_sub.add_parser(name); command.add_argument("id"); command.add_argument("--project",default="."); command.add_argument("--factory",default=None); command.add_argument("--json",action="store_true")
        if name == "handoff": command.add_argument("--owner")
    complete=execution_sub.add_parser("complete-phase"); complete.add_argument("id"); complete.add_argument("--output",required=True); complete.add_argument("--operation-id"); complete.add_argument("--owner"); complete.add_argument("--project",default="."); complete.add_argument("--factory",default=None); complete.add_argument("--json",action="store_true")
    approve_execution=execution_sub.add_parser("approve"); approve_execution.add_argument("id"); approve_execution.add_argument("--operation-id"); approve_execution.add_argument("--owner"); approve_execution.add_argument("--approver"); approve_execution.add_argument("--project",default="."); approve_execution.add_argument("--factory",default=None); approve_execution.add_argument("--json",action="store_true")
    approve_policy=execution_sub.add_parser("approve-policy"); approve_policy.add_argument("id"); approve_policy.add_argument("gate"); approve_policy.add_argument("--owner"); approve_policy.add_argument("--approver"); approve_policy.add_argument("--project",default="."); approve_policy.add_argument("--factory",default=None); approve_policy.add_argument("--json",action="store_true")
    waive=execution_sub.add_parser("waive-finding"); waive.add_argument("id"); waive.add_argument("finding",type=int); waive.add_argument("--reason",required=True); waive.add_argument("--approver"); waive.add_argument("--project",default="."); waive.add_argument("--factory",default=None); waive.add_argument("--json",action="store_true")
    reject=execution_sub.add_parser("reject"); reject.add_argument("id"); reject.add_argument("--reason",required=True); reject.add_argument("--gate"); reject.add_argument("--owner"); reject.add_argument("--approver"); reject.add_argument("--project",default="."); reject.add_argument("--factory",default=None); reject.add_argument("--json",action="store_true")
    cancel=execution_sub.add_parser("cancel"); cancel.add_argument("id"); cancel.add_argument("--reason",required=True); cancel.add_argument("--owner"); cancel.add_argument("--project",default="."); cancel.add_argument("--factory",default=None); cancel.add_argument("--json",action="store_true")
    ask_user=execution_sub.add_parser("ask-user"); ask_user.add_argument("id"); ask_user.add_argument("--question",required=True); ask_user.add_argument("--requires-authority",action="store_true"); ask_user.add_argument("--owner"); ask_user.add_argument("--project",default="."); ask_user.add_argument("--factory",default=None); ask_user.add_argument("--json",action="store_true")
    answer_question=execution_sub.add_parser("answer-question"); answer_question.add_argument("id"); answer_question.add_argument("--answer",required=True); answer_question.add_argument("--owner"); answer_question.add_argument("--project",default="."); answer_question.add_argument("--factory",default=None); answer_question.add_argument("--json",action="store_true")
    lease=execution_sub.add_parser("lease"); lease.add_argument("action",choices=["acquire","renew","release","status"]); lease.add_argument("id"); lease.add_argument("--owner"); lease.add_argument("--ttl",type=int,default=300); lease.add_argument("--project",default="."); lease.add_argument("--factory",default=None); lease.add_argument("--json",action="store_true")
    check_proposal=execution_sub.add_parser("check-proposal"); check_proposal.add_argument("id"); check_proposal.add_argument("--output",required=True); check_proposal.add_argument("--owner"); check_proposal.add_argument("--project",default="."); check_proposal.add_argument("--factory",default=None); check_proposal.add_argument("--json",action="store_true")
    profile_validation=execution_sub.add_parser("profile-validation"); profile_validation.add_argument("id"); profile_validation.add_argument("--project",default="."); profile_validation.add_argument("--factory",default=None); profile_validation.add_argument("--execute",action="store_true"); profile_validation.add_argument("--owner"); profile_validation.add_argument("--json",action="store_true")
    replay_validation=execution_sub.add_parser("replay-validation"); replay_validation.add_argument("id"); replay_validation.add_argument("--project",default="."); replay_validation.add_argument("--factory",default=None); replay_validation.add_argument("--json",action="store_true")
    engineering_context=execution_sub.add_parser("engineering-context"); engineering_context.add_argument("id"); engineering_context.add_argument("--repository",required=True); engineering_context.add_argument("--project",default="."); engineering_context.add_argument("--factory",default=None); engineering_context.add_argument("--json",action="store_true")
    engineering=sub.add_parser("engineering-context"); engineering.add_argument("repository"); engineering.add_argument("skill"); engineering.add_argument("--task"); engineering.add_argument("--project",default="."); engineering.add_argument("--factory",default=None); engineering.add_argument("--json",action="store_true")
    workspace=sub.add_parser("workspace"); workspace_sub=workspace.add_subparsers(dest="workspace_command",required=True)
    for name in ("inspect","prepare","verify","status","rollback"):
        command=workspace_sub.add_parser(name); command.add_argument("id"); command.add_argument("--project",default="."); command.add_argument("--factory",default=None); command.add_argument("--json",action="store_true")
        if name in {"prepare","rollback"}: command.add_argument("--execute",action="store_true")
    approval=sub.add_parser("approval"); approval_sub=approval.add_subparsers(dest="approval_command",required=True)
    approval_hook=approval_sub.add_parser("hook"); approval_hook.add_argument("--agent",choices=["codex","claude-code"],required=True); approval_hook.add_argument("--factory",default=None)
    for name in ("install-hook","hook-status"):
        command=approval_sub.add_parser(name); command.add_argument("--agent",choices=["codex","claude-code"],required=True); command.add_argument("--project",default=".")
    return root

def approval_command(args: argparse.Namespace) -> int:
    from . import approval_hook
    if args.approval_command == "hook":
        # Called by the harness with the human's message as JSON on stdin.
        try: payload=json.load(sys.stdin)
        except ValueError: return 0
        def open_service(cwd: Path) -> RuntimeService:
            root=find_project(cwd); return RuntimeService(root, resolve_factory(args.factory, root))
        code,out,err=approval_hook.handle(payload,args.agent,open_service)
        if out: sys.stdout.write(out)
        if err: sys.stderr.write(err+"\n")
        return code
    try: root=find_project(Path(args.project))
    except FileNotFoundError as exc: print(f"ERROR: {exc}"); return 1
    if args.approval_command == "install-hook":
        path=approval_hook.install(root,args.agent)
        print(f"approval hook installed in {path}")
        if args.agent == "codex":
            print(f"rule installed in {root / approval_hook.CODEX_RULES}; trust the hook with /hooks in Codex")
        return 0
    state=approval_hook.installed(root,args.agent)
    print(f"approval hook for {args.agent}: {'installed' if state else 'absent'} ({root / approval_hook.CONFIG[args.agent]})")
    return 0 if state else 1

def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "approval": return approval_command(args)
    if args.command in {"setup-adapter", "uninstall-adapter", "verify-adapter"}:
        try: args.factory = str(resolve_adapter_factory(args.factory))
        except FileNotFoundError as exc: print(f"ERROR: {exc}"); return 1
    elif args.command != "validate" and hasattr(args, "factory") and hasattr(args, "project"):
        try: args.factory = str(resolve_project_factory(args.factory, args.project))
        except FileNotFoundError as exc: print(f"ERROR: {exc}"); return 1
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
            result = service.intake(args.request, args.agent, args.intent, args.expect_workflow, args.activation_confirmed)
            result = {key:value for key,value in result.items() if key != "path"} | {"taskFile": result["path"]}
            print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else yaml.safe_dump(result, sort_keys=False, allow_unicode=True))
        else:
            experiment = {
                "modelIdentifier": args.model_identifier,
                "condition": args.experiment_condition,
                "repeatIndex": args.repeat_index,
                "environmentIdentifier": args.environment_identifier,
            }
            execution = service.start(args.request, args.agent, args.intent, args.expect_workflow, args.activation_confirmed,
                                      args.agent_session, experiment, args.bound_plan, args.bound_verification,
                                      args.expect_plan_sha256, args.expect_verification_sha256)
            task = TaskRegistry(service.project_root).load(execution.data["task"])
            print(yaml.safe_dump({"runtimeReceipt":"created","execution":execution.data["metadata"]["id"],"status":execution.data["status"],"intent":task["intent"]["type"],"mutating":task["intent"]["type"] in MUTATING,"workflow":execution.data["workflow"],"task":execution.data["task"],"nextPhase":execution.next_phase()["id"],"taskLog":str(runtime_root(service.project_root, service.project)/"tasks"/task["metadata"]["id"]/"events.jsonl")},sort_keys=False))
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
        if args.execution_command=="check-proposal":
            data=service.check_proposal(args.id,load_yaml(Path(args.output)),args.owner)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0 if data["status"]=="passed" else 1
        if args.execution_command=="profile-validation":
            data=service.run_profile_validation(args.id,owner=args.owner) if args.execute else {"mode":"plan","commands":service.profile_validation_plan(args.id)}
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="replay-validation":
            data=service.replay_validation(args.id)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="evidence":
            data=service.evidence_bundle(args.id)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="waive-finding":
            data=service.waive_finding(args.id,args.finding,args.reason,args.approver)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="metrics":
            data=service.metrics(args.id)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="complete-phase":
            output=load_yaml(Path(args.output))
            if not isinstance(output,dict): raise ValueError("phase output must be an object")
            execution=service.complete_phase(args.id,output,args.operation_id,args.owner)
        if args.execution_command=="approve": execution=service.approve_execution(args.id,args.operation_id,args.owner,args.approver)
        if args.execution_command=="approve-policy": execution=service.approve_policy_gate(args.id,args.gate,args.owner,args.approver)
        if args.execution_command=="cancel": execution=service.cancel_execution(args.id,args.reason,args.owner)
        if args.execution_command=="reject": execution=service.reject_gate(args.id,args.reason,args.gate,args.owner,args.approver)
        if args.execution_command=="ask-user": execution=service.ask_user(args.id,args.question,args.requires_authority,args.owner)
        if args.execution_command=="answer-question": execution=service.answer_user_question(args.id,args.answer,args.owner)
        if args.execution_command=="lease":
            data=service.lease(args.id,args.action,args.owner,args.ttl)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="handoff": service.handoff_execution(args.id,args.owner)
        if args.execution_command=="gate-check":
            data=service.gate_check(args.id)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
        if args.execution_command=="payload-ledger":
            data=service.delivered_payloads(args.id)
            print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True))
            return 1 if data["gaps"] else 0
        if args.execution_command=="next":
            from .phase_brief import compact_prepared
            data=compact_prepared(service.prepare_phase(args.id))
        else: data=execution.data
        print(json.dumps(data,indent=2,ensure_ascii=False) if args.json else yaml.safe_dump(data,sort_keys=False,allow_unicode=True)); return 0
    if args.command == "resolve":
        data = load_yaml(Path(args.decision))
        result = resolve_policy(data.get("requestedAutonomy", "L1"), data.get("constraints", [])).as_dict()
        print(json.dumps(result, indent=2) if args.json else yaml.safe_dump(result, sort_keys=False)); return 0
    if args.command == "setup-adapter":
        factory, target = resolve_adapter_factory(args.factory), Path(args.target).expanduser() if args.target else None
        if args.execute:
            for path in install_adapter(factory,args.agent,target,args.copy): print(f"Installed {path}")
        else:
            for source,destination in adapter_plan(factory,args.agent,target): print(f"PLAN {source} -> {destination}")
        return 0
    if args.command == "uninstall-adapter":
        factory, target = resolve_adapter_factory(args.factory), Path(args.target).expanduser() if args.target else None
        if args.execute:
            removed = uninstall_adapter(factory,args.agent,target,args.copy)
            for path in removed: print(f"Removed {path}")
            if not removed: print("Nothing to remove")
        else:
            for entry in adapter_status(factory,args.agent,target):
                destination, status = entry["destination"], entry["status"]
                if status == "absent": print(f"SKIP {destination} (absent)")
                elif status == "linked": print(f"PLAN remove {destination} (linked)")
                elif status == "copied" and args.copy: print(f"PLAN remove {destination} (copied)")
                elif status == "copied": print(f"REFUSE {destination} (copied; pass --copy to remove)")
                elif status == "broken": print(f"REFUSE {destination} (linked elsewhere)")
                else: print(f"REFUSE {destination} (not managed by this Factory)")
        return 0
    if args.command == "verify-adapter":
        factory, target = resolve_adapter_factory(args.factory), Path(args.target).expanduser() if args.target else None
        statuses = adapter_status(factory,args.agent,target)
        healthy = {"linked","copied"}
        if args.json:
            print(json.dumps(statuses, indent=2))
        else:
            for entry in statuses: print(f"{entry['status'].upper()} {entry['destination']}")
        return bool(any(entry["status"] not in healthy for entry in statuses))
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
        path = Path(args.path)
        if (path / "core" / "schemas").is_dir(): issues = validate_package(path)
        else:
            try: project_root = find_project(path); factory = resolve_factory(args.factory, project_root)
            except FileNotFoundError as exc: print(f"ERROR: {exc}"); return 1
            issues = validate_project(project_root, factory)
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
