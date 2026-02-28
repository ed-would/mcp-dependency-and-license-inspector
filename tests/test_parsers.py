"""Unit tests for npm and pip parsers."""

import tempfile
from pathlib import Path

import pytest

from mcp_dependency_inspector.models.package import Ecosystem
from mcp_dependency_inspector.parsers.npm import parse_package_json, parse_package_lock_json
from mcp_dependency_inspector.parsers.pip import parse_pyproject_toml, parse_requirements_txt


# ---------------------------------------------------------------------------
# package.json tests
# ---------------------------------------------------------------------------


def test_parse_package_json_returns_packages(sample_package_json):
    packages, _ = parse_package_json(str(sample_package_json))
    names = {p.name for p in packages}
    assert "lodash" in names
    assert "express" in names
    for pkg in packages:
        assert pkg.ecosystem == Ecosystem.NPM


def test_parse_package_json_includes_dev_dependencies(sample_package_json):
    packages, _ = parse_package_json(str(sample_package_json))
    names = {p.name for p in packages}
    assert "jest" in names


def test_parse_package_json_license_map(sample_package_json):
    _, license_map = parse_package_json(str(sample_package_json))
    assert "sample-project" in license_map
    assert license_map["sample-project"] == "MIT"


def test_parse_package_json_legacy_licenses_array(tmp_path):
    """Legacy npm 'licenses': [{\"type\": \"MIT\"}] populates license_map when 'license' is absent."""
    pkg = {
        "name": "legacy-pkg",
        "version": "1.0.0",
        "licenses": [{"type": "MIT"}],
        "dependencies": {},
    }
    path = tmp_path / "package.json"
    import json
    path.write_text(json.dumps(pkg))
    _, license_map = parse_package_json(str(path))
    assert "legacy-pkg" in license_map
    assert license_map["legacy-pkg"] == "MIT"


def test_parse_package_json_legacy_licenses_array_multiple(tmp_path):
    """Legacy 'licenses': [{\"type\": \"MIT\"}, {\"type\": \"Apache-2.0\"}] → 'MIT OR Apache-2.0'."""
    import json
    pkg = {
        "name": "dual-license-pkg",
        "version": "1.0.0",
        "licenses": [{"type": "MIT"}, {"type": "Apache-2.0"}],
        "dependencies": {},
    }
    path = tmp_path / "package.json"
    path.write_text(json.dumps(pkg))
    _, license_map = parse_package_json(str(path))
    assert "dual-license-pkg" in license_map
    assert license_map["dual-license-pkg"] == "MIT OR Apache-2.0"


def test_parse_package_json_version_cleaned(sample_package_json):
    packages, _ = parse_package_json(str(sample_package_json))
    lodash = next(p for p in packages if p.name == "lodash")
    # ^ and ~ should be stripped, leaving the bare version
    assert not lodash.version.startswith("^")
    assert not lodash.version.startswith("~")
    assert lodash.version == "4.17.15"


def test_parse_nonexistent_file_returns_empty():
    packages, license_map = parse_package_json("/nonexistent/does_not_exist/package.json")
    assert packages == []
    assert license_map == {}


def test_parse_requirements_txt_returns_packages(sample_requirements_txt):
    packages = parse_requirements_txt(str(sample_requirements_txt))
    names = {p.name for p in packages}
    assert "requests" in names
    assert "flask" in names


def test_parse_requirements_txt_version_exact_pin(sample_requirements_txt):
    packages = parse_requirements_txt(str(sample_requirements_txt))
    req = next(p for p in packages if p.name == "requests")
    assert req.version == "2.27.0"


def test_parse_requirements_txt_skips_comments(sample_requirements_txt):
    packages = parse_requirements_txt(str(sample_requirements_txt))
    for pkg in packages:
        assert not pkg.name.startswith("#"), f"Comment leaked into packages: {pkg.name!r}"


def test_parse_requirements_txt_all_packages_are_pypi(sample_requirements_txt):
    packages = parse_requirements_txt(str(sample_requirements_txt))
    for pkg in packages:
        assert pkg.ecosystem == Ecosystem.PYPI


def test_parse_empty_requirements_returns_empty():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
        fh.write("# only a comment\n")
        fh.write("# another comment\n")
        tmp_path = fh.name

    packages = parse_requirements_txt(tmp_path)
    assert packages == []


def test_parse_requirements_txt_nonexistent_returns_empty():
    packages = parse_requirements_txt("/nonexistent/does_not_exist/requirements.txt")
    assert packages == []


# ---------------------------------------------------------------------------
# pyproject.toml tests
# ---------------------------------------------------------------------------


def test_parse_pyproject_toml_pep517(sample_pyproject_toml):
    packages, _ = parse_pyproject_toml(str(sample_pyproject_toml))
    names = {p.name for p in packages}
    assert "httpx" in names
    assert "pydantic" in names


def test_parse_pyproject_toml_poetry_deps(sample_pyproject_toml):
    packages, _ = parse_pyproject_toml(str(sample_pyproject_toml))
    names = {p.name for p in packages}
    assert "fastapi" in names


def test_parse_pyproject_toml_license(sample_pyproject_toml):
    _, license_map = parse_pyproject_toml(str(sample_pyproject_toml))
    # The project name "sample-py-project" should have Apache-2.0
    assert "sample-py-project" in license_map
    assert license_map["sample-py-project"] == "Apache-2.0"


def test_parse_pyproject_toml_nonexistent_returns_empty():
    packages, license_map = parse_pyproject_toml("/nonexistent/does_not_exist/pyproject.toml")
    assert packages == []
    assert license_map == {}


def test_parse_pyproject_toml_skips_python_dep(sample_pyproject_toml):
    packages, _ = parse_pyproject_toml(str(sample_pyproject_toml))
    names_lower = {p.name.lower() for p in packages}
    assert "python" not in names_lower


# ---------------------------------------------------------------------------
# package-lock.json tests
# ---------------------------------------------------------------------------


def test_parse_package_lock_json_nonexistent_returns_empty():
    packages = parse_package_lock_json("/nonexistent/package-lock.json")
    assert packages == []


def test_parse_package_lock_json_valid(tmp_path):
    lock_data = {
        "lockfileVersion": 2,
        "packages": {
            "": {"name": "root", "version": "1.0.0"},
            "node_modules/lodash": {"version": "4.17.21"},
            "node_modules/express": {"version": "4.18.2"},
        },
    }
    import json

    lock_file = tmp_path / "package-lock.json"
    lock_file.write_text(json.dumps(lock_data))

    packages = parse_package_lock_json(str(lock_file))
    names = {p.name for p in packages}
    assert "lodash" in names
    assert "express" in names
    # Root package "" should be skipped
    assert not any(p.name == "root" for p in packages)
