"""Parsers for Node.js / NPM manifest and lock files."""

import json
import logging
import re
from pathlib import Path

from ..models.package import Ecosystem, Package

logger = logging.getLogger(__name__)

_VERSION_PREFIX_RE = re.compile(r"^[~^>=<!]+")


def _clean_version(version: str) -> str:
    """Strip leading version specifier characters (^, ~, >=, <=, =, >, <)."""
    return _VERSION_PREFIX_RE.sub("", version).strip() or "*"


def parse_package_json(path: str) -> tuple[list[Package], dict[str, str]]:
    """Parse package.json. Returns (packages, license_map).

    packages: direct deps from dependencies + devDependencies + peerDependencies.
    license_map: {name: license_str} collected from the root "license" key.
    Version specifiers are cleaned (^ ~ >= etc. stripped).
    """
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("package.json not found: %s", path)
        return [], {}

    try:
        with file_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return [], {}

    packages: list[Package] = []
    license_map: dict[str, str] = {}

    # Root package license: "license" (string) or legacy "licenses" (array)
    root_name = data.get("name", "")
    root_license = data.get("license", "")
    if not root_license and root_name:
        # Legacy npm "licenses": [{"type": "MIT"}, {"type": "Apache-2.0"}] → "MIT OR Apache-2.0"
        licenses_arr = data.get("licenses", [])
        if isinstance(licenses_arr, list) and licenses_arr:
            parts = []
            for entry in licenses_arr:
                if isinstance(entry, dict) and entry.get("type"):
                    parts.append(str(entry["type"]).strip())
                elif isinstance(entry, str):
                    parts.append(entry.strip())
            if parts:
                root_license = " OR ".join(parts)
    if root_name and root_license:
        license_map[root_name] = root_license

    dep_sections = ["dependencies", "devDependencies", "peerDependencies"]
    seen: set[tuple[str, str]] = set()

    for section in dep_sections:
        deps = data.get(section, {})
        if not isinstance(deps, dict):
            continue
        for name, version_spec in deps.items():
            if not isinstance(name, str) or not isinstance(version_spec, str):
                continue
            version = _clean_version(version_spec)
            key = (name, version)
            if key in seen:
                continue
            seen.add(key)
            packages.append(
                Package(
                    name=name,
                    version=version,
                    ecosystem=Ecosystem.NPM,
                    direct=True,
                )
            )

    return packages, license_map


def parse_package_lock_json(path: str) -> list[Package]:
    """Parse package-lock.json v2/v3 (packages field).

    Skips the root entry (key ""). Marks packages as direct=False
    for transitive entries resolved from nested node_modules paths.
    """
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("package-lock.json not found: %s", path)
        return []

    try:
        with file_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return []

    packages: list[Package] = []
    seen: set[tuple[str, str]] = set()

    # v2/v3 format uses "packages" dict
    lock_packages = data.get("packages", {})
    if not isinstance(lock_packages, dict):
        return []

    for key, pkg_data in lock_packages.items():
        if key == "":
            # Root package — skip
            continue
        if not isinstance(pkg_data, dict):
            continue

        # Determine package name: strip "node_modules/" prefix segments
        name = pkg_data.get("name", "")
        if not name:
            # Derive name from key (last node_modules/... segment)
            parts = key.replace("\\", "/").split("node_modules/")
            name = parts[-1].strip("/") if parts else key

        version = pkg_data.get("version", "*")
        # Transitive if the key has more than one "node_modules/" segment
        is_transitive = key.count("node_modules/") > 1 or key.startswith("node_modules/")
        direct = not is_transitive

        key_tuple = (name, version)
        if key_tuple in seen:
            continue
        seen.add(key_tuple)

        packages.append(
            Package(
                name=name,
                version=version,
                ecosystem=Ecosystem.NPM,
                direct=direct,
            )
        )

    return packages


def parse_pnpm_lock(path: str) -> list[Package]:
    """Parse pnpm-lock.yaml. Extract packages section, return Package list."""
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("pnpm-lock.yaml not found: %s", path)
        return []

    try:
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        with file_path.open("r", encoding="utf-8") as fh:
            data = yaml.load(fh)
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return []

    if not isinstance(data, dict):
        return []

    packages: list[Package] = []
    seen: set[tuple[str, str]] = set()

    # pnpm-lock.yaml v6+ uses "packages" dict with keys like "/name@version"
    lock_packages = data.get("packages", {})
    if not isinstance(lock_packages, dict):
        return []

    for pkg_key, pkg_data in lock_packages.items():
        if not isinstance(pkg_key, str):
            continue

        # Parse key formats:
        # v6: "/lodash@4.17.21"  or  "/@scope/name@1.0.0"
        # v9: "name@version"
        name = ""
        version = "*"

        stripped = pkg_key.lstrip("/")
        if "@" in stripped:
            # Handle scoped packages like @scope/name@version
            if stripped.startswith("@"):
                # Scoped: @scope/name@version
                at_idx = stripped.rfind("@")
                if at_idx > 0:
                    name = stripped[:at_idx]
                    version = stripped[at_idx + 1 :]
                else:
                    name = stripped
            else:
                at_idx = stripped.rfind("@")
                name = stripped[:at_idx]
                version = stripped[at_idx + 1 :]
        else:
            name = stripped

        if not name:
            continue

        # Clean version (remove resolution suffix like "_peer.dep=...")
        version = version.split("_")[0] if "_" in version else version
        version = version or "*"

        key_tuple = (name, version)
        if key_tuple in seen:
            continue
        seen.add(key_tuple)

        packages.append(
            Package(
                name=name,
                version=version,
                ecosystem=Ecosystem.NPM,
                direct=False,
            )
        )

    return packages
