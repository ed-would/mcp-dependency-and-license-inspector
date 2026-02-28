"""Unit tests for the license scanner."""

import pytest

from mcp_dependency_inspector.core.license_scanner import get_license_info, scan_licenses
from mcp_dependency_inspector.models.license_model import LicenseCategory
from mcp_dependency_inspector.models.package import Ecosystem, Package


def _make_package(name: str, version: str = "1.0.0", ecosystem: Ecosystem = Ecosystem.NPM) -> Package:
    return Package(name=name, version=version, ecosystem=ecosystem)


# ---------------------------------------------------------------------------
# get_license_info tests
# ---------------------------------------------------------------------------


def test_get_license_info_mit():
    info = get_license_info("MIT")
    assert info.category == LicenseCategory.PERMISSIVE
    assert info.is_copyleft is False
    assert info.is_unknown is False


def test_get_license_info_apache():
    info = get_license_info("Apache-2.0")
    assert info.category == LicenseCategory.PERMISSIVE
    assert info.is_copyleft is False
    assert info.is_unknown is False


def test_get_license_info_gpl3():
    info = get_license_info("GPL-3.0")
    assert info.category == LicenseCategory.COPYLEFT
    assert info.is_copyleft is True
    assert info.is_unknown is False


def test_get_license_info_gpl2():
    info = get_license_info("GPL-2.0")
    assert info.category == LicenseCategory.COPYLEFT
    assert info.is_copyleft is True


def test_get_license_info_agpl():
    info = get_license_info("AGPL-3.0")
    assert info.category == LicenseCategory.COPYLEFT
    assert info.is_copyleft is True


def test_get_license_info_unknown():
    info = get_license_info("CustomProprietary-1.0")
    assert info.category == LicenseCategory.UNKNOWN
    assert info.is_unknown is True


def test_get_license_info_empty_string_is_unknown():
    info = get_license_info("")
    assert info.category == LicenseCategory.UNKNOWN
    assert info.is_unknown is True


def test_get_license_info_compound_and():
    info = get_license_info("MIT AND Apache-2.0")
    assert info.category == LicenseCategory.MULTIPLE
    assert info.is_multiple is True
    assert info.is_unknown is False


def test_get_license_info_compound_or():
    info = get_license_info("MIT OR GPL-3.0")
    assert info.category == LicenseCategory.MULTIPLE
    assert info.is_multiple is True


def test_get_license_info_alias():
    """'Apache 2.0' is a known alias and should resolve to permissive."""
    info = get_license_info("Apache 2.0")
    assert info.category == LicenseCategory.PERMISSIVE
    assert info.is_unknown is False


def test_get_license_info_alias_mit_lower():
    """'mit' alias (lowercase) should resolve to MIT (permissive)."""
    info = get_license_info("mit")
    assert info.category == LicenseCategory.PERMISSIVE
    assert info.is_unknown is False


def test_get_license_info_isc():
    info = get_license_info("ISC")
    assert info.category == LicenseCategory.PERMISSIVE


def test_get_license_info_bsd3():
    info = get_license_info("BSD-3-Clause")
    assert info.category == LicenseCategory.PERMISSIVE


# ---------------------------------------------------------------------------
# scan_licenses tests
# ---------------------------------------------------------------------------


def test_scan_licenses_with_metadata():
    packages = [
        _make_package("lodash"),
        _make_package("express"),
    ]
    metadata = {"lodash": "MIT", "express": "MIT"}
    results = scan_licenses(packages, package_metadata=metadata)
    assert len(results) == 2
    for pl in results:
        assert pl.license.category == LicenseCategory.PERMISSIVE


def test_scan_licenses_unknown_when_no_metadata():
    packages = [_make_package("some-mystery-pkg")]
    results = scan_licenses(packages)
    assert len(results) == 1
    assert results[0].license.category == LicenseCategory.UNKNOWN
    assert results[0].license.is_unknown is True


def test_scan_licenses_mixed_metadata():
    packages = [
        _make_package("lodash"),
        _make_package("gpl-lib"),
        _make_package("no-license-pkg"),
    ]
    metadata = {"lodash": "MIT", "gpl-lib": "GPL-3.0"}
    results = scan_licenses(packages, package_metadata=metadata)
    by_name = {pl.package.name: pl.license for pl in results}

    assert by_name["lodash"].category == LicenseCategory.PERMISSIVE
    assert by_name["gpl-lib"].category == LicenseCategory.COPYLEFT
    assert by_name["no-license-pkg"].category == LicenseCategory.UNKNOWN


def test_scan_licenses_preserves_package_order():
    names = ["alpha", "beta", "gamma"]
    packages = [_make_package(n) for n in names]
    results = scan_licenses(packages)
    result_names = [pl.package.name for pl in results]
    assert result_names == names


def test_scan_licenses_empty_list():
    results = scan_licenses([])
    assert results == []


def test_scan_licenses_package_object_attached():
    pkg = _make_package("lodash")
    results = scan_licenses([pkg], package_metadata={"lodash": "MIT"})
    assert results[0].package is pkg
