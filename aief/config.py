"""Factory configuration utilities - single source of truth."""

from pathlib import Path
import yaml


def load_factory_config(factory_path: Path) -> dict:
    """Load factory.yaml and return the configuration."""
    factory_file = factory_path / "factory.yaml"
    if not factory_file.is_file():
        raise FileNotFoundError(f"factory.yaml not found at {factory_file}")
    return yaml.safe_load(factory_file.read_text(encoding="utf-8"))


def get_api_version(factory_path: Path) -> str:
    """Get the apiVersion from factory.yaml - single source of truth.

    All AIEF artifacts must use the version declared in factory.yaml.
    This ensures consistency across all generated documents.
    """
    config = load_factory_config(factory_path)
    api_version = config.get("apiVersion")
    if not api_version:
        raise ValueError("apiVersion not defined in factory.yaml")
    return api_version


def get_factory_version(factory_path: Path) -> str:
    """Get the Factory version from factory.yaml metadata."""
    config = load_factory_config(factory_path)
    factory_version = config.get("metadata", {}).get("version")
    if not factory_version:
        raise ValueError("metadata.version not defined in factory.yaml")
    return factory_version
