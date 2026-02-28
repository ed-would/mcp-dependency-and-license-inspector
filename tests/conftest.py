"""Pytest configuration and fixtures. Ensures src/ is on PYTHONPATH when running tests without installing the package."""

import sys
from pathlib import Path

import pytest

# Allow running tests without pip install -e . (e.g. in CI or when Python >= 3.11 is not default)
_root = Path(__file__).resolve().parent.parent
_src = str(_root / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def set_demo_mode(monkeypatch):
    """Force DEMO_MODE=true for all tests so no real HTTP is needed."""
    monkeypatch.setenv("DEMO_MODE", "true")
    from mcp_dependency_inspector import config

    monkeypatch.setattr(config.settings, "demo_mode", True)
    yield


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_package_json(fixtures_dir) -> Path:
    return fixtures_dir / "package.json"


@pytest.fixture
def sample_requirements_txt(fixtures_dir) -> Path:
    return fixtures_dir / "requirements.txt"


@pytest.fixture
def sample_pyproject_toml(fixtures_dir) -> Path:
    return fixtures_dir / "pyproject.toml"


@pytest.fixture
def policy_yaml(fixtures_dir) -> Path:
    return fixtures_dir / "policy_deny_gpl.yaml"
