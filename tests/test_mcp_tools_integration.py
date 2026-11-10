"""Integration tests: MCP tools called with test project path (fixtures_dir).

All tests use DEMO_MODE=true (conftest) so no real HTTP. Response format (JSON keys,
types) is asserted. No LLM or paid APIs are used.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore, Event
from typing import Never

import pytest

from mcp_dependency_inspector import server
from mcp_dependency_inspector.core import vulnerability_scanner
from mcp_dependency_inspector.models.package import DependencyGraph, Package
from mcp_dependency_inspector.server import (
    analyze_project_dependencies,
    check_policy_compliance,
    generate_sbom,
    scan_licenses_tool,
    scan_vulnerabilities_tool,
    suggest_dependency_replacements,
)

# ---------------------------------------------------------------------------
# analyze_project_dependencies
# ---------------------------------------------------------------------------


def test_integration_analyze_project_dependencies(fixtures_dir: Path) -> None:
    """Call analyze_project_dependencies on fixtures dir; assert response structure."""
    result = analyze_project_dependencies(str(fixtures_dir))
    assert isinstance(result, dict)
    assert "summary" in result
    assert isinstance(result["summary"], str)
    assert "total_packages" in result
    assert isinstance(result["total_packages"], int)
    assert result["total_packages"] >= 0
    assert "direct_count" in result
    assert "transitive_count" in result
    assert "ecosystem_counts" in result
    assert isinstance(result["ecosystem_counts"], dict)
    assert "packages" in result
    assert isinstance(result["packages"], list)
    for p in result["packages"]:
        assert "name" in p
        assert "version" in p
        assert "ecosystem" in p
    assert result["total_packages"] == len(result["packages"])


def test_integration_analyze_project_dependencies_has_npm_or_pypi(fixtures_dir: Path) -> None:
    """Fixtures contain package.json and requirements.txt so at least one ecosystem."""
    result = analyze_project_dependencies(str(fixtures_dir))
    ecosystems = set(result["ecosystem_counts"].keys())
    assert "npm" in ecosystems or "pypi" in ecosystems


# ---------------------------------------------------------------------------
# scan_vulnerabilities_tool
# ---------------------------------------------------------------------------


def test_integration_scan_vulnerabilities_tool(fixtures_dir: Path) -> None:
    """Call scan_vulnerabilities_tool; assert JSON structure (DEMO_MODE returns stubs)."""
    result = scan_vulnerabilities_tool(str(fixtures_dir))
    assert isinstance(result, dict)
    assert "summary" in result
    assert isinstance(result["summary"], str)
    assert "counts_by_severity" in result
    assert isinstance(result["counts_by_severity"], dict)
    assert "packages_scanned" in result
    assert isinstance(result["packages_scanned"], int)
    assert "vulnerabilities" in result
    assert isinstance(result["vulnerabilities"], list)
    assert "demo_mode" in result
    for v in result["vulnerabilities"]:
        assert "id" in v
        assert "package_name" in v
        assert "package_version" in v
        assert "severity" in v


# ---------------------------------------------------------------------------
# scan_licenses_tool
# ---------------------------------------------------------------------------


def test_integration_scan_licenses_tool_project_path(fixtures_dir: Path) -> None:
    """Call scan_licenses_tool with project_path; assert response format."""
    result = scan_licenses_tool(project_path=str(fixtures_dir))
    assert isinstance(result, dict)
    assert "error" not in result
    assert "summary" in result
    assert isinstance(result["summary"], str)
    assert "total_packages" in result
    assert isinstance(result["total_packages"], int)
    assert "licenses" in result
    assert isinstance(result["licenses"], list)
    for lic in result["licenses"]:
        assert "package" in lic
        assert "version" in lic
        assert "ecosystem" in lic
        assert "license" in lic
        assert "category" in lic
        assert "is_copyleft" in lic
        assert "is_unknown" in lic


def test_integration_scan_licenses_tool_packages_list() -> None:
    """Call scan_licenses_tool with explicit packages list."""
    result = scan_licenses_tool(
        packages=[
            {"name": "lodash", "version": "4.17.21", "ecosystem": "npm"},
            {"name": "requests", "version": "2.27.0"},
        ]
    )
    assert isinstance(result, dict)
    assert "error" not in result
    assert result["total_packages"] == 2
    assert len(result["licenses"]) == 2
    assert result["licenses"][1]["ecosystem"] == "unknown"


@pytest.mark.parametrize(
    ("package", "error_path"),
    [
        (None, "packages[1]"),
        ({}, "packages[1].name"),
        ({"name": " "}, "packages[1].name"),
        ({"name": None}, "packages[1].name"),
        ({"name": "dep", "ecosystem": "typo"}, "packages[1].ecosystem"),
    ],
)
def test_integration_scan_licenses_rejects_invalid_package(
    package: dict[str, str | None] | None, error_path: str
) -> None:
    result = scan_licenses_tool(packages=[{"name": "valid", "ecosystem": "npm"}, package])

    assert result["success"] is False
    assert error_path in result["error"]
    assert "licenses" not in result


def test_integration_scan_licenses_tool_error_when_no_input() -> None:
    """Neither project_path nor packages → error message."""
    result = scan_licenses_tool()
    assert isinstance(result, dict)
    assert "error" in result


# ---------------------------------------------------------------------------
# check_policy_compliance
# ---------------------------------------------------------------------------


def test_integration_check_policy_compliance(fixtures_dir: Path, policy_yaml: Path) -> None:
    """Call check_policy_compliance with project path and policy file."""
    result = check_policy_compliance(str(fixtures_dir), policy=str(policy_yaml))
    assert isinstance(result, dict)
    assert "summary" in result
    assert isinstance(result["summary"], str)
    assert "compliant" in result
    assert isinstance(result["compliant"], bool)
    assert "packages_checked" in result
    assert isinstance(result["packages_checked"], int)
    assert "violations_count" in result
    assert "violations" in result
    assert isinstance(result["violations"], list)
    assert "demo_mode" in result
    for v in result["violations"]:
        assert "type" in v
        assert "package_name" in v
        assert "package_version" in v
        assert "details" in v


@pytest.mark.parametrize("policy", [None, ""])
def test_integration_check_policy_compliance_default_policy(
    fixtures_dir: Path, policy: str | None
) -> None:
    """Missing and blank policy inputs both use the default config."""
    result = check_policy_compliance(str(fixtures_dir), policy=policy)
    assert "compliant" in result
    assert "violations" in result


def test_integration_check_policy_compliance_policy_dict(fixtures_dir: Path) -> None:
    """check_policy_compliance accepts policy as dict."""
    result = check_policy_compliance(
        str(fixtures_dir),
        policy={"denied_licenses": ["GPL-3.0"], "block_critical_cve": True},
    )
    assert "compliant" in result
    assert "violations" in result


def test_integration_osv_failure_leaves_audit_incomplete(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_packages: list[Package]) -> Never:
        raise OSError("test OSV failure")

    monkeypatch.setattr(server.settings, "demo_mode", False)
    monkeypatch.setattr(vulnerability_scanner, "_query_osv_batch", unavailable)
    monkeypatch.setattr(server, "_last_report", None)

    scan = scan_vulnerabilities_tool(str(fixtures_dir))
    audit = check_policy_compliance(str(fixtures_dir))
    resource = json.loads(server.resource_report_latest())

    assert scan["vulnerability_scan_status"] == "unavailable"
    assert scan["demo_mode"] is False
    assert scan["vulnerabilities"] == []
    assert scan["packages_scanned"] == 0
    for report in (audit, resource):
        assert report["vulnerability_scan_status"] == "unavailable"
        assert report["compliant"] is False
        assert report["violations"] == []
        assert "INCOMPLETE" in report["summary"].upper()


@pytest.mark.parametrize(
    ("argument", "filename", "message"),
    [
        ("policy_path", "link.json", "not under allowed base directory"),
        ("policy", "missing.json", "Cannot resolve policy file"),
        ("policy_path", "broken.json", "Cannot load policy file"),
    ],
)
def test_integration_check_rejects_bad_policy_before_scanning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argument: str, filename: str, message: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside_policy = tmp_path / "outside.json"
    outside_policy.write_text("{}", encoding="utf-8")
    (project / "link.json").symlink_to(outside_policy)
    (project / "broken.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr(server.settings, "allowed_base_path", str(project))

    def unexpected_scan(*args: object, **kwargs: object) -> None:
        pytest.fail("Project scan started before the policy was validated")

    monkeypatch.setattr(server, "scan_project", unexpected_scan)

    with pytest.raises(ValueError, match=message):
        check_policy_compliance(str(project), **{argument: str(project / filename)})


@pytest.mark.parametrize(
    ("tool_name", "resource_name"),
    [
        ("check_policy_compliance", "resource_report_latest"),
        ("generate_sbom", "resource_sbom_latest_spdx"),
    ],
)
def test_timeout_returns_while_worker_is_busy_and_preserves_latest(
    fixtures_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    resource_name: str,
) -> None:
    call = getattr(server, tool_name)
    latest = getattr(server, resource_name)
    slow_project = tmp_path / "slow"
    slow_project.mkdir()
    started, release, finished = Event(), Event(), Event()
    scan = server.scan_project

    def controlled_scan(
        project_path: str, exclude_dirs: list[str] | None
    ) -> tuple[DependencyGraph, dict[str, str]]:
        if Path(project_path) == slow_project.resolve():
            started.set()
            release.wait(timeout=5)
            finished.set()
        return scan(project_path, exclude_dirs)

    monkeypatch.setattr(server, "scan_project", controlled_scan)
    monkeypatch.setattr(server, "_last_report", None)
    monkeypatch.setattr(server, "_last_sboms", {})
    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(server, "_tool_executor", executor)
        monkeypatch.setattr(server, "_tool_slots", BoundedSemaphore(1))
        call(str(fixtures_dir))
        previous = latest()
        monkeypatch.setattr(server.settings, "tool_timeout_seconds", 0.2)
        try:
            with pytest.raises(ValueError, match="timed out"):
                call(str(slow_project))
            assert started.is_set() and not finished.is_set()
            with pytest.raises(ValueError, match="workers are busy"):
                call(str(fixtures_dir))
        finally:
            release.set()
        executor.submit(lambda: None).result(timeout=5)
        assert latest() == previous
        monkeypatch.setattr(server.settings, "tool_timeout_seconds", 5)
        call(str(fixtures_dir))


# ---------------------------------------------------------------------------
# generate_sbom
# ---------------------------------------------------------------------------


def test_integration_generate_sbom_spdx(fixtures_dir: Path) -> None:
    """Generate SPDX SBOM; assert structure."""
    result = generate_sbom(str(fixtures_dir), format="spdx")
    assert isinstance(result, dict)
    assert "error" not in result
    assert result["format"] == "spdx"
    assert "package_count" in result
    assert "sbom" in result
    sbom = result["sbom"]
    assert isinstance(sbom, dict)
    assert sbom.get("spdxVersion") == "SPDX-2.3"
    assert "packages" in sbom
    assert isinstance(sbom["packages"], list)
    assert len(sbom["packages"]) == result["package_count"]


def test_integration_generate_sbom_cyclonedx(fixtures_dir: Path) -> None:
    """Generate CycloneDX SBOM; assert structure."""
    result = generate_sbom(str(fixtures_dir), format="cyclonedx")
    assert isinstance(result, dict)
    assert "error" not in result
    assert result["format"] == "cyclonedx"
    assert "package_count" in result
    assert "sbom" in result
    sbom = result["sbom"]
    assert isinstance(sbom, dict)
    assert sbom.get("bomFormat") == "CycloneDX"
    assert "components" in sbom
    assert isinstance(sbom["components"], list)
    assert len(sbom["components"]) == result["package_count"]


def test_integration_generate_sbom_invalid_format(fixtures_dir: Path) -> None:
    """Unknown format returns error dict."""
    result = generate_sbom(str(fixtures_dir), format="invalid")
    assert "error" in result


# ---------------------------------------------------------------------------
# suggest_dependency_replacements
# ---------------------------------------------------------------------------


def test_integration_suggest_dependency_replacements() -> None:
    """Call suggest_dependency_replacements; assert structure (stub in DEMO_MODE)."""
    result = suggest_dependency_replacements(
        [
            {"name": "lodash", "version": "4.17.15", "reason": "cve"},
            {"name": "requests", "version": "2.27.0", "reason": "license"},
        ]
    )
    assert isinstance(result, dict)
    assert "results" in result
    assert isinstance(result["results"], list)
    assert len(result["results"]) == 2
    for r in result["results"]:
        assert "package" in r
        assert "version" in r
        assert "reason" in r
        assert "alternatives" in r
        assert isinstance(r["alternatives"], list)


def test_integration_suggest_dependency_replacements_wrapped_list() -> None:
    """Accept packages sent as [[{...}, {...}]] (e.g. by MCP Inspector)."""
    result = suggest_dependency_replacements(
        [
            [
                {"name": "lodash", "version": "4.17.15", "ecosystem": "npm", "reason": "cve"},
                {"name": "requests", "version": "2.27.0", "ecosystem": "pypi", "reason": "cve"},
            ]
        ]
    )
    assert isinstance(result, dict)
    assert "results" in result
    assert len(result["results"]) == 2
    for r in result["results"]:
        for alt in r["alternatives"]:
            assert "name" in alt
            assert "version" in alt
            assert "license" in alt
            assert "reason" in alt
    assert result.get("demo_mode") is True


# ---------------------------------------------------------------------------
# Error handling: invalid path
# ---------------------------------------------------------------------------


def test_integration_analyze_project_nonexistent_path() -> None:
    """Non-existent project path raises ValueError."""
    with pytest.raises(ValueError, match="Path does not exist|not a directory"):
        analyze_project_dependencies("/nonexistent/path/xyz")


def test_integration_generate_sbom_nonexistent_path() -> None:
    """generate_sbom with non-existent path raises ValueError."""
    with pytest.raises(ValueError, match="Path does not exist|not a directory"):
        generate_sbom("/nonexistent/path/xyz", format="spdx")
