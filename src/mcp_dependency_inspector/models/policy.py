from pydantic import BaseModel

from .vulnerability import VulnerabilityScanStatus


class PolicyConfig(BaseModel):
    allowed_licenses: list[str] = []
    denied_licenses: list[str] = []
    deny_unknown_license: bool = False
    block_critical_cve: bool = True
    block_high_cve: bool = False


class PolicyViolation(BaseModel):
    type: str  # "license" | "cve" | "unknown_license"
    package_name: str
    package_version: str
    details: str
    recommendation: str = ""


class ComplianceReport(BaseModel):
    compliant: bool
    violations: list[PolicyViolation]
    packages_checked: int
    vulnerability_scan_status: VulnerabilityScanStatus | None = None
