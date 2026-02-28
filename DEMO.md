# Демо-сценарий: Dependency & License Inspector MCP

Сценарий выполняется **без платных сервисов и API-ключей**. Всё через **Docker** и **MCP Inspector**.
Время: 3–5 минут.

---

## Что нужно перед началом

1. **Сервер запущен** — выполните шаги 1–3 из [README.md — Быстрый старт](README.md#быстрый-старт): сборка образа, при желании smoke, затем `docker run ... serve`. Терминал с сервером оставьте открытым.

2. **MCP Inspector подключён** — выполните шаг 4 из README: запустите Inspector и подключитесь к `http://localhost:8000/mcp` (транспорт Streamable HTTP). В списке должны появиться инструменты сервера.

Демо-проект **`demo_project`** уже внутри контейнера; в вызовах инструментов используйте путь **`demo_project`**.

---

## Шаг 1. Проверка соответствия политике

В MCP Inspector выберите инструмент **`check_policy_compliance`** и вызовите его с аргументами:

| Параметр       | Значение                            |
| -------------- | ----------------------------------- |
| `project_path` | `demo_project`                      |
| `policy_path`  | `demo_project/policy_strict.yaml`   |

Поле **`policy_path`** — обычный текст, кавычки вводить не нужно. (Вместо него можно использовать `policy`, но тогда в режиме JSON нужны кавычки: `"demo_project/policy_strict.yaml"`.)

Нажмите выполнить и откройте ответ. Ожидаемо: **`compliant`** = `false`, **`violations_count`** > 0, в **`violations`** — список нарушений (type, package_name, details, recommendation).

---

## Шаг 2. Рекомендации по заменам

Выберите инструмент **`suggest_dependency_replacements`** и вызовите с аргументом **`packages`** (массив):

```json
[
  {
    "name": "lodash",
    "version": "4.17.15",
    "ecosystem": "npm",
    "reason": "cve"
  },
  {
    "name": "requests",
    "version": "2.27.0",
    "ecosystem": "pypi",
    "reason": "cve"
  }
]
```

В ответе в **`results`** у каждого пакета будет список **`alternatives`** (name, version, license, reason). В демо-режиме появятся стаб-альтернативы (например lodash-es, remeda, httpx), в ответе **`demo_mode`** = `true`.

---

## Итог

После двух вызовов видна полная картина нарушений политики и список рекомендуемых замен — без ручного запуска отдельных утилит.

---

## Проверка типичных проблем (troubleshooting)

Три демо-кейса помогают убедиться, что окружение настроено правильно, и понять, что проверять, если основной сценарий не проходит.

### Кейс A. Доступность сервера и подключение Inspector

**Цель:** убедиться, что сервер отвечает и MCP Inspector видит инструменты.

**Шаги:**

1. Убедитесь, что контейнер запущен: в терминале должна быть команда `docker run ... serve` без выхода; при необходимости перезапустите её по README (шаги 1–3).
2. В MCP Inspector проверьте, что в списке инструментов есть, например, `analyze_project_dependencies` и `check_policy_compliance`. Если списка нет — нажмите **Connect** с URL `http://localhost:8000/mcp` и транспортом **Streamable HTTP** (шаг 4 README).
3. Вызовите инструмент **`analyze_project_dependencies`** с одним аргументом: `project_path` = `demo_project`. Нажмите выполнить.

**Ожидаемый результат:** ответ 200, в теле JSON с полями `total_packages`, `packages`, `ecosystem_counts`; массив `packages` не пустой.

**Если не проходит — что проверить:**

- Контейнер не запущен или завершился → перезапустите `docker run --rm -p 8000:8000 --memory=2048m --cpus=2 -e DEMO_MODE=true dependency-inspector-mcp serve`.
- В Inspector ошибка подключения → проверьте, что в URL указано именно `http://localhost:8000/mcp`, транспорт **Streamable HTTP**; порт 8000 не занят другим процессом (`lsof -i :8000`).
- Ошибка «Path does not exist» → для этого кейса используйте строго `demo_project` (без слэша в начале, без опечаток).

---

### Кейс B. Неверный путь к проекту или политике

**Цель:** воспроизвести типичную ошибку пути и убедиться, что исправление работает.

**Шаги:**

1. В MCP Inspector выберите **`check_policy_compliance`**.
2. Вызовите с **неверными** аргументами: `project_path` = `not_exist`, `policy_path` = `demo_project/policy_strict.yaml`. Выполните.
3. Убедитесь, что в ответе есть ошибка (например «Path does not exist» или «not a directory»).
4. Исправьте только `project_path` на `demo_project`, остальное оставьте. Выполните снова.
5. Убедитесь, что ответ успешный: есть поля `compliant`, `violations_count`, `violations`.

**Ожидаемый результат:** при шаге 2 — ошибка валидации; при шаге 4 — успешный JSON без ошибки.

**Если не проходит — что проверить:**

- При шаге 2 нет ошибки (сервер «принял» неверный путь) → убедитесь, что вызываете именно `check_policy_compliance` и передаёте строку `not_exist` в `project_path`.
- При шаге 4 снова ошибка «Path does not exist» → в `project_path` должно быть ровно `demo_project` (сервер в Docker работает из `/app`, там лежит каталог `demo_project`). Не используйте `/demo_project` или `./demo_project`, если в документации не указано иное.
- Ошибка загрузки политики → укажите **`policy_path`**: `demo_project/policy_strict.yaml` (без кавычек). Либо в `policy` — тогда в JSON нужны кавычки.

---

### Кейс C. Демо-режим и стаб-данные (CVE, замены)

**Цель:** убедиться, что при `DEMO_MODE=true` сервер возвращает стаб-уязвимости и стаб-замены без внешних API.

**Шаги:**

1. Убедитесь, что контейнер запущен с переменной **`DEMO_MODE=true`** (в команде `docker run` должно быть `-e DEMO_MODE=true`). Если нет — остановите контейнер (Ctrl+C) и запустите заново с этой переменной.
2. Вызовите **`check_policy_compliance`** с `project_path` = `demo_project`, `policy_path` = `demo_project/policy_strict.yaml`. Откройте ответ.
3. Проверьте: в массиве **`violations`** есть хотя бы одно нарушение с `type` = `cve` (например пакет lodash или requests). В ответе может быть поле **`demo_mode`** = `true`.
4. Вызовите **`suggest_dependency_replacements`** с `packages` = `[{"name": "lodash", "version": "4.17.15", "ecosystem": "npm", "reason": "cve"}]`. В ответе в **`results`** у lodash должен быть непустой список **`alternatives`** (например lodash-es, remeda); в теле ответа **`demo_mode`** = `true`.

**Ожидаемый результат:** нарушения типа `cve` присутствуют; у lodash есть стаб-альтернативы; `demo_mode` = `true`.

**Если не проходит — что проверить:**

- Нет нарушений по CVE в шаге 3 → перезапустите контейнер с **`-e DEMO_MODE=true`**; политика `policy_strict.yaml` должна включать проверку CVE (block_critical_cve / block_high_cve). Повторно выполните шаг 2.
- Пустой список `alternatives` для lodash в шаге 4 → проверьте, что в запросе передаёте массив с полем `reason` (например `"cve"`); перезапуск с `DEMO_MODE=true` при необходимости.
- В ответах нет поля `demo_mode` или оно `false` → переменная окружения не применилась; пересоздайте контейнер с явным `-e DEMO_MODE=true`.

---

## Контракт Docker (справка)

Контейнер поддерживает команды **`serve`** и **`smoke`**; при **serve** сервер слушает порт 8000, endpoint **`/mcp`** (MCP Streamable HTTP), **`/health`** — проверка готовности. Подробности запуска — в [README.md](README.md).

---

## Типичные проблемы

| Ситуация                  | Решение                                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| «Path does not exist»     | Указывать `project_path` как **`demo_project`** (без ведущего слэша).                                                           |
| Ошибка загрузки политики  | Указывать **`policy_path`**: `demo_project/policy_strict.yaml` (без кавычек) или `policy`: `"demo_project/policy_strict.yaml"`. |
| Нет нарушений по CVE      | Запускать контейнер с **`-e DEMO_MODE=true`** (как в README).                                                                   |
| Inspector не подключается | Контейнер запущен с **`-p 8000:8000`**, в Inspector выбран транспорт **Streamable HTTP** и URL **`http://localhost:8000/mcp`**. |
