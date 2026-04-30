import yaml
from aief.runtime import Execution

def test_execution_persists_resumes_and_handoffs(tmp_path):
    workflow = {"metadata":{"id":"demo"},"phases":[{"id":"read","skill":"understand-task"},{"id":"write","skill":"implement-change","gate":{"id":"approval"}}]}
    execution = Execution.create(tmp_path, workflow, "TASK-1")
    assert execution.advance({"summary":"ok"}) == "running"
    assert execution.advance() == "waiting-approval"
    resumed = Execution.load(execution.root)
    assert resumed.advance(approved=True) == "completed"
    assert yaml.safe_load(resumed.handoff().read_text())["status"] == "completed"
