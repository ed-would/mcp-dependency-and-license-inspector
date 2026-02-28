"""SBOM generation in SPDX 2.3 and CycloneDX 1.5 formats."""

import datetime
import re
import uuid

from ..models.package import DependencyGraph, Ecosystem, Package


def _make_purl(pkg: Package) -> str:
    """Generate a Package URL (purl) for npm/pypi packages."""
    if pkg.ecosystem == Ecosystem.NPM:
        encoded_name = pkg.name.replace("@", "%40").replace("/", "%2F")
        return f"pkg:npm/{encoded_name}@{pkg.version}"
    if pkg.ecosystem == Ecosystem.PYPI:
        return f"pkg:pypi/{pkg.name.lower()}@{pkg.version}"
    if pkg.ecosystem == Ecosystem.MAVEN:
        return f"pkg:maven/{pkg.name}@{pkg.version}"
    return f"pkg:generic/{pkg.name}@{pkg.version}"


def _spdx_safe_id(name: str, version: str) -> str:
    """Create an SPDX-safe element identifier (alphanumeric + dash only)."""
    safe_name = re.sub(r"[^A-Za-z0-9.\-]", "-", name)
    safe_version = re.sub(r"[^A-Za-z0-9.\-]", "-", version)
    return f"SPDXRef-{safe_name}-{safe_version}"


def generate_spdx(graph: DependencyGraph, project_name: str = "project") -> dict:
    """Generate an SPDX 2.3 JSON document for the dependency graph."""
    doc_uuid = str(uuid.uuid4())
    namespace = f"https://spdx.org/spdxdocs/{project_name}-{doc_uuid}"

    spdx_packages = []
    for pkg in graph.packages:
        spdx_id = _spdx_safe_id(pkg.name, pkg.version)
        spdx_packages.append(
            {
                "SPDXID": spdx_id,
                "name": pkg.name,
                "versionInfo": pkg.version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": _make_purl(pkg),
                    }
                ],
            }
        )

    relationships = []
    for pkg in graph.packages:
        child_id = _spdx_safe_id(pkg.name, pkg.version)
        for parent_name in pkg.parents:
            for other in graph.packages:
                if other.name == parent_name:
                    parent_id = _spdx_safe_id(other.name, other.version)
                    relationships.append(
                        {
                            "spdxElementId": parent_id,
                            "relationshipType": "DEPENDS_ON",
                            "relatedSpdxElement": child_id,
                        }
                    )
                    break

    doc = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": project_name,
        "documentNamespace": namespace,
        "documentDescribes": [_spdx_safe_id(pkg.name, pkg.version) for pkg in graph.packages],
        "packages": spdx_packages,
    }
    if relationships:
        doc["relationships"] = relationships
    return doc


def generate_cyclonedx(graph: DependencyGraph, project_name: str = "project") -> dict:
    """Generate a CycloneDX 1.5 JSON BOM for the dependency graph."""
    serial_number = f"urn:uuid:{uuid.uuid4()}"
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    components = []
    for pkg in graph.packages:
        components.append(
            {
                "type": "library",
                "name": pkg.name,
                "version": pkg.version,
                "purl": _make_purl(pkg),
            }
        )

    dependencies = []
    for pkg in graph.packages:
        depends_on = [
            _make_purl(other)
            for other in graph.packages
            if pkg.name in other.parents
        ]
        if depends_on:
            dependencies.append(
                {
                    "ref": _make_purl(pkg),
                    "dependsOn": depends_on,
                }
            )

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "serialNumber": serial_number,
        "metadata": {
            "timestamp": timestamp,
            "component": {
                "type": "application",
                "name": project_name,
            },
        },
        "components": components,
    }
    if dependencies:
        bom["dependencies"] = dependencies
    return bom
