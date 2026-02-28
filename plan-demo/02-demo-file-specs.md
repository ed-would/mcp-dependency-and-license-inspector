# Спецификации файлов демо-проекта

Краткие форматы файлов в `demo_project/` для однозначной реализации.

---

## policy_strict.yaml

YAML, ключи верхнего уровня:

- `allowed_licenses`: список строк (MIT, Apache-2.0, BSD-3-Clause, ISC)
- `denied_licenses`: список строк (GPL-2.0, GPL-3.0, AGPL-3.0)
- `deny_unknown_license`: boolean (true)
- `block_critical_cve`: boolean (true)
- `block_high_cve`: boolean (false)

Соответствует формату из `plan/04-architecture-and-api.md` и загрузке через `load_policy()`.

---

## package.json (корень)

- `name`: строка (например `demo-mcp-inspector`)
- `version`: строка (например `1.0.0`)
- `license`: строка `"MIT"`
- `dependencies`: объект; обязательно ключ `lodash` со значением `"4.17.15"` или `"^4.17.15"` (парсер приводит к 4.17.15); плюс например `express`: `"^4.18.2"`

Опционально `devDependencies` для разнообразия (не обязательно для стабов).

---

## package-lock.json

Формат npm lockfile v2/v3:

- `name`, `version` в корне (как в package.json)
- `lockfileVersion`: 2 или 3
- `packages`: объект:
  - ключ `""`: объект корневого пакета с `name`, `version` (корень парсер пропускает)
  - ключ `"node_modules/lodash"`: объект с `"name": "lodash"`, `"version": "4.17.15"`
  - ключ `"node_modules/express"`: объект с `"name": "express"`, `"version": "4.18.2"` (или актуальная версия)

Парсер в `parsers/npm.py` использует только `packages`; для каждой записи кроме `""` берёт `name` и `version` из `pkg_data`. Поле `direct`: для ключа с одним вхождением `node_modules/` считаются direct. То есть `node_modules/lodash` и `node_modules/express` — direct.

---

## requirements.txt

Строки (по одной зависимости):

- `requests==2.27.0` — обязательно для стаба CVE
- `flask>=2.3.0` или с пиннированной версией
- `click~=8.1.0` или аналог

Комментарии и пустые строки допускаются. Парсер извлекает имя и версию; для `==` версия берётся как есть.

---

## pyproject.toml

- Секция `[project]`:
  - `name`: строка (например `demo-py-app`)
  - `version`: строка
  - `license`: строка `"Apache-2.0"` или `{ text = "Apache-2.0" }`
  - `dependencies`: список PEP 508 строк (например `"httpx>=0.27.0"`, `"pydantic>=2.7.0"`)

Опционально `[tool.poetry]` с `name`, `version`, `license`, `dependencies` — парсер объединяет оба источника.

---

## pkg_with_gpl/package.json

Минимальный манифест:

- `name`: уникальное имя (например `gpl-demo-lib`)
- `version`: строка (например `1.0.0`)
- `license`: строка `"GPL-3.0"`
- `dependencies`: пустой объект `{}` (или одна лёгкая зависимость для разнообразия)

Нужен только чтобы при сканировании `demo_project/` в license_metadata попала запись с GPL-3.0 и `check_policy_compliance` с `policy_strict.yaml` выдал нарушение.

---

## README.md

Краткий текст: назначение папки — демо-проект для воспроизводимой проверки MCP «Инспектор зависимостей и лицензий»; не устанавливать зависимости, не содержать секретов; сценарий описан в корневом `DEMO.md`.
