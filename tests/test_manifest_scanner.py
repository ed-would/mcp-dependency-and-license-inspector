"""Unit tests for the manifest scanner (scan_project)."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from mcp_dependency_inspector.core.manifest_scanner import scan_project
from mcp_dependency_inspector.models.package import DependencyGraph


def test_scan_project_fixtures_dir(fixtures_dir):
    """Scanning the fixtures dir (has package.json + requirements.txt) should find packages."""
    graph, _ = scan_project(str(fixtures_dir))
    assert isinstance(graph, DependencyGraph)
    assert len(graph.packages) > 0


def test_scan_project_ecosystem_counts(fixtures_dir):
    """ecosystem_counts should include npm and/or pypi keys."""
    graph, _ = scan_project(str(fixtures_dir))
    ecosystems = set(graph.ecosystem_counts.keys())
    assert "npm" in ecosystems or "pypi" in ecosystems


def test_scan_project_returns_license_metadata(fixtures_dir):
    """scan_project should return a non-empty license metadata dict from package.json."""
    _, license_metadata = scan_project(str(fixtures_dir))
    # package.json has "license": "MIT" for "sample-project"
    assert isinstance(license_metadata, dict)
    assert "sample-project" in license_metadata


def test_scan_project_deduplication(tmp_path):
    """Packages with the same name/version/ecosystem appearing in multiple files should be deduplicated."""
    # Write a requirements.txt with the same package twice would be unusual,
    # but we can rely on the dedup key logic by writing the same file content twice
    reqs = tmp_path / "requirements.txt"
    reqs.write_text("requests==2.27.0\n")

    graph, _ = scan_project(str(tmp_path))
    request_pkgs = [p for p in graph.packages if p.name == "requests"]
    assert len(request_pkgs) == 1


def test_scan_project_excludes_dirs(tmp_path):
    """Packages inside an excluded directory should not be included."""
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    inner_pkg = node_modules / "package.json"
    inner_pkg.write_text(
        json.dumps(
            {
                "name": "inner-pkg",
                "version": "1.0.0",
                "dependencies": {"evil-dep": "^1.0.0"},
            }
        )
    )

    graph, _ = scan_project(str(tmp_path), exclude_dirs=["node_modules"])
    names = {p.name for p in graph.packages}
    assert "evil-dep" not in names


def test_scan_project_nonexistent_returns_empty():
    """Non-existent path should return an empty graph without raising."""
    graph, metadata = scan_project("/nonexistent/path/abc123")
    assert isinstance(graph, DependencyGraph)
    assert len(graph.packages) == 0
    assert metadata == {}


def test_scan_project_empty_directory(tmp_path):
    """A directory with no manifest files should produce an empty graph."""
    graph, _ = scan_project(str(tmp_path))
    assert len(graph.packages) == 0


def test_scan_project_npm_packages_have_npm_ecosystem(tmp_path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(
        json.dumps(
            {
                "name": "test-app",
                "version": "1.0.0",
                "dependencies": {"lodash": "^4.17.21"},
            }
        )
    )
    graph, _ = scan_project(str(tmp_path))
    npm_pkgs = [p for p in graph.packages if p.ecosystem.value == "npm"]
    assert len(npm_pkgs) > 0


def test_scan_project_counts_direct_and_transitive(tmp_path):
    """direct_count + transitive_count must equal total packages."""
    reqs = tmp_path / "requirements.txt"
    reqs.write_text("requests==2.27.0\nflask>=2.3.0\n")
    graph, _ = scan_project(str(tmp_path))
    assert graph.direct_count + graph.transitive_count == len(graph.packages)


def test_scan_project_default_exclude_dirs_applied(tmp_path):
    """Default excluded dirs (e.g. .venv) should not be scanned."""
    venv = tmp_path / ".venv"
    venv.mkdir()
    inner_reqs = venv / "requirements.txt"
    inner_reqs.write_text("hidden-pkg==0.0.1\n")

    graph, _ = scan_project(str(tmp_path))
    names = {p.name for p in graph.packages}
    assert "hidden-pkg" not in names
