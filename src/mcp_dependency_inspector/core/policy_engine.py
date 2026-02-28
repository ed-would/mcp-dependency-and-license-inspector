"""Policy compliance evaluation."""

import json
import logging
from pathlib import Path

from ..models.license_model import LicenseCategory, PackageLicense
from ..models.package import DependencyGraph
from ..models.policy import ComplianceReport, PolicyConfig, PolicyViolation
from ..models.vulnerability import Severity, VulnerabilityReport

logger = logging.getLogger(__name__)


def load_policy(policy_input: dict | str) -> PolicyConfig:
    """Load PolicyConfig from a dict or a YAML/JSON file path."""
    if isinstance(policy_input, dict):
        return PolicyConfig(**policy_input)

    path = Path(policy_input)
    if not path.exists():
        logger.warning("Policy file not found: %s — using defaults", path)
        return PolicyConfig()

    suffix = path.suffix.lower()
    try:
        if suffix in (".yaml", ".yml"):
            from ruamel.yaml import YAML

            yaml = YAML(typ="safe")
            with path.open("r", encoding="utf-8") as fh:
                data = yaml.load(fh) or {}
            return PolicyConfig(**data)

        if suffix == ".json":
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return PolicyConfig(**data)

        logger.warning("Unrecognised policy file extension %r; trying JSON then YAML", suffix)
        with path.open("r", encoding="utf-8") as fh:
            raw = fh.read()
        try:
            return PolicyConfig(**json.loads(raw))
        except json.JSONDecodeError:
            from ruamel.yaml import YAML

            yaml = YAML(typ="safe")
            import io

            data = yaml.load(io.StringIO(raw)) or {}
            return PolicyConfig(**data)

    except Exception as exc:
        logger.error("Failed to load policy from %s: %s — using defaults", path, exc)
        return PolicyConfig()


def evaluate_compliance(
    dep_graph: DependencyGraph,
    package_licenses: list[PackageLicense],
    vuln_report: VulnerabilityReport | None,
    policy: PolicyConfig,
) -> ComplianceReport:
    """Evaluate policy compliance for the dependency graph.

    Checks:
    - Denied licenses
    - Unknown licenses when deny_unknown_license=True
    - Critical CVEs when block_critical_cve=True
    - High CVEs when block_high_cve=True
    """
    violations: list[PolicyViolation] = []
    packages_checked = len(dep_graph.packages)

    # Normalise denied/allowed lists for case-insensitive comparison
    denied_upper = {lic.upper() for lic in policy.denied_licenses}
    allowed_upper = {lic.upper() for lic in policy.allowed_licenses}

    for pkg_license in package_licenses:
        pkg = pkg_license.package
        lic = pkg_license.license

        # Check denied licenses
        if lic.spdx_id and lic.spdx_id.upper() in denied_upper:
            violations.append(
                PolicyViolation(
                    type="license",
                    package_name=pkg.name,
                    package_version=pkg.version,
                    details=f"License {lic.spdx_id!r} is explicitly denied by policy",
                    recommendation=f"Replace {pkg.name} with a package using a permitted license",
                )
            )
            continue

        # Check for name-based denied match when SPDX id unavailable
        if not lic.spdx_id and lic.name.upper() in denied_upper:
            violations.append(
                PolicyViolation(
                    type="license",
                    package_name=pkg.name,
                    package_version=pkg.version,
                    details=f"License {lic.name!r} is explicitly denied by policy",
                    recommendation=f"Replace {pkg.name} with a package using a permitted license",
                )
            )
            continue

        # Unknown license check
        if policy.deny_unknown_license and lic.category == LicenseCategory.UNKNOWN:
            violations.append(
                PolicyViolation(
                    type="unknown_license",
                    package_name=pkg.name,
                    package_version=pkg.version,
                    details=f"License is unknown or could not be classified for {pkg.name}=={pkg.version}",
                    recommendation="Verify the license manually or choose a package with a known SPDX license",
                )
            )

        # Allowed-list enforcement: if allowed_licenses is set, any license NOT in it is a violation
        if allowed_upper and lic.category != LicenseCategory.UNKNOWN:
            spdx_key = lic.spdx_id.upper() if lic.spdx_id else ""
            name_upper = lic.name.upper()
            in_allowed = (spdx_key in allowed_upper) or (name_upper in allowed_upper)
            if not in_allowed:
                violations.append(
                    PolicyViolation(
                        type="license",
                        package_name=pkg.name,
                        package_version=pkg.version,
                        details=(
                            f"License {lic.spdx_id or lic.name!r} is not in the allowed licenses list"
                        ),
                        recommendation=f"Replace {pkg.name} with a package using an allowed license",
                    )
                )

    # Vulnerability checks
    if vuln_report:
        for vuln in vuln_report.vulnerabilities:
            if policy.block_critical_cve and vuln.severity == Severity.CRITICAL:
                violations.append(
                    PolicyViolation(
                        type="cve",
                        package_name=vuln.package_name,
                        package_version=vuln.package_version,
                        details=f"Critical vulnerability {vuln.id}: {vuln.title or vuln.description}",
                        recommendation=(
                            f"Upgrade {vuln.package_name} to {vuln.fixed_version}"
                            if vuln.fixed_version
                            else f"Remove or replace {vuln.package_name}"
                        ),
                    )
                )
            elif policy.block_high_cve and vuln.severity == Severity.HIGH:
                violations.append(
                    PolicyViolation(
                        type="cve",
                        package_name=vuln.package_name,
                        package_version=vuln.package_version,
                        details=f"High severity vulnerability {vuln.id}: {vuln.title or vuln.description}",
                        recommendation=(
                            f"Upgrade {vuln.package_name} to {vuln.fixed_version}"
                            if vuln.fixed_version
                            else f"Remove or replace {vuln.package_name}"
                        ),
                    )
                )

    return ComplianceReport(
        compliant=len(violations) == 0,
        violations=violations,
        packages_checked=packages_checked,
    )
