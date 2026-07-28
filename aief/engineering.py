from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml
import hashlib
import json

from .capabilities import resolve_profiles


class EngineeringContextError(ValueError):
    """Raised when engineering knowledge cannot be resolved safely."""


class PracticeConflict(EngineeringContextError):
    pass


def _load_all_practices(factory: Path) -> dict[str, dict[str, Any]]:
    practices: dict[str, dict[str, Any]] = {}
    root = factory / "organization"
    for path in sorted(root.rglob("*.yaml")):
        practice = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(practice, dict) or practice.get("kind") != "Practice":
            continue
        identifier = practice["metadata"]["id"]
        if identifier in practices:
            raise EngineeringContextError(f"duplicate organization practice: {identifier}")
        document = (path.parent / practice["document"]["path"]).resolve()
        if not document.is_relative_to(root.resolve()):
            raise EngineeringContextError(f"practice document escapes organization catalog: {identifier}")
        if not document.is_file():
            raise EngineeringContextError(f"practice document is missing: {identifier}: {document}")
        practices[identifier] = {**practice, "_manifest": path, "_document": document}
    return practices


def _load_catalog_manifests(factory: Path) -> dict[str, dict[str, Any]]:
    catalogs: dict[str, dict[str, Any]] = {}
    root = factory / "organization" / "catalogs"
    for path in sorted(root.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("kind") != "OrganizationCatalog":
            continue
        identifier = data["metadata"]["id"]
        if identifier in catalogs:
            raise EngineeringContextError(f"duplicate organization catalog: {identifier}")
        catalogs[identifier] = {**data, "_manifest": path}
    return catalogs


def _resolve_catalogs(factory: Path, references: list[str]) -> list[dict[str, Any]]:
    available = _load_catalog_manifests(factory)
    resolved: list[dict[str, Any]] = []
    visiting: set[str] = set()
    completed: set[str] = set()

    def visit(reference: str) -> None:
        identifier, version = _parse_ref(reference)
        if identifier not in available:
            raise EngineeringContextError(f"unknown organization catalog: {identifier}")
        catalog = available[identifier]
        actual = catalog["metadata"]["version"]
        if version and version != actual:
            raise EngineeringContextError(f"organization catalog {identifier} requires version {version}, catalog provides {actual}")
        if identifier in completed:
            return
        if identifier in visiting:
            raise EngineeringContextError(f"organization catalog inheritance cycle: {identifier}")
        visiting.add(identifier)
        for parent in catalog.get("extends", []):
            visit(parent)
        visiting.remove(identifier)
        completed.add(identifier)
        resolved.append(catalog)

    for reference in references:
        visit(reference)
    return resolved


def load_practices(factory: Path, catalog_references: list[str] | None = None) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    references = catalog_references if catalog_references is not None else ["factory-default@1.0.0"]
    catalogs = _resolve_catalogs(factory, references)
    available = _load_all_practices(factory)
    selected: dict[str, dict[str, Any]] = {}
    for catalog in catalogs:
        for reference in catalog.get("practiceRefs", []):
            practice = _resolve_reference(available, reference)
            selected[practice["metadata"]["id"]] = practice
        for references_for_profile in catalog.get("profileBindings", {}).values():
            for reference in references_for_profile:
                practice = _resolve_reference(available, reference)
                selected[practice["metadata"]["id"]] = practice
    return selected, catalogs


def _parse_ref(reference: str) -> tuple[str, str | None]:
    identifier, separator, version = reference.partition("@")
    return identifier, version if separator else None


def _resolve_reference(catalog: dict[str, dict[str, Any]], reference: str) -> dict[str, Any]:
    identifier, version = _parse_ref(reference)
    if identifier not in catalog:
        raise EngineeringContextError(f"unknown organization practice: {identifier}")
    practice = catalog[identifier]
    actual = practice["metadata"]["version"]
    if version and version != actual:
        raise EngineeringContextError(f"practice {identifier} requires version {version}, catalog provides {actual}")
    return practice


def _applies(practice: dict[str, Any], profiles: set[str], skill: str) -> bool:
    applies = practice.get("appliesTo", {})
    selected_profiles = set(applies.get("profiles", []))
    selected_skills = set(applies.get("skills", []))
    return (not selected_profiles or bool(selected_profiles & profiles)) and (not selected_skills or skill in selected_skills)


def _local_document(project_root: Path, reference: str, owner: str) -> Path:
    document = (project_root / reference).resolve()
    if not document.is_relative_to(project_root.resolve()):
        raise EngineeringContextError(f"{owner} engineering document escapes project workspace: {reference}")
    if not document.is_file():
        raise EngineeringContextError(f"{owner} engineering document is missing: {reference}")
    return document


def resolve_engineering_context(factory: Path, project_root: Path, project: dict[str, Any], repository_id: str, skill_id: str, task: dict[str, Any] | None = None) -> dict[str, Any]:
    repositories = {repository["id"]: repository for repository in project.get("repositories", [])}
    if repository_id not in repositories:
        raise EngineeringContextError(f"unknown repository: {repository_id}")
    repository = repositories[repository_id]
    resolved_profiles = resolve_profiles(factory, repository.get("profiles", []))
    profile_ids = [profile["metadata"]["id"] for profile in resolved_profiles]
    profile_resolutions=[{"id":profile["metadata"]["id"],"version":profile["metadata"]["version"],"source":str(factory/"profiles"/profile["metadata"]["id"]/"profile.yaml"),"extends":profile.get("extends",[])} for profile in resolved_profiles]
    profile_set = set(profile_ids)
    skill_path = factory / "core" / "skills" / skill_id / "skill.yaml"
    if not skill_path.is_file(): raise EngineeringContextError(f"unknown Core Skill: {skill_id}")
    skill = yaml.safe_load(skill_path.read_text(encoding="utf-8"))
    categories = list(skill.get("engineeringContext", {}).get("requires", []))
    engineering = project.get("engineering", {})
    catalog_refs = engineering.get("organizationCatalogs", ["factory-default@1.0.0"])
    catalog, selected_catalogs = load_practices(factory, catalog_refs)
    profile_refs = [reference for profile in resolved_profiles for reference in profile.get("practiceRefs", [])]
    for selected_catalog in selected_catalogs:
        bindings = selected_catalog.get("profileBindings", {})
        for profile_id in profile_ids:
            profile_refs.extend(bindings.get(profile_id, []))
    profile_refs = list(dict.fromkeys(profile_refs))
    active: dict[str, dict[str, Any]] = {}
    resolutions: list[dict[str, Any]] = []

    inherit_organization = engineering.get("inheritOrganization", True)
    for identifier, practice in catalog.items():
        if practice["category"] not in categories or not _applies(practice, profile_set, skill_id):
            continue
        referenced = any(_parse_ref(reference)[0] == identifier for reference in profile_refs)
        if practice["enforcement"] == "mandatory" or (inherit_organization and practice["enforcement"] == "default" and referenced):
            active[identifier] = practice
            resolutions.append({"practice":identifier,"action":"inherit","source":"organization"})
    for reference in profile_refs:
        practice = _resolve_reference(catalog, reference)
        if practice["category"] in categories and _applies(practice, profile_set, skill_id) and practice["enforcement"] != "optional" and inherit_organization:
            active[practice["metadata"]["id"]] = practice

    def apply_configuration(configuration: dict[str, Any], source: str) -> None:
        for reference, selection in configuration.get("practices", {}).items():
            identifier, requested_version = _parse_ref(reference)
            mode = selection["mode"]
            practice = catalog.get(identifier)
            if practice is None:
                if mode != "enable" or not selection.get("ref") or not selection.get("category"):
                    raise EngineeringContextError(f"unknown practice {identifier}; local practices require enable, ref and category")
                if selection["category"] not in categories: continue
                document = _local_document(project_root, selection["ref"], source)
                active[identifier] = {"metadata":{"id":identifier,"version":"1.0.0"},"category":selection["category"],"enforcement":"default","override":{"allowed":True},"_document":document}
                resolutions.append({"practice":identifier,"action":"enable","source":source})
                continue
            actual_version = practice["metadata"]["version"]
            if requested_version and requested_version != actual_version:
                raise EngineeringContextError(f"practice {identifier} requires version {requested_version}, catalog provides {actual_version}")
            if practice["category"] not in categories or not _applies(practice, profile_set, skill_id): continue
            if mode == "inherit": continue
            if mode == "disable":
                if practice["enforcement"] == "mandatory":
                    raise PracticeConflict(f"PRACTICE_CONFLICT: {source} cannot disable mandatory practice {identifier}")
                active.pop(identifier, None); resolutions.append({"practice":identifier,"action":"disable","source":source}); continue
            if mode == "enable":
                active[identifier] = practice; resolutions.append({"practice":identifier,"action":"enable","source":source}); continue
            if mode == "override":
                if practice["enforcement"] == "mandatory" or not practice["override"]["allowed"]:
                    raise PracticeConflict(f"PRACTICE_CONFLICT: {source} cannot override protected practice {identifier}")
                document = _local_document(project_root, selection["ref"], source)
                active[identifier] = {**practice,"_document":document,"_base_document":practice["_document"],"_overrides":str(practice["_document"])}
                resolutions.append({"practice":identifier,"action":"override","source":source})

    apply_configuration(project.get("engineering", {}), "project")
    apply_configuration(repository.get("engineering", {}), "repository")
    if task: apply_configuration(task.get("engineering", {}), "task")

    # Project context complements selected organization practices without pretending to be an organization rule.
    context = project.get("context", {})
    for category, key in (("convention", "conventions"), ("architecture", "architecture")):
        if category in categories and context.get(key):
            document = _local_document(project_root, context[key], "project")
            identifier = f"project-{category}"
            active[identifier] = {"metadata":{"id":identifier,"version":"1.0.0"},"category":category,"enforcement":"default","override":{"allowed":True},"_document":document}
            resolutions.append({"practice":identifier,"action":"complement","source":"project"})

    practices = []
    for identifier, practice in sorted(active.items()):
        source = next((candidate for candidate in ("task","repository","project") if any(item["practice"] == identifier and item["source"] == candidate for item in resolutions)),"organization")
        document = practice["_document"]
        content = document.read_text(encoding="utf-8")
        if practice.get("_base_document") and practice.get("inheritance", {}).get("strategy", "merge") == "merge":
            content = practice["_base_document"].read_text(encoding="utf-8").rstrip() + "\n\n# Project/repository specialization\n\n" + content.lstrip()
        content_hash=hashlib.sha256(content.encode()).hexdigest()
        provenance={"source":source,"document":str(document)}
        if practice.get("_manifest"): provenance["manifest"]=str(practice["_manifest"])
        item = {"id":identifier,"version":practice["metadata"]["version"],"category":practice["category"],"enforcement":practice["enforcement"],"source":source,"document":str(document),"content":content,"contentHash":content_hash,"provenance":provenance}
        if practice.get("_overrides"): item["overrides"] = practice["_overrides"]
        practices.append(item)
    task_context={key:task[key] for key in ("objective","scope","classification","constraints") if task and key in task}
    catalog_resolutions=[{"id":item["metadata"]["id"],"version":item["metadata"]["version"],"source":str(item["_manifest"]),"extends":item.get("extends",[])} for item in selected_catalogs]
    identity={"project":project["metadata"]["id"],"repository":repository_id,"skill":skill_id,
              "organizationCatalogs":[{"id":item["id"],"version":item["version"]} for item in catalog_resolutions],
              "profiles":[{"id":item["id"],"version":item["version"],"extends":item["extends"]} for item in profile_resolutions],"categories":categories,
              "practices":[{"id":item["id"],"version":item["version"],"source":item["source"],"contentHash":item["contentHash"]} for item in practices],"taskContext":task_context}
    fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return {"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"EffectiveEngineeringContext","metadata":{"id":f"{project['metadata']['id']}-{repository_id}-{skill_id}"},"project":project["metadata"]["id"],"repository":repository_id,"skill":skill_id,
            **({"task":task["metadata"]["id"]} if task else {}),"profiles":profile_ids,"profileResolutions":profile_resolutions,"organizationCatalogs":catalog_resolutions,"categories":categories,"practices":practices,"resolutions":resolutions,"taskContext":task_context,"fingerprint":fingerprint}


def validate_engineering_configuration(factory: Path, project_root: Path, project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try: catalog, _ = load_practices(factory, project.get("engineering", {}).get("organizationCatalogs", ["factory-default@1.0.0"]))
    except EngineeringContextError as exc: return [str(exc)]
    configurations = [("project", project.get("engineering", {}))]
    configurations.extend((f"repository {repository['id']}", repository.get("engineering", {})) for repository in project.get("repositories", []))
    for owner, configuration in configurations:
        for reference, selection in configuration.get("practices", {}).items():
            identifier, version = _parse_ref(reference)
            practice = catalog.get(identifier)
            mode = selection.get("mode")
            if practice is None:
                if mode != "enable" or not selection.get("ref") or not selection.get("category"):
                    errors.append(f"{owner}: unknown practice {identifier}; local practices require enable, ref and category")
                elif selection.get("ref"):
                    try: _local_document(project_root, selection["ref"], owner)
                    except EngineeringContextError as exc: errors.append(str(exc))
                continue
            actual = practice["metadata"]["version"]
            if version and version != actual: errors.append(f"{owner}: practice {identifier} requires version {version}, catalog provides {actual}")
            if mode == "disable" and practice["enforcement"] == "mandatory": errors.append(f"PRACTICE_CONFLICT: {owner} cannot disable mandatory practice {identifier}")
            if mode == "override":
                if practice["enforcement"] == "mandatory" or not practice["override"]["allowed"]: errors.append(f"PRACTICE_CONFLICT: {owner} cannot override protected practice {identifier}")
                elif selection.get("ref"):
                    try: _local_document(project_root, selection["ref"], owner)
                    except EngineeringContextError as exc: errors.append(str(exc))
    return errors
