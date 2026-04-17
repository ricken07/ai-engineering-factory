from pathlib import Path
from aief.validation import validate_package

root = Path(__file__).resolve().parents[1]
issues = validate_package(root)
for issue in issues:
    print(f"{issue.path}: {issue.message}")
if issues:
    raise SystemExit(1)
print("Factory package validation passed")
