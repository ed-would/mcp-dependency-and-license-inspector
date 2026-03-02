# Dependency & License Inspector MCP — для разработчиков и AppSec

Подробное описание: установка, запуск, инструменты, примеры вызовов и ограничения.

---

## Установка и запуск

### Docker (рекомендуется)

Демо работает без установки Python на хост.

1. **Сборка образа**
   ```bash
   docker build -t dependency-inspector-mcp .
   ```

2. **Проверка готовности (smoke)**
   ```bash
   docker run --rm dependency-inspector-mcp smoke
   ```
   Успех: «smoke: ok», код выхода 0.

3. **Запуск MCP-сервера**
   ```bash
   docker run --rm -p 8000:8000 --memory=2048m --cpus=2 -e DEMO_MODE=true dependency-inspector-mcp serve
   ```
   Сервер слушает порт 8000; endpoint для клиента: `http://localhost:8000/mcp` (транспорт Streamable HTTP).

4. **Подключение MCP Inspector**
   ```bash
   npx -y @modelcontextprotocol/inspector
   ```
   В браузере: Transport — Streamable HTTP, URL — `http://localhost:8000/mcp`, Connect.

### Локальный запуск (stdio)

Для Cursor / Claude Code / VS Code: добавьте MCP-сервер в конфиг с командой запуска Python-модуля (см. README в корне репо). Требуется Python 3.11+, зависимости из `requirements.txt`.

---

## Основные tools

| Инструмент | Назначение |
|------------|------------|
| `analyze_project_dependencies` | Граф зависимостей (direct + transitive) по манифестам npm/Python |
| `scan_vulnerabilities` | CVE через OSV API или стабы в DEMO_MODE |
| `scan_licenses` | Лицензии и флаги риска (copyleft, unknown, multiple) |
| `check_policy_compliance` | Проверка по YAML/JSON-политике: нарушения и рекомендации |
| `generate_sbom` | SBOM в формате SPDX 2.3 или CycloneDX 1.5 (JSON) |
| `suggest_dependency_replacements` | Рекомендации по замене проблемных пакетов (CVE/лицензия) |

---

## Примеры вызовов (demo_project)

**Проверка политики:**
```json
{
  "project_path": "demo_project",
  "policy": "demo_project/policy_strict.yaml"
}
```
Инструмент: `check_policy_compliance`.

**Рекомендации по заменам:**
```json
{
  "packages": [
    {"name": "lodash", "ecosystem": "npm", "reason": "cve"},
    {"name": "requests", "ecosystem": "pypi", "reason": "license"}
  ]
}
```
Инструмент: `suggest_dependency_replacements`.

Подробные параметры и форматы ответов — в [README.md](../README.md) в корне репозитория.

---

## Ограничения по ресурсам и безопасности (из .cursorrules)

| Параметр | Значение |
|----------|----------|
| Docker image | ≤ 500 MB |
| CPU | 2.0 |
| RAM | 2048 MB |
| LLM в ядре | нет (детерминированная логика) |
| Секреты | не хранить в репо; только через переменные окружения |
| Детерминизм | результаты tools определяются только входными данными |

**Переменные окружения:** `ALLOWED_BASE_PATH`, `MAX_INPUT_PATH_LENGTH`, `MAX_EXCLUDE_DIRS`, `MAX_POLICY_PAYLOAD_BYTES`, `TOOL_TIMEOUT_SECONDS`, `DEMO_MODE` — см. `.env.example` и plan/05-architecture-and-api.md.

**Безопасность:** сервер не выполняет произвольные shell-команды; операции — чтение файлов и HTTP (OSV). API-ключи — только через env, не в коде и не в образе.
