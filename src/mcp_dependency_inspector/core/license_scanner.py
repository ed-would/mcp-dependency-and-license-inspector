"""License classification and scanning."""

import logging
import re

from ..models.license_model import LicenseCategory, LicenseInfo, PackageLicense
from ..models.package import Package
from .license_data import LICENSE_DATA, SPDX_ALIASES

logger = logging.getLogger(__name__)

_COMPOUND_PATTERN = re.compile(r"\s+(?:AND|OR)\s+", re.IGNORECASE)


def _normalize(license_str: str) -> str:
    """Normalize license string to uppercase SPDX-like key."""
    normalized = license_str.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.upper().replace(" ", "-")


def _resolve_spdx_key(license_str: str) -> str | None:
    """Try to resolve a license string to a known LICENSE_DATA key.

    First checks direct uppercase match, then alias table, then partial alias match.
    Returns None if not found.
    """
    stripped = license_str.strip()

    # Direct SPDX alias lookup (case-sensitive aliases first)
    if stripped in SPDX_ALIASES:
        return SPDX_ALIASES[stripped]

    # Normalized uppercase key lookup
    key = _normalize(stripped)
    if key in LICENSE_DATA:
        return key

    # Alias lookup via normalized key
    if key in SPDX_ALIASES:
        canonical = SPDX_ALIASES[key]
        normalized_canonical = _normalize(canonical)
        if normalized_canonical in LICENSE_DATA:
            return normalized_canonical
        return canonical.upper()

    # Case-insensitive alias lookup
    lower = stripped.lower()
    for alias, canonical in SPDX_ALIASES.items():
        if alias.lower() == lower:
            normalized_canonical = _normalize(canonical)
            if normalized_canonical in LICENSE_DATA:
                return normalized_canonical

    return None


def get_license_info(license_str: str) -> LicenseInfo:
    """Classify a license string into a LicenseInfo.

    Handles AND/OR compound licenses (returns MULTIPLE category).
    Looks up in LICENSE_DATA (with alias fallback).
    Unknown strings yield LicenseCategory.UNKNOWN.
    """
    if not license_str or not license_str.strip():
        return LicenseInfo(
            spdx_id=None,
            name="Unknown",
            category=LicenseCategory.UNKNOWN,
            is_unknown=True,
        )

    stripped = license_str.strip()

    # Detect compound license expressions (AND / OR)
    if _COMPOUND_PATTERN.search(stripped):
        return LicenseInfo(
            spdx_id=None,
            name=stripped,
            category=LicenseCategory.MULTIPLE,
            is_multiple=True,
        )

    # Attempt resolution to a known SPDX key
    key = _resolve_spdx_key(stripped)

    if key and key in LICENSE_DATA:
        data = LICENSE_DATA[key]
        is_copyleft = data["category"] == "copyleft"
        return LicenseInfo(
            spdx_id=key,
            name=data["name"],
            category=LicenseCategory.COPYLEFT if is_copyleft else LicenseCategory.PERMISSIVE,
            is_copyleft=is_copyleft,
        )

    logger.debug("Unknown license string: %r", license_str)
    return LicenseInfo(
        spdx_id=None,
        name=stripped,
        category=LicenseCategory.UNKNOWN,
        is_unknown=True,
    )


def scan_licenses(
    packages: list[Package],
    package_metadata: dict[str, str] | None = None,
) -> list[PackageLicense]:
    """Return PackageLicense for each package.

    package_metadata maps package name to a license string.
    Packages missing from metadata get LicenseCategory.UNKNOWN.
    """
    metadata = package_metadata or {}
    result: list[PackageLicense] = []

    for pkg in packages:
        license_str = metadata.get(pkg.name, "")
        if license_str:
            license_info = get_license_info(license_str)
        else:
            license_info = LicenseInfo(
                spdx_id=None,
                name="Unknown",
                category=LicenseCategory.UNKNOWN,
                is_unknown=True,
            )
        result.append(PackageLicense(package=pkg, license=license_info))

    return result
