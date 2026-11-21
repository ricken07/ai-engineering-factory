"""Phase brief: the instructions an agent must read before producing a phase output.

`execution next` used to return every EffectiveEngineeringContext inline, with
the full text of each practice repeated per repository. Agents whose tools
truncate large command outputs could then miss the practices. The brief is a
single Markdown file written next to the execution, with each practice once,
so an agent can read it completely; the command output only points to it.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _practices(contexts: list[dict[str, Any]]) -> list[tuple[dict[str, Any], list[str]]]:
    seen: dict[tuple[str, str], tuple[dict[str, Any], list[str]]] = {}
    for context in contexts:
        for practice in context.get("practices", []):
            key = (practice["id"], practice.get("contentHash", ""))
            entry = seen.setdefault(key, (practice, []))
            entry[1].append(context["repository"])
    return list(seen.values())


def render_phase_brief(phase: dict[str, Any], skill_contract: dict[str, Any], contexts: list[dict[str, Any]]) -> str:
    lines = [f"# Phase brief: {phase['id']} ({phase['skill']})", "",
             "Read this file completely before producing the phase output.", "",
             "## Skill contract", "",
             f"- Instructions: `{skill_contract['instructions']}`",
             f"- Manifest: `{skill_contract['manifest']}`",
             f"- Output schema: `{skill_contract['outputSchema']}`"]
    for contract in skill_contract.get("outputContracts", []):
        lines.append(f"- Output contract ({contract['source']}): `{contract['schema']}`")
    rework = phase.get("rework")
    if rework:
        lines += ["", f"## Rework {rework['number']}: address the review findings", "",
                  f"The independent review did not approve the previous implementation (decision "
                  f"`{rework.get('decision')}`; report `{rework['review']}` in the execution directory).",
                  "Address every finding below, then the change is validated and reviewed again. Do not",
                  "reduce the acceptance criteria to fit the implementation; if a criterion itself is wrong,",
                  "ask the human."]
        for finding in rework.get("findings", []):
            if isinstance(finding, dict):
                label = " ".join(str(finding[key]) for key in ("severity", "criterion") if finding.get(key))
                lines += ["", f"- **{label or 'finding'}** {finding.get('location', '')}".rstrip(),
                          f"  - {finding.get('finding', '')}".rstrip()]
                if finding.get("correction"):
                    lines.append(f"  - Expected correction: {finding['correction']}")
            else:
                lines += ["", f"- {finding}"]
    if phase.get("action") == "propose-change":
        lines += ["", "## Authorized action: propose-change", "",
                  "Authorized autonomy denies `modify-local-files`: do not create, edit or delete any file of the",
                  "repositories. The Runtime fingerprinted the workspace when this phase started and rejects the",
                  "output if it changed. Write the change as unified diffs (paths relative to the repository's Git",
                  "root, as `git diff` prints them from there) in files inside the execution directory, and list them",
                  "in `details.proposal.patches` as `{repository, path}`. A human approves the `apply-proposal` gate;",
                  "the Runtime then applies the patches before validation.", "",
                  "Before completing the phase, check the proposal with `aief execution check-proposal <id>",
                  "--output <draft-output> --owner <owner>`: the Runtime applies the patches to a disposable copy,",
                  "runs the validation commands there and reports the result. Fix the patches until it passes."]
    if not contexts:
        lines += ["", "No engineering context applies to this phase."]
        return "\n".join(lines) + "\n"
    lines += ["", "## Repositories", ""]
    for context in contexts:
        lines.append(f"- `{context['repository']}`: profiles {', '.join(context.get('profiles', [])) or 'none'}; "
                     f"context `{context['metadata']['id']}` ({context.get('fingerprint', '')[:16]})")
    task = next((context.get("taskContext") for context in contexts if context.get("taskContext")), None)
    if task:
        lines += ["", "## Task context", ""]
        lines += [f"- {key}: {value}" for key, value in task.items()]
    lines += ["", "## Practices", "",
              "Each practice applies to the repositories listed with it. Follow every one of them."]
    for practice, repositories in _practices(contexts):
        lines += ["", f"### {practice['id']} {practice.get('version', '')}".rstrip(), "",
                  f"Applies to: {', '.join(f'`{item}`' for item in repositories)}. "
                  f"Category: {practice.get('category')}. Enforcement: {practice.get('enforcement')}.", "",
                  practice.get("content", "").strip()]
    return "\n".join(lines) + "\n"


def write_phase_brief(root: Path, phase: dict[str, Any], skill_contract: dict[str, Any], contexts: list[dict[str, Any]]) -> dict[str, Any]:
    text = render_phase_brief(phase, skill_contract, contexts)
    path = root / f"phase-brief-{phase['id']}.md"
    path.write_text(text, encoding="utf-8")
    content = text.encode("utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def compact_prepared(data: dict[str, Any]) -> dict[str, Any]:
    """Command output of `execution next`: contexts by reference, brief by path."""
    compact = dict(data)
    compact["engineeringContexts"] = [
        {"repository": item["repository"], "id": item["metadata"]["id"], "fingerprint": item.get("fingerprint")}
        for item in data.get("engineeringContexts", [])
    ]
    return compact
