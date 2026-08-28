import yaml
from aief.knowledge import approve_candidate, create_task_memory, verify_approval

def candidate():
    return {"apiVersion":"aief.dev/v1alpha1","kind":"MemoryCandidate","metadata":{"id":"MC-1"},"sourceTask":"TASK-1","statement":"Use normalized errors.","evidence":["validation.yaml"],"target":"project-memory","status":"proposed"}

def test_task_memory_is_agent_neutral_and_reusable(tmp_path):
    path = create_task_memory(tmp_path, "TASK-1")
    assert yaml.safe_load(path.read_text())["task"] == "TASK-1"
    assert create_task_memory(tmp_path, "TASK-1") == path

def test_approval_is_bound_to_candidate_content_and_target():
    value = candidate(); promotion = approve_candidate(value, "reviewer")
    assert verify_approval(value, promotion)
    value["statement"] = "Changed after approval."
    assert not verify_approval(value, promotion)
