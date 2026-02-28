# План демо-сценария для MCP «Инспектор зависимостей и лицензий»

## Цель

Реализовать минимальный демо-проект `demo_project/` и документ `DEMO.md`, чтобы наглядно проверить все 6 MCP tools без внешних платных сервисов и ключей. Для каждого инструмента — 1–2 примера с предсказуемым результатом (в т.ч. уязвимости и лицензии через стабы/фикстуры).

---

## 1. Соответствие tools → примеры в демо

| Tool | Что должно быть в демо | Ожидаемый результат (DEMO_MODE=true) |
|------|------------------------|--------------------------------------|
| **analyze_project_dependencies** | Несколько манифестов (npm + Python), lock-файлы опционально | Список пакетов, сводка по экосистемам, direct/transitive |
| **scan_vulnerabilities** | Пакеты, совпадающие со стабами: `lodash` 4.17.15 (npm), `requests` 2.27.0 (pypi) | CVE-стабы (GHSA-demo-npm-001, CVE-2023-DEMO-002), счётчики по severity |
| **scan_licenses** | Корневые лицензии в package.json / pyproject.toml; зависимости без лицензии в манифестах → UNKNOWN | Mix: MIT, Apache-2.0, GPL-3.0 (для нарушения), UNKNOWN; флаги is_copyleft, is_unknown |
| **check_policy_compliance** | Файл политики в демо (allowed/denied, deny_unknown_license, block_critical_cve) + пакеты с GPL или unknown | compliant: false, список violations (license/cve/unknown_license), рекомендации |
| **generate_sbom** | Тот же набор манифестов | SPDX 2.3 JSON и CycloneDX 1.5 JSON с компонентами и зависимостями |
| **suggest_dependency_replacements** | Пакеты из стабов: lodash, requests (и опционально moment) | Стаб-альтернативы: lodash→lodash-es/remeda, requests→httpx, moment→date-fns/dayjs |

Источники стабов в коде:

- Уязвимости: `src/mcp_dependency_inspector/core/vulnerability_scanner.py` — `DEMO_VULNERABILITIES` (lodash 4.17.15, requests 2.27.0).
- Замены: `src/mcp_dependency_inspector/server.py` — `_STUB_ALTERNATIVES` (lodash, requests, moment).

---

## 2. Структура `demo_project/`

Требования: размер до 10 МБ; только текстовые манифесты и конфиги; без секретов, токенов и крупных бинарников.

```
demo_project/
├── README.md                 # Краткое описание: «Демо для проверки MCP Inspector»
├── policy_strict.yaml        # Политика: allowed MIT/Apache/BSD, denied GPL/AGPL, deny_unknown_license, block_critical_cve
├── package.json              # Корень npm: name, version, license "MIT", deps: lodash@4.17.15, express
├── package-lock.json         # Минимальный lock с lodash 4.17.15 (и при необходимости express) для точных версий
├── requirements.txt          # requests==2.27.0, flask, click (и др. по желанию, без тяжёлых)
├── pyproject.toml            # [project] name, license Apache-2.0, dependencies (httpx, pydantic и т.д.)
├── pkg_with_gpl/
│   └── package.json          # Отдельный «проект» с license "GPL-3.0" для проверки нарушений политики
```

Пояснения:

- **package.json (корень):** зависимости с точными версиями, совместимыми со стабами: например `lodash` с версией 4.17.15 (в lock — 4.17.15), чтобы в DEMO_MODE стаб уязвимости сработал.
- **package-lock.json:** минимальный v2/v3 с полем `packages`, содержащим как минимум корень и `lodash@4.17.15` (и при необходимости express и их транзитивы в минимальном объёме).
- **requirements.txt:** строка `requests==2.27.0` обязательна для стаба CVE; остальное — лёгкие пакеты.
- **pyproject.toml:** даёт второй экосистему (pypi), корневую лицензию (например Apache-2.0).
- **pkg_with_gpl/package.json:** отдельный манифест с `"license": "GPL-3.0"` для нарушения политики.
- **policy_strict.yaml:** allowed_licenses, denied_licenses (GPL-2.0, GPL-3.0, AGPL-3.0), deny_unknown_license: true, block_critical_cve: true, block_high_cve: false.

Исключения: в `exclude_dirs` сервера уже фигурируют `node_modules`, `.venv`, `__pycache__`, `target`, `.git` — папки с артефактами в демо не создаём.

---

## 3. Содержимое ключевых файлов (референс)

- **policy_strict.yaml:** allowed_licenses (MIT, Apache-2.0, BSD-3-Clause, ISC), denied_licenses (GPL-2.0, GPL-3.0, AGPL-3.0), deny_unknown_license: true, block_critical_cve: true, block_high_cve: false.
- **package.json (корень):** name, version, "license": "MIT", dependencies: lodash 4.17.15 или ^4.17.15, express ^4.18.2.
- **package-lock.json:** минимальная структура npm lockfile v2/v3: корень "" и пакеты в `packages` с lodash 4.17.15.
- **requirements.txt:** requests==2.27.0, flask, click и т.п.
- **pyproject.toml:** [project] name, version, license Apache-2.0, dependencies (httpx, pydantic).
- **pkg_with_gpl/package.json:** name (уникальный), version, "license": "GPL-3.0", dependencies: {} или одна лёгкая зависимость.

---

## 4. Обновление DEMO.md

1. В качестве стандартного пути для всех примеров использовать `demo_project/`.
2. Пошаговый сценарий под каждый tool: запуск MCP с DEMO_MODE=true; вызовы analyze_project_dependencies, scan_vulnerabilities, scan_licenses, check_policy_compliance, generate_sbom, suggest_dependency_replacements с ожидаемыми результатами.
3. Проверка без MCP-клиента: путь `demo_project` вместо `tests/fixtures`.
4. Указать: сценарий выполняется без платных сервисов и API-ключей; при отсутствии сети или DEMO_MODE используются стабы.

---

## 5. Проверка ограничений

- **Размер до 10 МБ:** только манифесты и README; без node_modules, .venv, бинарников.
- **Безопасность:** нет приватных данных, токенов, ключей.
- **Достаточность для DEMO.md:** сценарий полностью проходится по `demo_project/` и покрывает все 6 tools.

---

## 6. Порядок реализации

1. Создать папку `plan-demo/` и файл `01-demo-scenario-plan.md`.
2. Опционально добавить `02-demo-file-specs.md`.
3. Создать `demo_project/` и все перечисленные файлы.
4. Обновить `DEMO.md`.
5. Прогнать сценарий: запуск сервера с DEMO_MODE, вызов каждого tool, проверка ответов.
