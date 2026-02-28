"""Walk a project directory and collect all dependency information from manifests."""

import logging
import os
from collections import Counter
from typing import Callable

from ..config import settings
from ..models.package import DependencyGraph, Ecosystem, Package
from ..parsers.npm import parse_package_json, parse_package_lock_json, parse_pnpm_lock
from ..parsers.pip import parse_poetry_lock, parse_pyproject_toml, parse_requirements_txt

logger = logging.getLogger(__name__)

# Maps manifest filename → (parser_callable, ecosystem)
# Parsers that return (list[Package], dict[str,str]) are "manifest" parsers;
# parsers that return list[Package] only are "lock" parsers.
# We tag them with a flag.
_MANIFEST_PARSERS: dict[
    str,
    tuple[Callable[..., tuple[list[Package], dict[str, str]] | list[Package]], Ecosystem, bool],
] = {
    "package.json": (parse_package_json, Ecosystem.NPM, True),
    "package-lock.json": (parse_package_lock_json, Ecosystem.NPM, False),
    "pnpm-lock.yaml": (parse_pnpm_lock, Ecosystem.NPM, False),
    "requirements.txt": (parse_requirements_txt, Ecosystem.PYPI, False),
    "pyproject.toml": (parse_pyproject_toml, Ecosystem.PYPI, True),
    "poetry.lock": (parse_poetry_lock, Ecosystem.PYPI, False),
}


def scan_project(
    project_path: str,
    exclude_dirs: list[str] | None = None,
) -> tuple[DependencyGraph, dict[str, str]]:
    """Walk project_path, discover manifest files, and parse them.

    Returns:
        (DependencyGraph, license_metadata) where license_metadata is a combined
        {package_name: license_str} dict from all manifests that provide it.

    Skips excluded directories (default: settings.exclude_dirs).
    Deduplicates packages by (name, version, ecosystem).
    """
    excluded: set[str] = set(exclude_dirs if exclude_dirs is not None else settings.exclude_dirs)

    all_packages: dict[tuple[str, str, str], Package] = {}
    all_license_metadata: dict[str, str] = {}

    if not os.path.isdir(project_path):
        logger.warning("Project path does not exist or is not a directory: %s", project_path)
        return _build_graph([]), {}

    for dirpath, dirnames, filenames in os.walk(project_path, topdown=True):
        # Prune excluded directories in-place so os.walk won't descend into them
        dirnames[:] = [d for d in dirnames if d not in excluded]

        for filename in filenames:
            if filename not in _MANIFEST_PARSERS:
                continue

            file_path = os.path.join(dirpath, filename)
            parser, _ecosystem, has_license_map = _MANIFEST_PARSERS[filename]

            logger.debug("Parsing manifest: %s", file_path)

            try:
                if has_license_map:
                    result = parser(file_path)
                    if isinstance(result, tuple):
                        pkgs, lic_map = result
                    else:
                        pkgs = result
                        lic_map = {}
                    all_license_metadata.update(lic_map)
                else:
                    raw = parser(file_path)
                    pkgs = raw if isinstance(raw, list) else []
            except Exception as exc:
                logger.warning("Unexpected error parsing %s: %s", file_path, exc)
                continue

            for pkg in pkgs:
                dedup_key = (pkg.name, pkg.version, pkg.ecosystem.value)
                if dedup_key not in all_packages:
                    all_packages[dedup_key] = pkg

    package_list = list(all_packages.values())
    graph = _build_graph(package_list)
    return graph, all_license_metadata


def _build_graph(packages: list[Package]) -> DependencyGraph:
    """Construct a DependencyGraph from a flat package list."""
    ecosystem_counts: Counter[str] = Counter()
    direct_count = 0
    transitive_count = 0

    for pkg in packages:
        ecosystem_counts[pkg.ecosystem.value] += 1
        if pkg.direct:
            direct_count += 1
        else:
            transitive_count += 1

    return DependencyGraph(
        packages=packages,
        ecosystem_counts=dict(ecosystem_counts),
        direct_count=direct_count,
        transitive_count=transitive_count,
    )
