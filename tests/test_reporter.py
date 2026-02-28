"""Unit tests for Markdown report formatters."""

import pytest

from mcp_dependency_inspector.core.reporter import (
    format_compliance_report,
    format_dependency_summary,
    format_license_report,
    format_vulnerability_report,
    to_json_compliance_report,
    to_json_dependency_summary,
    to_json_license_report,
    to_json_vulnerability_report,
)
from mcp_dependency_inspector.models.license_model import LicenseCategory, LicenseInfo, PackageLicense
from mcp_dependency_inspector.models.package import DependencyGraph, Ecosystem, Package
from mcp_dependency_inspector.models.policy import ComplianceReport, PolicyViolation
from mcp_dependency_inspector.models.vulnerability import Severity, Vulnerability, VulnerabilityReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph(packages: list[Package]) -> DependencyGraph:
    from collections import Counter

    eco_counts = Counter(p.ecosystem.value for p in packages)
    direct = sum(1 for p in packages if p.direct)
    transitive = len(packages) - direct
    return DependencyGraph(
        packages=packages,
        ecosystem_counts=dict(eco_counts),
        direct_count=direct,
        transitive_count=transitive,
    )


def _make_package_license(name: str, version: str, license_str: str) -> PackageLicense:
    from mcp_dependency_inspector.core.license_scanner import get_license_info

    pkg = Package(name=name, version=version, ecosystem=Ecosystem.NPM)
    return PackageLicense(package=pkg, license=get_license_info(license_str))


def _make_vuln(
    pkg_name: str = "vuln-pkg",
    pkg_version: str = "1.0.0",
    severity: Severity = Severity.HIGH,
    vuln_id: str = "CVE-2024-001",
) -> Vulnerability:
    return Vulnerability(
        id=vuln_id,
        package_name=pkg_name,
        package_version=pkg_version,
        ecosystem="npm",
        severity=severity,
        title=f"[Test] {severity.value} vulnerability",
        fixed_version="2.0.0",
    )


# ---------------------------------------------------------------------------
# format_dependency_summary
# ---------------------------------------------------------------------------


def test_format_dependency_summary_returns_markdown():
    packages = [
        Package(name="lodash", version="4.17.21", ecosystem=Ecosystem.NPM, direct=True),
        Package(name="express", version="4.18.2", ecosystem=Ecosystem.NPM, direct=False),
    ]
    graph = _make_graph(packages)
    result = format_dependency_summary(graph)
    assert isinstance(result, str)
    assert len(result) > 0
    # Should contain Markdown heading or table syntax
    assert "#" in result or "|" in result


def test_format_dependency_summary_contains_package_names():
    packages = [Package(name="lodash", version="4.17.21", ecosystem=Ecosystem.NPM, direct=True)]
    graph = _make_graph(packages)
    result = format_dependency_summary(graph)
    assert "lodash" in result


def test_format_dependency_summary_empty_graph():
    graph = _make_graph([])
    result = format_dependency_summary(graph)
    assert "No packages found" in result


def test_format_dependency_summary_counts():
    packages = [
        Package(name="a", version="1.0.0", ecosystem=Ecosystem.NPM, direct=True),
        Package(name="b", version="1.0.0", ecosystem=Ecosystem.NPM, direct=False),
    ]
    graph = _make_graph(packages)
    result = format_dependency_summary(graph)
    assert "2" in result  # total count
    assert "1" in result  # direct or transitive count


def test_format_dependency_summary_ecosystem_breakdown():
    packages = [
        Package(name="lodash", version="4.17.21", ecosystem=Ecosystem.NPM, direct=True),
        Package(name="requests", version="2.31.0", ecosystem=Ecosystem.PYPI, direct=True),
    ]
    graph = _make_graph(packages)
    result = format_dependency_summary(graph)
    assert "npm" in result.lower()
    assert "pypi" in result.lower()


# ---------------------------------------------------------------------------
# format_license_report
# ---------------------------------------------------------------------------


def test_format_license_report_contains_package_name():
    licenses = [_make_package_license("lodash", "4.17.21", "MIT")]
    result = format_license_report(licenses)
    assert "lodash" in result


def test_format_license_report_contains_license():
    licenses = [_make_package_license("lodash", "4.17.21", "MIT")]
    result = format_license_report(licenses)
    assert "MIT" in result or "mit" in result.lower()


def test_format_license_report_copyleft_flagged():
    licenses = [_make_package_license("gpl-lib", "1.0.0", "GPL-3.0")]
    result = format_license_report(licenses)
    assert "Copyleft" in result or "copyleft" in result.lower()


def test_format_license_report_empty():
    result = format_license_report([])
    assert "No license data" in result


def test_format_license_report_multiple_packages():
    licenses = [
        _make_package_license("lodash", "4.17.21", "MIT"),
        _make_package_license("gpl-lib", "1.0.0", "GPL-3.0"),
    ]
    result = format_license_report(licenses)
    assert "lodash" in result
    assert "gpl-lib" in result


# ---------------------------------------------------------------------------
# format_vulnerability_report
# ---------------------------------------------------------------------------


def test_format_vulnerability_report_shows_severity():
    vuln = _make_vuln(severity=Severity.HIGH)
    report = VulnerabilityReport(
        vulnerabilities=[vuln],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=1,
    )
    report.counts_by_severity[Severity.HIGH.value] = 1
    result = format_vulnerability_report(report)
    assert "high" in result.lower()


def test_format_vulnerability_report_shows_critical():
    vuln = _make_vuln(severity=Severity.CRITICAL)
    report = VulnerabilityReport(
        vulnerabilities=[vuln],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=1,
    )
    report.counts_by_severity[Severity.CRITICAL.value] = 1
    result = format_vulnerability_report(report)
    assert "critical" in result.lower()


def test_format_vulnerability_report_empty():
    report = VulnerabilityReport(
        vulnerabilities=[],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=3,
    )
    result = format_vulnerability_report(report)
    assert "No vulnerabilities found" in result


def test_format_vulnerability_report_shows_cve_id():
    vuln = _make_vuln(vuln_id="CVE-2024-12345")
    report = VulnerabilityReport(
        vulnerabilities=[vuln],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=1,
    )
    result = format_vulnerability_report(report)
    assert "CVE-2024-12345" in result


def test_format_vulnerability_report_shows_package_name():
    vuln = _make_vuln(pkg_name="evil-package")
    report = VulnerabilityReport(
        vulnerabilities=[vuln],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=1,
    )
    result = format_vulnerability_report(report)
    assert "evil-package" in result


# ---------------------------------------------------------------------------
# format_compliance_report
# ---------------------------------------------------------------------------


def test_format_compliance_report_compliant_true():
    report = ComplianceReport(compliant=True, violations=[], packages_checked=5)
    result = format_compliance_report(report)
    assert "✅" in result or "COMPLIANT" in result or "compliant" in result.lower()


def test_format_compliance_report_non_compliant():
    violation = PolicyViolation(
        type="license",
        package_name="gpl-lib",
        package_version="1.0.0",
        details="GPL-3.0 is denied",
    )
    report = ComplianceReport(compliant=False, violations=[violation], packages_checked=3)
    result = format_compliance_report(report)
    assert "❌" in result or "NON-COMPLIANT" in result or "non-compliant" in result.lower()


def test_format_compliance_report_shows_violation_details():
    violation = PolicyViolation(
        type="license",
        package_name="gpl-lib",
        package_version="1.0.0",
        details="GPL-3.0 is denied",
    )
    report = ComplianceReport(compliant=False, violations=[violation], packages_checked=1)
    result = format_compliance_report(report)
    assert "gpl-lib" in result


def test_format_compliance_report_packages_checked():
    report = ComplianceReport(compliant=True, violations=[], packages_checked=42)
    result = format_compliance_report(report)
    assert "42" in result


def test_format_compliance_report_no_violations_message():
    report = ComplianceReport(compliant=True, violations=[], packages_checked=5)
    result = format_compliance_report(report)
    assert "No policy violations" in result or "compliant" in result.lower()


def test_format_compliance_report_cve_violation():
    violation = PolicyViolation(
        type="cve",
        package_name="vuln-pkg",
        package_version="0.1.0",
        details="Critical CVE-2024-9999",
    )
    report = ComplianceReport(compliant=False, violations=[violation], packages_checked=1)
    result = format_compliance_report(report)
    assert "vuln-pkg" in result
    assert "CVE" in result or "cve" in result.lower()


# ---------------------------------------------------------------------------
# JSON report functions
# ---------------------------------------------------------------------------


def test_to_json_dependency_summary():
    packages = [
        Package(name="lodash", version="4.17.21", ecosystem=Ecosystem.NPM, direct=True),
        Package(name="express", version="4.18.2", ecosystem=Ecosystem.NPM, direct=False),
    ]
    graph = _make_graph(packages)
    result = to_json_dependency_summary(graph)
    assert result["total_packages"] == 2
    assert result["direct_count"] == 1
    assert result["transitive_count"] == 1
    assert len(result["packages"]) == 2
    assert result["ecosystem_counts"]["npm"] == 2


def test_to_json_license_report():
    licenses = [
        _make_package_license("lodash", "4.17.21", "MIT"),
        _make_package_license("gpl-lib", "1.0.0", "GPL-3.0"),
    ]
    result = to_json_license_report(licenses)
    assert result["total_packages"] == 2
    assert len(result["licenses"]) == 2
    assert result["licenses"][0]["package"]["name"] == "lodash"
    assert "category" in result["licenses"][0]["license"]


def test_to_json_vulnerability_report():
    vuln = _make_vuln(vuln_id="CVE-2024-001")
    report = VulnerabilityReport(
        vulnerabilities=[vuln],
        counts_by_severity={Severity.HIGH.value: 1, Severity.CRITICAL.value: 0},
        packages_scanned=1,
    )
    result = to_json_vulnerability_report(report)
    assert result["packages_scanned"] == 1
    assert len(result["vulnerabilities"]) == 1
    assert result["vulnerabilities"][0]["id"] == "CVE-2024-001"


def test_to_json_compliance_report():
    report = ComplianceReport(
        compliant=False,
        violations=[
            PolicyViolation(
                type="license",
                package_name="gpl-lib",
                package_version="1.0.0",
                details="GPL-3.0 denied",
                recommendation="Replace with MIT alternative",
            )
        ],
        packages_checked=5,
    )
    result = to_json_compliance_report(report)
    assert result["compliant"] is False
    assert result["packages_checked"] == 5
    assert len(result["violations"]) == 1
    assert result["violations"][0]["package_name"] == "gpl-lib"
