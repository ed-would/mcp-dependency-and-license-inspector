"""Report formatters: Markdown and JSON for dependency, license, vulnerability, and compliance data."""

from collections import defaultdict

from ..models.license_model import LicenseCategory, PackageLicense
from ..models.package import DependencyGraph
from ..models.policy import ComplianceReport
from ..models.vulnerability import Severity, VulnerabilityReport

_SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.UNKNOWN,
]


def format_dependency_summary(graph: DependencyGraph) -> str:
    """Return a Markdown report of packages grouped by ecosystem."""
    if not graph.packages:
        return "## Dependency Summary\n\nNo packages found.\n"

    lines = ["## Dependency Summary", ""]
    lines.append(
        f"**Total packages:** {len(graph.packages)} "
        f"({graph.direct_count} direct, {graph.transitive_count} transitive)"
    )
    lines.append("")

    # Ecosystem breakdown
    if graph.ecosystem_counts:
        lines.append("### Breakdown by Ecosystem")
        lines.append("")
        lines.append("| Ecosystem | Count |")
        lines.append("|-----------|-------|")
        for eco, count in sorted(graph.ecosystem_counts.items()):
            lines.append(f"| {eco} | {count} |")
        lines.append("")

    # Packages table grouped by ecosystem
    by_ecosystem: dict[str, list] = defaultdict(list)
    for pkg in graph.packages:
        by_ecosystem[pkg.ecosystem.value].append(pkg)

    for ecosystem in sorted(by_ecosystem.keys()):
        pkgs = sorted(by_ecosystem[ecosystem], key=lambda p: p.name.lower())
        lines.append(f"### {ecosystem.upper()} Packages")
        lines.append("")
        lines.append("| Name | Version | Direct |")
        lines.append("|------|---------|--------|")
        for pkg in pkgs:
            direct_label = "Yes" if pkg.direct else "No"
            lines.append(f"| {pkg.name} | {pkg.version} | {direct_label} |")
        lines.append("")

    return "\n".join(lines)


def format_license_report(licenses: list[PackageLicense]) -> str:
    """Return a Markdown table of package licenses with risk flags."""
    if not licenses:
        return "## License Report\n\nNo license data available.\n"

    lines = ["## License Report", ""]
    lines.append(f"**Packages analysed:** {len(licenses)}")
    lines.append("")
    lines.append("| Package | Version | Ecosystem | License | Category | Risk |")
    lines.append("|---------|---------|-----------|---------|----------|------|")

    for pl in sorted(licenses, key=lambda x: x.package.name.lower()):
        pkg = pl.package
        lic = pl.license
        spdx = lic.spdx_id or lic.name
        category = lic.category.value

        risk_flags = []
        if lic.is_copyleft:
            risk_flags.append("⚠ Copyleft")
        if lic.is_unknown:
            risk_flags.append("❓ Unknown")
        if lic.is_multiple:
            risk_flags.append("📋 Multiple")
        risk = ", ".join(risk_flags) if risk_flags else "✅ OK"

        lines.append(
            f"| {pkg.name} | {pkg.version} | {pkg.ecosystem.value} | {spdx} | {category} | {risk} |"
        )

    lines.append("")
    return "\n".join(lines)


def format_vulnerability_report(report: VulnerabilityReport) -> str:
    """Return a Markdown vulnerability report with summary counts and a CVE table."""
    lines = ["## Vulnerability Report", ""]
    lines.append(f"**Packages scanned:** {report.packages_scanned}")
    lines.append(f"**Vulnerabilities found:** {len(report.vulnerabilities)}")
    lines.append("")

    if report.counts_by_severity:
        lines.append("### Summary by Severity")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in _SEVERITY_ORDER:
            count = report.counts_by_severity.get(sev.value, 0)
            if count > 0:
                lines.append(f"| {sev.value.upper()} | {count} |")
        lines.append("")

    if not report.vulnerabilities:
        lines.append("No vulnerabilities found.")
        lines.append("")
        return "\n".join(lines)

    # Sort by severity (critical first), then by id
    sev_rank = {s.value: i for i, s in enumerate(_SEVERITY_ORDER)}
    sorted_vulns = sorted(
        report.vulnerabilities,
        key=lambda v: (sev_rank.get(v.severity.value, 99), v.id),
    )

    lines.append("### Vulnerabilities")
    lines.append("")
    lines.append("| CVE ID | Package | Version | Severity | Title | Fixed In |")
    lines.append("|--------|---------|---------|----------|-------|----------|")

    for vuln in sorted_vulns:
        fixed = vuln.fixed_version or "—"
        title = (vuln.title or vuln.description or "—")[:80]
        lines.append(
            f"| {vuln.id} | {vuln.package_name} | {vuln.package_version} "
            f"| {vuln.severity.value.upper()} | {title} | {fixed} |"
        )

    lines.append("")
    return "\n".join(lines)


def format_compliance_report(report: ComplianceReport) -> str:
    """Return a Markdown compliance report with overall status and violation details."""
    lines = ["## Compliance Report", ""]

    status_icon = "✅ COMPLIANT" if report.compliant else "❌ NON-COMPLIANT"
    lines.append(f"**Status:** {status_icon}")
    lines.append(f"**Packages checked:** {report.packages_checked}")
    lines.append(f"**Violations found:** {len(report.violations)}")
    lines.append("")

    if not report.violations:
        lines.append("No policy violations detected.")
        lines.append("")
        return "\n".join(lines)

    # Group violations by type
    by_type: dict[str, list] = defaultdict(list)
    for v in report.violations:
        by_type[v.type].append(v)

    for vtype in sorted(by_type.keys()):
        violations = by_type[vtype]
        type_label = {
            "license": "License Violations",
            "unknown_license": "Unknown License Violations",
            "cve": "CVE Violations",
        }.get(vtype, vtype.replace("_", " ").title())

        lines.append(f"### {type_label}")
        lines.append("")
        lines.append("| Package | Version | Details | Recommendation |")
        lines.append("|---------|---------|---------|----------------|")

        for v in violations:
            details = v.details.replace("|", "\\|")
            rec = v.recommendation.replace("|", "\\|") or "—"
            lines.append(f"| {v.package_name} | {v.package_version} | {details} | {rec} |")

        lines.append("")

    return "\n".join(lines)


# ─── JSON report generators (machine-readable summaries) ─────────────────────


def to_json_dependency_summary(graph: DependencyGraph) -> dict:
    """Return a JSON-serializable dependency summary (packages, counts, ecosystems)."""
    return {
        "total_packages": len(graph.packages),
        "direct_count": graph.direct_count,
        "transitive_count": graph.transitive_count,
        "ecosystem_counts": dict(graph.ecosystem_counts),
        "packages": [p.model_dump() for p in graph.packages],
    }


def to_json_license_report(licenses: list[PackageLicense]) -> dict:
    """Return a JSON-serializable license report with risk flags per package."""
    return {
        "total_packages": len(licenses),
        "licenses": [
            {
                "package": pl.package.model_dump(),
                "license": {
                    "spdx_id": pl.license.spdx_id,
                    "name": pl.license.name,
                    "category": pl.license.category.value,
                    "is_copyleft": pl.license.is_copyleft,
                    "is_unknown": pl.license.is_unknown,
                    "is_multiple": pl.license.is_multiple,
                },
            }
            for pl in licenses
        ],
    }


def to_json_vulnerability_report(report: VulnerabilityReport) -> dict:
    """Return a JSON-serializable vulnerability report."""
    return report.model_dump()


def to_json_compliance_report(report: ComplianceReport) -> dict:
    """Return a JSON-serializable compliance report (violations, status)."""
    return report.model_dump()
