"""Unit tests for SBOM generation (SPDX and CycloneDX)."""

import pytest

from mcp_dependency_inspector.core.sbom_builder import generate_cyclonedx, generate_spdx
from mcp_dependency_inspector.models.package import DependencyGraph, Ecosystem, Package


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


def _sample_graph() -> DependencyGraph:
    return _make_graph(
        [
            Package(name="lodash", version="4.17.21", ecosystem=Ecosystem.NPM, direct=True),
            Package(name="requests", version="2.31.0", ecosystem=Ecosystem.PYPI, direct=True),
        ]
    )


# ---------------------------------------------------------------------------
# SPDX tests
# ---------------------------------------------------------------------------


def test_generate_spdx_structure():
    graph = _sample_graph()
    result = generate_spdx(graph)
    assert "spdxVersion" in result
    assert "dataLicense" in result
    assert "SPDXID" in result
    assert "packages" in result


def test_generate_spdx_version_value():
    result = generate_spdx(_sample_graph())
    assert result["spdxVersion"] == "SPDX-2.3"
    assert result["dataLicense"] == "CC0-1.0"
    assert result["SPDXID"] == "SPDXRef-DOCUMENT"


def test_generate_spdx_package_count():
    graph = _sample_graph()
    result = generate_spdx(graph)
    assert len(result["packages"]) == len(graph.packages)


def test_generate_spdx_package_fields():
    result = generate_spdx(_sample_graph())
    for pkg in result["packages"]:
        assert "SPDXID" in pkg
        assert "name" in pkg
        assert "versionInfo" in pkg
        assert "externalRefs" in pkg


def test_generate_spdx_purl_in_external_refs():
    result = generate_spdx(_sample_graph())
    purls = [
        ref["referenceLocator"]
        for pkg in result["packages"]
        for ref in pkg.get("externalRefs", [])
        if ref.get("referenceType") == "purl"
    ]
    assert len(purls) == 2
    assert any(p.startswith("pkg:npm/") for p in purls)
    assert any(p.startswith("pkg:pypi/") for p in purls)


def test_generate_spdx_empty_graph():
    graph = _make_graph([])
    result = generate_spdx(graph)
    assert result["packages"] == []


def test_generate_spdx_document_namespace():
    result = generate_spdx(_sample_graph(), project_name="my-project")
    assert "my-project" in result["documentNamespace"]
    assert result["name"] == "my-project"


# ---------------------------------------------------------------------------
# CycloneDX tests
# ---------------------------------------------------------------------------


def test_generate_cyclonedx_structure():
    graph = _sample_graph()
    result = generate_cyclonedx(graph)
    assert "bomFormat" in result
    assert "specVersion" in result
    assert "components" in result


def test_generate_cyclonedx_format_values():
    result = generate_cyclonedx(_sample_graph())
    assert result["bomFormat"] == "CycloneDX"
    assert result["specVersion"] == "1.5"


def test_generate_cyclonedx_component_count():
    graph = _sample_graph()
    result = generate_cyclonedx(graph)
    assert len(result["components"]) == len(graph.packages)


def test_generate_cyclonedx_purl():
    result = generate_cyclonedx(_sample_graph())
    for component in result["components"]:
        assert "purl" in component
        assert component["purl"].startswith("pkg:")


def test_generate_cyclonedx_metadata_fields():
    result = generate_cyclonedx(_sample_graph())
    assert "metadata" in result
    assert "timestamp" in result["metadata"]
    assert "component" in result["metadata"]


def test_generate_cyclonedx_serial_number():
    result = generate_cyclonedx(_sample_graph())
    assert "serialNumber" in result
    assert result["serialNumber"].startswith("urn:uuid:")


def test_generate_cyclonedx_empty_graph():
    graph = _make_graph([])
    result = generate_cyclonedx(graph)
    assert result["components"] == []


def test_generate_cyclonedx_npm_purl_format():
    graph = _make_graph(
        [Package(name="lodash", version="4.17.21", ecosystem=Ecosystem.NPM, direct=True)]
    )
    result = generate_cyclonedx(graph)
    assert result["components"][0]["purl"] == "pkg:npm/lodash@4.17.21"


def test_generate_cyclonedx_pypi_purl_format():
    graph = _make_graph(
        [Package(name="Requests", version="2.31.0", ecosystem=Ecosystem.PYPI, direct=True)]
    )
    result = generate_cyclonedx(graph)
    # PyPI purls should use lowercase names
    assert result["components"][0]["purl"] == "pkg:pypi/requests@2.31.0"


def test_generate_spdx_relationships_when_parents_present():
    child = Package(
        name="child-pkg",
        version="1.0.0",
        ecosystem=Ecosystem.NPM,
        direct=False,
        parents=["parent-pkg"],
    )
    parent = Package(
        name="parent-pkg",
        version="2.0.0",
        ecosystem=Ecosystem.NPM,
        direct=True,
        parents=[],
    )
    graph = _make_graph([parent, child])
    result = generate_spdx(graph)
    assert "relationships" in result
    rels = result["relationships"]
    assert len(rels) >= 1
    dep_rel = next(r for r in rels if r["relationshipType"] == "DEPENDS_ON")
    assert dep_rel["relatedSpdxElement"] == "SPDXRef-child-pkg-1.0.0"
    assert "parent-pkg" in dep_rel["spdxElementId"]


def test_generate_spdx_no_relationships_without_parents():
    graph = _sample_graph()
    result = generate_spdx(graph)
    assert "relationships" not in result


def test_generate_cyclonedx_dependencies_when_parents_present():
    child = Package(
        name="child-pkg",
        version="1.0.0",
        ecosystem=Ecosystem.NPM,
        direct=False,
        parents=["parent-pkg"],
    )
    parent = Package(
        name="parent-pkg",
        version="2.0.0",
        ecosystem=Ecosystem.NPM,
        direct=True,
        parents=[],
    )
    graph = _make_graph([parent, child])
    result = generate_cyclonedx(graph)
    assert "dependencies" in result
    parent_purl = "pkg:npm/parent-pkg@2.0.0"
    parent_dep = next(d for d in result["dependencies"] if d["ref"] == parent_purl)
    assert "pkg:npm/child-pkg@1.0.0" in parent_dep["dependsOn"]


def test_generate_cyclonedx_no_dependencies_without_parents():
    graph = _sample_graph()
    result = generate_cyclonedx(graph)
    assert "dependencies" not in result
