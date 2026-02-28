"""Integration tests: MCP tools called with test project path (fixtures_dir).

All tests use DEMO_MODE=true (conftest) so no real HTTP. Response format (JSON keys,
types) is asserted. No LLM or paid APIs are used.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
            {"name": "requests", "version": "2.27.0", "ecosystem": "pypi"},
        ]
    )
    assert isinstance(result, dict)
    assert "error" not in result
    assert result["total_packages"] == 2
    assert len(result["licenses"]) == 2


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


def test_integration_check_policy_compliance_default_policy(fixtures_dir: Path) -> None:
    """check_policy_compliance with no policy uses default config."""
    result = check_policy_compliance(str(fixtures_dir))
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
