"""Parsers for Python / pip manifest and lock files."""

import logging
import re
from pathlib import Path

from ..models.package import Ecosystem, Package

logger = logging.getLogger(__name__)

# Matches version specifiers: ==, >=, <=, ~=, !=, >, <
_VERSION_SPEC_RE = re.compile(r"[><=!~^]+[\s]*[\d.*]+(?:,\s*[><=!~^]+[\s]*[\d.*]+)*")
# Splits a requirement line into name and specifier
_REQ_LINE_RE = re.compile(r"^([A-Za-z0-9_.\-\[\]]+)\s*([><=!~^,\s\d.*]*)$")
_EXTRAS_RE = re.compile(r"\[.*?\]")


def _extract_version(specifier: str) -> str:
    """Extract a single clean version from a specifier string.

    Handles ==1.2.3, >=1.2.3, ~=1.2.3.  Returns '*' when ambiguous.
    """
    specifier = specifier.strip()
    if not specifier:
        return "*"
    # Prefer exact pin ==
    exact = re.search(r"==\s*([\d.a-zA-Z_+\-]+)", specifier)
    if exact:
        return exact.group(1).strip()
    # Compatible release ~=
    compat = re.search(r"~=\s*([\d.a-zA-Z_+\-]+)", specifier)
    if compat:
        return compat.group(1).strip()
    # Minimum >= or >
    minimum = re.search(r">=?\s*([\d.a-zA-Z_+\-]+)", specifier)
    if minimum:
        return minimum.group(1).strip()
    return "*"


def _normalise_name(name: str) -> str:
    """Normalise package name per PEP 503 (lowercase, dashes)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements_txt(path: str) -> list[Package]:
    """Parse requirements.txt. Skip comments, blank lines, and pip options.

    Handles: pkg==ver, pkg>=ver, pkg~=ver, pkg (no version → '*').
    Ignores -r includes, -c constraints, --index-url, etc.
    """
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("requirements.txt not found: %s", path)
        return []

    packages: list[Package] = []

    try:
        with file_path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return []

    for raw_line in lines:
        line = raw_line.strip()

        # Skip empty lines, comments, and pip options
        if not line or line.startswith("#") or line.startswith("-") or line.startswith("--"):
            continue

        # Remove inline comment
        if " #" in line:
            line = line[: line.index(" #")].strip()

        # Remove environment markers (e.g. ; python_version < "3.8")
        if ";" in line:
            line = line[: line.index(";")].strip()

        # Remove extras (e.g. package[extra])
        name_part = _EXTRAS_RE.sub("", line).strip()

        match = _REQ_LINE_RE.match(name_part)
        if not match:
            logger.debug("Skipping unrecognised requirements line: %r", line)
            continue

        name = match.group(1).strip()
        specifier = match.group(2).strip()
        version = _extract_version(specifier)

        packages.append(
            Package(
                name=name,
                version=version,
                ecosystem=Ecosystem.PYPI,
                direct=True,
            )
        )

    return packages


def _parse_pep508_version(dep: str) -> tuple[str, str]:
    """Parse a PEP 508 dependency string into (name, version)."""
    # Remove extras and markers
    dep = re.sub(r"\[.*?\]", "", dep)
    if ";" in dep:
        dep = dep[: dep.index(";")]
    dep = dep.strip()

    # Match name and optional specifier
    m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)", dep)
    if not m:
        return dep, "*"

    name = m.group(1).strip()
    specifier = m.group(2).strip()
    version = _extract_version(specifier) if specifier else "*"
    return name, version


def parse_pyproject_toml(path: str) -> tuple[list[Package], dict[str, str]]:
    """Parse pyproject.toml using tomli.

    Reads [project].dependencies (PEP 517/518) and [tool.poetry.dependencies].
    Returns (packages, license_map) where license_map is {project_name: license_str}.
    """
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("pyproject.toml not found: %s", path)
        return [], {}

    try:
        import tomli

        with file_path.open("rb") as fh:
            data = tomli.load(fh)
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return [], {}

    packages: list[Package] = []
    license_map: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()

    # --- PEP 517/518 [project] section ---
    project = data.get("project", {})
    if isinstance(project, dict):
        project_name = project.get("name", "")
        project_license = project.get("license", {})
        if isinstance(project_license, dict):
            lic_text = project_license.get("text", "") or project_license.get("file", "")
            if project_name and lic_text:
                license_map[project_name] = lic_text
        elif isinstance(project_license, str) and project_name:
            license_map[project_name] = project_license

        for dep in project.get("dependencies", []):
            if not isinstance(dep, str):
                continue
            name, version = _parse_pep508_version(dep)
            key = (name, version)
            if key not in seen:
                seen.add(key)
                packages.append(
                    Package(name=name, version=version, ecosystem=Ecosystem.PYPI, direct=True)
                )

    # --- [tool.poetry] section ---
    tool = data.get("tool", {})
    poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
    if isinstance(poetry, dict):
        poetry_name = poetry.get("name", "")
        poetry_license = poetry.get("license", "")
        if poetry_name and poetry_license:
            license_map[poetry_name] = poetry_license

        poetry_deps = poetry.get("dependencies", {})
        if isinstance(poetry_deps, dict):
            for dep_name, dep_spec in poetry_deps.items():
                if dep_name.lower() == "python":
                    continue
                if isinstance(dep_spec, str):
                    version = _extract_version(dep_spec) if dep_spec not in ("*", "") else "*"
                elif isinstance(dep_spec, dict):
                    version_val = dep_spec.get("version", "*")
                    version = _extract_version(version_val) if version_val else "*"
                else:
                    version = "*"

                key = (dep_name, version)
                if key not in seen:
                    seen.add(key)
                    packages.append(
                        Package(
                            name=dep_name,
                            version=version,
                            ecosystem=Ecosystem.PYPI,
                            direct=True,
                        )
                    )

    return packages, license_map


def parse_poetry_lock(path: str) -> list[Package]:
    """Parse poetry.lock TOML. Read [[package]] sections for name and version."""
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("poetry.lock not found: %s", path)
        return []

    try:
        import tomli

        with file_path.open("rb") as fh:
            data = tomli.load(fh)
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return []

    packages: list[Package] = []
    seen: set[tuple[str, str]] = set()

    for pkg in data.get("package", []):
        if not isinstance(pkg, dict):
            continue
        name = pkg.get("name", "")
        version = pkg.get("version", "*")
        if not name:
            continue
        key = (name, version)
        if key in seen:
            continue
        seen.add(key)
        packages.append(
            Package(
                name=name,
                version=version,
                ecosystem=Ecosystem.PYPI,
                direct=False,
            )
        )

    return packages
