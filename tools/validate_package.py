from pathlib import Path
import json, yaml
from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "core" / "schemas"

for path in SCHEMAS.glob("*.json"):
    Draft202012Validator.check_schema(json.loads(path.read_text()))

for path in ROOT.rglob("*.yaml"):
    yaml.safe_load(path.read_text())

skills = {p.parent.name for p in (ROOT / "core" / "skills").glob("*/skill.yaml")}
for wf in (ROOT / "core" / "workflows").glob("*/workflow.yaml"):
    data = yaml.safe_load(wf.read_text())
    for phase in data.get("phases", []):
        assert phase["skill"] in skills, f"Unknown skill {phase['skill']} in {wf}"

print("Factory package validation passed")
