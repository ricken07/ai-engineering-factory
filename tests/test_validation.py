from pathlib import Path

from aief.validation import validate_package


def test_package_is_valid():
    assert validate_package(Path(__file__).parents[1]) == []
