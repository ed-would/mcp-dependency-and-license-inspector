"""Unit tests for the policy engine."""

import pytest

from mcp_dependency_inspector.core.license_scanner import scan_licenses
from mcp_dependency_inspector.core.policy_engine import evaluate_compliance, load_policy
from mcp_dependency_inspector.models.license_model import LicenseCategory, LicenseInfo, PackageLicense
from mcp_dependency_inspector.models.package import DependencyGraph, Ecosystem, Package
from mcp_dependency_inspector.models.policy import ComplianceReport, PolicyConfig
from mcp_dependency_inspector.models.vulnerability import Severity, Vulnerability, VulnerabilityReport


def _make_package(name: str, version: str = "1.0.0", ecosystem: Ecosystem = Ecosystem.NPM) -> Package:
    return Package(name=name, version=version, ecosystem=ecosystem)


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


def _make_package_license(pkg: Package, license_str: str) -> PackageLicense:
    from mcp_dependency_inspector.core.license_scanner import get_license_info

    return PackageLicense(package=pkg, license=get_license_info(license_str))


def _empty_vuln_report(n: int = 0) -> VulnerabilityReport:
    from mcp_dependency_inspector.models.vulnerability import Severity

    return VulnerabilityReport(
        vulnerabilities=[],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=n,
    )


# ---------------------------------------------------------------------------
# load_policy tests
# ---------------------------------------------------------------------------


def test_load_policy_from_dict():
    policy = load_policy({"denied_licenses": ["GPL-3.0"], "block_critical_cve": True})
    assert isinstance(policy, PolicyConfig)
    assert "GPL-3.0" in policy.denied_licenses
    assert policy.block_critical_cve is True


def test_load_policy_defaults_when_empty_dict():
    policy = load_policy({})
    assert isinstance(policy, PolicyConfig)
    assert policy.block_critical_cve is True  # default
    assert policy.denied_licenses == []


def test_load_policy_from_yaml_file(policy_yaml):
    policy = load_policy(str(policy_yaml))
    assert "GPL-3.0" in policy.denied_licenses
    assert "AGPL-3.0" in policy.denied_licenses
    assert policy.block_critical_cve is True
    assert policy.block_high_cve is False


def test_load_policy_yaml_allowed_licenses(policy_yaml):
    policy = load_policy(str(policy_yaml))
    assert "MIT" in policy.allowed_licenses
    assert "Apache-2.0" in policy.allowed_licenses


def test_load_policy_nonexistent_file_returns_defaults(tmp_path):
    policy = load_policy(str(tmp_path / "nonexistent.yaml"))
    assert isinstance(policy, PolicyConfig)


# ---------------------------------------------------------------------------
# evaluate_compliance tests
# ---------------------------------------------------------------------------


def test_evaluate_compliance_clean():
    """All packages with allowed licenses and no vulns → compliant."""
    pkg1 = _make_package("lodash", "4.17.21")
    pkg2 = _make_package("express", "4.18.2")
    graph = _make_graph([pkg1, pkg2])
    pkg_licenses = [
        _make_package_license(pkg1, "MIT"),
        _make_package_license(pkg2, "MIT"),
    ]
    policy = load_policy({"denied_licenses": ["GPL-3.0"], "block_critical_cve": True})
    report = evaluate_compliance(graph, pkg_licenses, _empty_vuln_report(2), policy)
    assert report.compliant is True
    assert report.violations == []


def test_evaluate_compliance_denied_license():
    """A package with a denied license must produce a license violation."""
    pkg = _make_package("gpl-lib", "1.0.0")
    graph = _make_graph([pkg])
    pkg_licenses = [_make_package_license(pkg, "GPL-3.0")]
    policy = load_policy({"denied_licenses": ["GPL-3.0"]})
    report = evaluate_compliance(graph, pkg_licenses, _empty_vuln_report(1), policy)
    assert report.compliant is False
    assert any(v.type == "license" for v in report.violations)
    violation_names = [v.package_name for v in report.violations]
    assert "gpl-lib" in violation_names


def test_evaluate_compliance_critical_cve():
    """A critical CVE with block_critical_cve=True → compliant=False."""
    pkg = _make_package("vuln-pkg", "0.1.0")
    graph = _make_graph([pkg])
    pkg_licenses = [_make_package_license(pkg, "MIT")]
    policy = load_policy({"block_critical_cve": True})

    vuln = Vulnerability(
        id="CVE-2024-9999",
        package_name="vuln-pkg",
        package_version="0.1.0",
        ecosystem="npm",
        severity=Severity.CRITICAL,
        title="Critical test vuln",
    )
    vuln_report = VulnerabilityReport(
        vulnerabilities=[vuln],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=1,
    )
    vuln_report.counts_by_severity[Severity.CRITICAL.value] = 1

    report = evaluate_compliance(graph, pkg_licenses, vuln_report, policy)
    assert report.compliant is False
    assert any(v.type == "cve" for v in report.violations)


def test_evaluate_compliance_high_cve_not_blocked_by_default():
    """A HIGH CVE with block_high_cve=False should not block compliance."""
    pkg = _make_package("vuln-pkg", "0.1.0")
    graph = _make_graph([pkg])
    pkg_licenses = [_make_package_license(pkg, "MIT")]
    policy = load_policy({"block_critical_cve": True, "block_high_cve": False})

    vuln = Vulnerability(
        id="CVE-2024-HIGH",
        package_name="vuln-pkg",
        package_version="0.1.0",
        ecosystem="npm",
        severity=Severity.HIGH,
        title="High test vuln",
    )
    vuln_report = VulnerabilityReport(
        vulnerabilities=[vuln],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=1,
    )

    report = evaluate_compliance(graph, pkg_licenses, vuln_report, policy)
    assert report.compliant is True


def test_evaluate_compliance_high_cve_blocked_when_configured():
    """A HIGH CVE with block_high_cve=True should block compliance."""
    pkg = _make_package("vuln-pkg", "0.1.0")
    graph = _make_graph([pkg])
    pkg_licenses = [_make_package_license(pkg, "MIT")]
    policy = load_policy({"block_high_cve": True})

    vuln = Vulnerability(
        id="CVE-2024-HIGH",
        package_name="vuln-pkg",
        package_version="0.1.0",
        ecosystem="npm",
        severity=Severity.HIGH,
        title="High test vuln",
    )
    vuln_report = VulnerabilityReport(
        vulnerabilities=[vuln],
        counts_by_severity={s.value: 0 for s in Severity},
        packages_scanned=1,
    )

    report = evaluate_compliance(graph, pkg_licenses, vuln_report, policy)
    assert report.compliant is False
    assert any(v.type == "cve" for v in report.violations)


def test_evaluate_compliance_unknown_license_blocked():
    """With deny_unknown_license=True, packages with unknown license → violation."""
    pkg = _make_package("mystery-pkg", "2.0.0")
    graph = _make_graph([pkg])
    unknown_lic = LicenseInfo(
        spdx_id=None,
        name="Unknown",
        category=LicenseCategory.UNKNOWN,
        is_unknown=True,
    )
    pkg_licenses = [PackageLicense(package=pkg, license=unknown_lic)]
    policy = load_policy({"deny_unknown_license": True})

    report = evaluate_compliance(graph, pkg_licenses, _empty_vuln_report(1), policy)
    assert report.compliant is False
    assert any(v.type == "unknown_license" for v in report.violations)


def test_evaluate_compliance_unknown_license_allowed_when_not_blocked():
    """With deny_unknown_license=False, unknown license should not cause violation."""
    pkg = _make_package("mystery-pkg", "2.0.0")
    graph = _make_graph([pkg])
    unknown_lic = LicenseInfo(
        spdx_id=None,
        name="Unknown",
        category=LicenseCategory.UNKNOWN,
        is_unknown=True,
    )
    pkg_licenses = [PackageLicense(package=pkg, license=unknown_lic)]
    policy = load_policy({"deny_unknown_license": False, "allowed_licenses": []})

    report = evaluate_compliance(graph, pkg_licenses, _empty_vuln_report(1), policy)
    assert report.compliant is True


def test_evaluate_compliance_packages_checked_count():
    packages = [_make_package(f"pkg-{i}") for i in range(5)]
    graph = _make_graph(packages)
    pkg_licenses = [_make_package_license(p, "MIT") for p in packages]
    policy = load_policy({})
    report = evaluate_compliance(graph, pkg_licenses, _empty_vuln_report(5), policy)
    assert report.packages_checked == 5


def test_evaluate_compliance_no_vulns_none():
    """Passing vuln_report=None should not crash and should be compliant."""
    pkg = _make_package("safe-pkg", "1.0.0")
    graph = _make_graph([pkg])
    pkg_licenses = [_make_package_license(pkg, "MIT")]
    policy = load_policy({"block_critical_cve": True})

    report = evaluate_compliance(graph, pkg_licenses, None, policy)
    assert report.compliant is True


def test_evaluate_compliance_multiple_license_not_in_allowed_list():
    """When allowed_licenses is set, MULTIPLE (compound) license not in list → violation."""
    from mcp_dependency_inspector.core.license_scanner import get_license_info

    pkg = _make_package("dual-lic-pkg", "1.0.0")
    graph = _make_graph([pkg])
    # "MIT AND Apache-2.0" is classified as MULTIPLE, spdx_id=None
    multi_lic = get_license_info("MIT AND Apache-2.0")
    assert multi_lic.category == LicenseCategory.MULTIPLE
    pkg_licenses = [PackageLicense(package=pkg, license=multi_lic)]
    policy = load_policy({"allowed_licenses": ["MIT", "Apache-2.0"]})

    report = evaluate_compliance(graph, pkg_licenses, _empty_vuln_report(1), policy)
    assert report.compliant is False
    assert any(v.type == "license" for v in report.violations)
