#!/usr/bin/env python3
"""Dependency & License Inspector MCP server (stdio and streamable-HTTP transport).

Security: no shell or subprocess execution; path and payload size limits;
optional allowed_base_path; per-tool timeout.
"""

import inspect
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import settings
from .models import PolicyConfig
from .core.manifest_scanner import scan_project
from .core.license_scanner import scan_licenses
from .core.policy_engine import load_policy, evaluate_compliance
from .core.vulnerability_scanner import scan_vulnerabilities
from .core.sbom_builder import generate_spdx, generate_cyclonedx
from .core.reporter import (
    format_dependency_summary,
    format_license_report,
    format_vulnerability_report,
    format_compliance_report,
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="dependency-license-inspector",
    instructions=(
        "Inspect project dependencies and licenses. "
        "Use analyze_project_dependencies first, then scan_vulnerabilities, "
        "scan_licenses, check_policy_compliance as needed. "
        "generate_sbom produces SPDX or CycloneDX output. "
        "suggest_dependency_replacements recommends alternatives for problematic packages."
    ),
)

# ── Root and health (lightweight; for container readiness and browser UX) ─────────

@mcp.custom_route("/", ["GET"], include_in_schema=False)
async def root(_request: Request) -> Response:
    """Info for browser: /mcp is for MCP clients only."""
    return JSONResponse({
        "service": "dependency-license-inspector",
        "mcp_endpoint": "/mcp",
        "health": "/health",
        "hint": "Open /mcp in an MCP client (e.g. MCP Inspector) with URL http://localhost:8000/mcp. Browsers get 406 because the client must send Accept: text/event-stream.",
    })


@mcp.custom_route("/health", ["GET"], include_in_schema=False)
async def health(_request: Request) -> Response:
    """Quick liveness/readiness check; no heavy operations."""
    return JSONResponse({"status": "ok", "service": "dependency-license-inspector"})


# Session state for MCP resources: last report and SBOM from the most recent tool run.
_last_report: dict[str, Any] | None = None
_last_sbom_spdx: dict[str, Any] | None = None
_last_sbom_cyclonedx: dict[str, Any] | None = None
_last_sbom_project_name: str = ""


def _with_timeout(f: Any) -> Any:
    """Run sync tool in a thread with configurable timeout. No shell/subprocess used."""

    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if settings.tool_timeout_seconds <= 0:
            return f(*args, **kwargs)
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(f, *args, **kwargs)
            try:
                return fut.result(timeout=settings.tool_timeout_seconds)
            except TimeoutError:
                raise ValueError(
                    f"Tool execution timed out after {settings.tool_timeout_seconds}s"
                ) from None

    wrapped.__signature__ = inspect.signature(f)
    return wrapped


# ── Tool 1 ───────────────────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Scan a project directory and return the full dependency graph "
        "(direct + transitive) for all detected ecosystems (npm, PyPI, Maven). "
        "Returns a Markdown summary plus JSON data."
    )
)
@_with_timeout
def analyze_project_dependencies(
    project_path: Annotated[str, "Path to the project root directory to scan."],
    exclude_dirs: Annotated[
        list[str] | None,
        "Directory names to exclude from scanning (e.g. node_modules, .venv, __pycache__). Default from config.",
    ] = None,
) -> dict[str, Any]:
    """Build aggregated dependency list for the project."""
    _validate_exclude_dirs(exclude_dirs)
    path = _resolve_path(project_path)
    effective_exclude = exclude_dirs or settings.exclude_dirs
    graph, license_meta = scan_project(str(path), effective_exclude)
    return {
        "summary": format_dependency_summary(graph),
        "total_packages": len(graph.packages),
        "direct_count": graph.direct_count,
        "transitive_count": graph.transitive_count,
        "ecosystem_counts": graph.ecosystem_counts,
        "packages": [p.model_dump() for p in graph.packages],
    }


# ── Tool 2 ───────────────────────────────────────────────────────────────────

@mcp.tool(
    name="scan_vulnerabilities",
    description=(
        "Scan project dependencies for known vulnerabilities using the OSV database. "
        "Returns CVEs with severity and recommended fix versions. "
        "In DEMO_MODE or when offline, returns stub data."
    )
)
@_with_timeout
def scan_vulnerabilities_tool(
    project_path: Annotated[str, "Path to the project root directory to scan."],
    exclude_dirs: Annotated[
        list[str] | None,
        "Directory names to exclude from scanning. Default from config.",
    ] = None,
) -> dict[str, Any]:
    """Vulnerability scan via OSV API (or stubs in DEMO_MODE)."""
    _validate_exclude_dirs(exclude_dirs)
    path = _resolve_path(project_path)
    effective_exclude = exclude_dirs or settings.exclude_dirs
    graph, _ = scan_project(str(path), effective_exclude)
    report = scan_vulnerabilities(graph.packages)
    return {
        "summary": format_vulnerability_report(report),
        "counts_by_severity": report.counts_by_severity,
        "packages_scanned": report.packages_scanned,
        "vulnerabilities": [v.model_dump() for v in report.vulnerabilities],
        "demo_mode": settings.demo_mode,
    }


# ── Tool 3 ───────────────────────────────────────────────────────────────────

@mcp.tool(
    name="scan_licenses",
    description=(
        "List licenses for all project dependencies with risk flags "
        "(copyleft, unknown, multiple). Accepts a project path or an explicit "
        "list of packages [{name, version, ecosystem}]."
    )
)
@_with_timeout
def scan_licenses_tool(
    project_path: Annotated[
        str | None,
        "Path to the project root. Omit if using 'packages' instead.",
    ] = None,
    packages: Annotated[
        list[dict[str, str]] | None,
        "Explicit list of packages {name, version?, ecosystem?}. Use when not scanning from disk.",
    ] = None,
    exclude_dirs: Annotated[
        list[str] | None,
        "Directory names to exclude when scanning project_path. Default from config.",
    ] = None,
) -> dict[str, Any]:
    """License scan for project or explicit package list."""
    from .models.package import Package, Ecosystem

    if project_path:
        _validate_exclude_dirs(exclude_dirs)
        path = _resolve_path(project_path)
        effective_exclude = exclude_dirs or settings.exclude_dirs
        graph, license_meta = scan_project(str(path), effective_exclude)
        pkg_list = graph.packages
    elif packages:
        pkg_list = [
            Package(
                name=p["name"],
                version=p.get("version", "*"),
                ecosystem=Ecosystem(p.get("ecosystem", "unknown")),
            )
            for p in packages
        ]
        license_meta = {}
    else:
        return {"success": False, "error": "Either project_path or packages must be provided."}

    license_results = scan_licenses(pkg_list, license_meta)
    return {
        "summary": format_license_report(license_results),
        "total_packages": len(license_results),
        "licenses": [
            {
                "package": r.package.name,
                "version": r.package.version,
                "ecosystem": r.package.ecosystem.value,
                "license": r.license.name,
                "spdx_id": r.license.spdx_id,
                "category": r.license.category.value,
                "is_copyleft": r.license.is_copyleft,
                "is_unknown": r.license.is_unknown,
                "is_multiple": r.license.is_multiple,
            }
            for r in license_results
        ],
    }


# ── Tool 4 ───────────────────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Evaluate the project against a license and CVE policy. "
        "Use policy_path for a file path (e.g. demo_project/policy_strict.yaml) — plain text, no quotes. "
        "Or use policy: dict or JSON string path. "
        "Returns compliant (bool), violations list."
    )
)
@_with_timeout
def check_policy_compliance(
    project_path: Annotated[str, "Path to the project root directory to evaluate."],
    policy_path: Annotated[
        str | None,
        "Path to policy file (YAML/JSON). Plain text, e.g. demo_project/policy_strict.yaml — no quotes needed.",
    ] = "",
    policy: Annotated[
        dict[str, Any] | str | None,
        "Policy: dict or path to YAML/JSON file. Ignored if policy_path is set. For API: use quoted string or object.",
    ] = None,
    exclude_dirs: Annotated[
        list[str] | None,
        "Directory names to exclude from scanning. Default from config.",
    ] = None,
) -> dict[str, Any]:
    """Full compliance check: scan + license check + policy evaluation."""
    _validate_exclude_dirs(exclude_dirs)
    # Prefer policy_path (plain string, no JSON quotes) for convenience in Inspector
    effective_policy: dict[str, Any] | str | None = None
    if policy_path and str(policy_path).strip():
        effective_policy = str(policy_path).strip()
    else:
        effective_policy = policy
    _validate_policy_input(effective_policy)
    path = _resolve_path(project_path)
    effective_exclude = exclude_dirs or settings.exclude_dirs
    graph, license_meta = scan_project(str(path), effective_exclude)
    license_results = scan_licenses(graph.packages, license_meta)
    vuln_report = scan_vulnerabilities(graph.packages)

    if effective_policy is None:
        policy_cfg: PolicyConfig = PolicyConfig()
    else:
        policy_cfg = load_policy(effective_policy)

    compliance = evaluate_compliance(graph, license_results, vuln_report, policy_cfg)
    result = {
        "summary": format_compliance_report(compliance),
        "compliant": compliance.compliant,
        "packages_checked": compliance.packages_checked,
        "violations_count": len(compliance.violations),
        "violations": [v.model_dump() for v in compliance.violations],
        "demo_mode": settings.demo_mode,
    }
    global _last_report
    _last_report = {
        "project_path": str(path),
        "summary": result["summary"],
        "compliant": compliance.compliant,
        "packages_checked": compliance.packages_checked,
        "violations_count": len(compliance.violations),
        "violations": [v.model_dump() for v in compliance.violations],
    }
    return result


# ── Tool 5 ───────────────────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Generate a Software Bill of Materials (SBOM) in SPDX 2.3 or CycloneDX 1.5 "
        "JSON format for the project dependencies. "
        "Accepts project_path and format ('spdx' or 'cyclonedx'). "
        "Returns JSON object with sbom field."
    )
)
@_with_timeout
def generate_sbom(
    project_path: Annotated[str, "Path to the project root directory."],
    format: Annotated[
        str,
        "Output format: 'spdx' (SPDX 2.3 JSON) or 'cyclonedx' (CycloneDX 1.5 JSON).",
    ] = "spdx",
    exclude_dirs: Annotated[
        list[str] | None,
        "Directory names to exclude from scanning. Default from config.",
    ] = None,
) -> dict[str, Any]:
    """Generate SBOM. format must be 'spdx' or 'cyclonedx'."""
    if format not in ("spdx", "cyclonedx"):
        return {"success": False, "error": f"Unknown format '{format}'. Use 'spdx' or 'cyclonedx'."}
    _validate_exclude_dirs(exclude_dirs)
    path = _resolve_path(project_path)
    effective_exclude = exclude_dirs or settings.exclude_dirs
    graph, _ = scan_project(str(path), effective_exclude)
    project_name = path.name

    if format == "spdx":
        sbom = generate_spdx(graph, project_name)
    else:
        sbom = generate_cyclonedx(graph, project_name)

    global _last_sbom_spdx, _last_sbom_cyclonedx, _last_sbom_project_name
    _last_sbom_project_name = project_name
    if format == "spdx":
        _last_sbom_spdx = sbom
    else:
        _last_sbom_cyclonedx = sbom

    return {
        "format": format,
        "package_count": len(graph.packages),
        "sbom": sbom,
    }


# ── Tool 6 ───────────────────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Suggest safe, policy-compliant replacement packages for dependencies "
        "that have CVEs or denied licenses. "
        "In DEMO_MODE or when offline, returns curated stub suggestions."
    )
)
@_with_timeout
def suggest_dependency_replacements(
    packages: Annotated[
        list[dict[str, str]] | list[list[dict[str, str]]],
        "List of packages to replace: [{name, version?, ecosystem?, reason}]. reason: 'cve' or 'license'. Pass a single array of objects.",
    ],
    policy: Annotated[
        dict[str, Any] | str | None,
        "Optional policy dict or path to filter suggested replacements by license.",
    ] = None,
) -> dict[str, Any]:
    """Return alternative packages for problematic deps.

    packages: list of {name, version, ecosystem, reason}
              where reason is "cve" or "license".
    In DEMO_MODE or on error: return stub suggestions.
    """
    # Normalize: some MCP clients (e.g. Inspector) send packages as [[{...}, {...}]] instead of [{...}, {...}]
    if packages and isinstance(packages[0], list):
        packages = list(packages[0])
    else:
        packages = list(packages) if packages else []
    _validate_policy_input(policy)
    if settings.demo_mode:
        return _stub_replacements(packages)

    try:
        return _live_replacements(packages, policy)
    except Exception as exc:
        logger.warning("Replacement lookup failed (%s); returning stubs", exc)
        return _stub_replacements(packages)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_exclude_dirs(exclude_dirs: list[str] | None) -> None:
    if exclude_dirs is None:
        return
    if len(exclude_dirs) > settings.max_exclude_dirs:
        raise ValueError(
            f"exclude_dirs length ({len(exclude_dirs)}) exceeds limit ({settings.max_exclude_dirs})"
        )


def _validate_policy_input(policy: dict[str, Any] | str | None) -> None:
    if policy is None:
        return
    if isinstance(policy, str):
        if len(policy) > settings.max_policy_payload_bytes:
            raise ValueError(
                f"Policy path length exceeds limit ({settings.max_policy_payload_bytes})"
            )
        return
    payload = json.dumps(policy)
    if len(payload.encode("utf-8")) > settings.max_policy_payload_bytes:
        raise ValueError(
            f"Policy payload size exceeds limit ({settings.max_policy_payload_bytes} bytes)"
        )


def _resolve_path(project_path: str) -> Path:
    if len(project_path) > settings.max_input_path_length:
        raise ValueError(
            f"project_path length exceeds limit ({settings.max_input_path_length})"
        )
    path = Path(project_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")
    if settings.allowed_base_path:
        base = Path(settings.allowed_base_path).expanduser().resolve()
        if not base.exists() or not base.is_dir():
            raise ValueError(f"allowed_base_path is not a valid directory: {base}")
        try:
            path.relative_to(base)
        except ValueError:
            raise ValueError(
                f"Path {path} is not under allowed base directory {base}"
            ) from None
    return path


_STUB_ALTERNATIVES: dict[str, list[dict[str, str]]] = {
    "lodash": [
        {
            "name": "lodash-es",
            "version": "^4.17.21",
            "license": "MIT",
            "reason": "ESM variant of lodash, same API, no known CVEs in latest",
        },
        {
            "name": "remeda",
            "version": "^1.0.0",
            "license": "MIT",
            "reason": "Modern type-safe utility library, actively maintained",
        },
    ],
    "requests": [
        {
            "name": "httpx",
            "version": ">=0.27.0",
            "license": "BSD-3-Clause",
            "reason": "Modern async-ready HTTP client, actively maintained, no known CVEs",
        },
    ],
    "moment": [
        {
            "name": "date-fns",
            "version": "^3.0.0",
            "license": "MIT",
            "reason": "Lightweight date utility, tree-shakeable, actively maintained",
        },
        {
            "name": "dayjs",
            "version": "^1.11.0",
            "license": "MIT",
            "reason": "Moment.js-compatible API, much smaller bundle",
        },
    ],
}


def _stub_replacements(packages: list[dict[str, str]]) -> dict[str, Any]:
    results = []
    for pkg in packages:
        name = pkg.get("name", "")
        alternatives = _STUB_ALTERNATIVES.get(
            name.lower(),
            [
                {
                    "name": f"{name}-alternative",
                    "version": "latest",
                    "license": "MIT",
                    "reason": "[DEMO] Example alternative — check npm/PyPI for real options",
                }
            ],
        )
        results.append(
            {
                "package": name,
                "version": pkg.get("version", "*"),
                "reason": pkg.get("reason", "unknown"),
                "alternatives": alternatives,
            }
        )
    return {"results": results, "demo_mode": True}


def _live_replacements(
    packages: list[dict[str, str]],
    policy: dict | str | None,
) -> dict[str, Any]:
    """Best-effort live lookup: delegates to stubs (real impl can query npm/PyPI)."""
    return _stub_replacements(packages)


# ── MCP Resources ──────────────────────────────────────────────────────────────

@mcp.resource(
    "report://latest",
    description="Last compliance report from check_policy_compliance (project path, summary, violations).",
    mime_type="application/json",
)
def resource_report_latest() -> str:
    """Return the most recent policy compliance report from this session (JSON string)."""
    if _last_report is None:
        payload = {
            "message": "No report yet. Call check_policy_compliance(project_path, policy) first.",
            "report": None,
        }
    else:
        payload = _last_report
    return json.dumps(payload, ensure_ascii=False)


@mcp.resource(
    "sbom://latest/spdx",
    description="Last generated SPDX 2.3 JSON SBOM from generate_sbom(..., format='spdx').",
    mime_type="application/json",
)
def resource_sbom_latest_spdx() -> str:
    """Return the most recent SPDX SBOM from this session (JSON string)."""
    if _last_sbom_spdx is None:
        payload = {
            "message": "No SPDX SBOM yet. Call generate_sbom(project_path, format='spdx') first.",
            "sbom": None,
        }
    else:
        payload = {"project_name": _last_sbom_project_name, "sbom": _last_sbom_spdx}
    return json.dumps(payload, ensure_ascii=False)


@mcp.resource(
    "sbom://latest/cyclonedx",
    description="Last generated CycloneDX 1.5 JSON SBOM from generate_sbom(..., format='cyclonedx').",
    mime_type="application/json",
)
def resource_sbom_latest_cyclonedx() -> str:
    """Return the most recent CycloneDX SBOM from this session (JSON string)."""
    if _last_sbom_cyclonedx is None:
        payload = {
            "message": "No CycloneDX SBOM yet. Call generate_sbom(project_path, format='cyclonedx') first.",
            "sbom": None,
        }
    else:
        payload = {"project_name": _last_sbom_project_name, "sbom": _last_sbom_cyclonedx}
    return json.dumps(payload, ensure_ascii=False)


# ── MCP Prompts ───────────────────────────────────────────────────────────────

@mcp.prompt(
    description=(
        "Audit project dependencies for vulnerabilities and license risks, "
        "then suggest a remediation plan."
    )
)
def audit_dependencies_and_risks(project_path: str) -> str:
    return (
        f"Please audit the project at `{project_path}`:\n"
        "1. Call `analyze_project_dependencies` to get the full dependency graph.\n"
        "2. Call `scan_vulnerabilities` to list CVEs with severity.\n"
        "3. Call `scan_licenses` to list license risk flags.\n"
        "4. Call `check_policy_compliance` with the default policy to get violations.\n"
        "5. Summarise findings: must-fix (critical CVEs, denied licenses), "
        "should-fix (high CVEs, unknown licenses), nice-to-have (medium/low CVEs).\n"
        "6. Suggest `suggest_dependency_replacements` for the top violations."
    )


@mcp.prompt(
    description="Generate a license compliance report suitable for legal review."
)
def license_report_for_legal(project_path: str) -> str:
    return (
        f"Please produce a license compliance report for `{project_path}`:\n"
        "1. Call `scan_licenses` to list all dependency licenses.\n"
        "2. Call `check_policy_compliance` to identify denied or risky licenses.\n"
        "3. Format the output as a concise table grouped by license type "
        "(permissive / copyleft / unknown).\n"
        "4. For each copyleft or unknown license, include: package name, version, "
        "license name, risk level, and recommended action (replace / accept / review)."
    )


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
