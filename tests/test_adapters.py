from pathlib import Path
from aief.adapters import INTENTS, adapter_mapping, select_workflow
ROOT = Path(__file__).parents[1]
INTENT_WORKFLOW = {
    "analyze":"analyze-task", "implement":"implement-task", "fix":"fix-bug",
    "refactor":"refactor-code", "test":"add-tests", "review":"review-change",
    "document":"update-documentation", "promote":"promote-knowledge",
}
def test_commands_and_language_select_same_workflow():
    assert select_workflow("/implement PROJ-142") == select_workflow("implement PROJ-142") == "implement-task"
def test_adapters_resolve_every_public_intent():
    for adapter in ("codex", "claude-code"):
        for workflow in INTENTS.values(): assert adapter_mapping(ROOT, adapter, workflow).is_file()


def test_native_skills_pin_intent_and_expected_workflow():
    for adapter in ("codex", "claude-code"):
        for intent, workflow in INTENT_WORKFLOW.items():
            instructions = (ROOT / "adapters" / adapter / "skills" / intent / "SKILL.md").read_text()
            assert f"--intent {intent}" in instructions
            assert f"--expect-workflow {workflow}" in instructions
            assert "Runtime receipt" in instructions


def test_runtime_protocol_forbids_unreceipted_mutation():
    for adapter in ("codex", "claude-code"):
        protocol = (ROOT / "adapters" / adapter / "runtime-protocol.md").read_text()
        assert "runtimeReceipt" in protocol
        assert "A textual\n   statement such as “Task normalized” is never a Runtime receipt" in protocol
        assert "implement-change" in protocol
        assert "skillContract.instructions" in protocol
        assert "`factory.yaml` inside the project workspace" in protocol
        assert "`$(pwd)`" in protocol
        assert "literal" in protocol
        assert '--output "<absolute-artifact-path>"' in protocol


def test_install_repoints_link_from_another_factory_but_refuses_foreign_paths(tmp_path):
    import shutil, pytest
    from aief.adapter_install import install_adapter
    other = tmp_path / "other"; shutil.copytree(ROOT / "adapters", other / "adapters")
    target = tmp_path / "skills"
    install_adapter(other, "claude-code", target)
    install_adapter(ROOT, "claude-code", target)
    assert (target / "analyze").resolve() == (ROOT / "adapters/claude-code/skills/analyze").resolve()
    (target / "fix").unlink(); (target / "fix").mkdir()
    with pytest.raises(FileExistsError): install_adapter(ROOT, "claude-code", target)
