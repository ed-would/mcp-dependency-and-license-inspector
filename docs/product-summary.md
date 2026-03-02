# Резюме продукта / Product Summary

## Русская версия (для технического руководителя и жюри)

**Dependency & License Inspector MCP** — детерминированный MCP-сервер для анализа зависимостей, лицензий и уязвимостей проекта. Ядро построено без вызовов LLM: результаты инструментов однозначно определяются входными данными (манифесты, политика, конфиг). Сервер предоставляет шесть инструментов: `analyze_project_dependencies` (граф зависимостей), `scan_vulnerabilities` (CVE через OSV или стабы), `scan_licenses` (лицензии и флаги риска), `check_policy_compliance` (проверка по YAML/JSON-политике), `generate_sbom` (SPDX/CycloneDX), `suggest_dependency_replacements` (рекомендации по заменам). Единая точка входа для npm и Python; результаты в виде структурированного JSON — удобны для интерпретации в чате с ИИ.

**Для кого:** разработчики в AI-редакторах (Cursor, Claude Code, VS Code), инженеры по безопасности (AppSec), юристы и compliance. Главная ценность — сокращение времени аудита с часов до минут, раннее выявление критичных CVE и недопустимых лицензий, готовность к регуляторным требованиям за счёт SBOM.

**Ограничения:** демо и тесты работают без платных API (OSV — бесплатный; при `DEMO_MODE=true` — стабы); Docker-образ ≤500 MB; лимиты CPU 2.0, RAM 2048 MB; транспорты stdio и Streamable HTTP; без LLM в ядре.

---

## English version (for GitHub and external audience)

**Dependency & License Inspector MCP** is a deterministic MCP server for dependency, license, and vulnerability analysis. The core is LLM-free: tool outputs are fully determined by inputs (manifests, policy config). Six tools are available: `analyze_project_dependencies`, `scan_vulnerabilities`, `scan_licenses`, `check_policy_compliance`, `generate_sbom`, and `suggest_dependency_replacements`. Single entry point for npm and Python; structured JSON responses for easy interpretation in AI chat and agent workflows.

**Target users:** developers in AI editors (Cursor, Claude Code, VS Code), AppSec engineers, and legal/compliance teams. Main value: faster audits (hours → minutes), early detection of critical CVEs and non-compliant licenses, SBOM output for supply chain transparency.

**Constraints:** demo and tests run without paid APIs (OSV is free; stubs used when `DEMO_MODE=true`); Docker image ≤500 MB; CPU 2.0, RAM 2048 MB; stdio and Streamable HTTP transport; no LLM in core. Docker contract: `serve` (MCP server), `smoke` (health check).
