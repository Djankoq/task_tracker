# Task Tracker

Backend на FastAPI с подключением к PostgreSQL через SQLAlchemy и psycopg2. Приложение использует схему `task_tracker` из предыдущего задания.

## Интеграция с Frontend

Отдельный React-проект расположен рядом с бэкендом: `../task_tracker_frontend`.

Для пользователей добавлены административные маршруты `POST /users/`, `GET /users/{id}`, `PUT /users/{id}`, `DELETE /users/{id}`. Создание требует `login`, `display_name`, `password` (8–128 символов), принимает `is_admin` (по умолчанию false). PUT заменяет публичные поля и при наличии `password` обновляет пароль; при отсутствии поля хеш сохраняется. Пароли хешируются PBKDF2-HMAC-SHA256 (600 000 итераций, случайная соль). В ответах нет паролей и хешей. Администратор не может удалить себя или снять с себя административную роль. Связанные записи препятствуют удалению (409), правила остальных сущностей сохранены. Вход по паролю пока не предусмотрен: API использует существующие Bearer-сеансы.

`GET /projects/{id}/members` возвращает действующих участников доступного проекта с ролями, ID, именем и логином. Фронтенд использует этот маршрут для выбора исполнителя и доступных переходов статуса. Этот маршрут не меняет состав участников.

Списки поддерживают включительные числовые фильтры `user_id_min/max` для пользователей, `task_count_min/max` для проектов и `task_id_min/max` для задач. У задач также есть `due_from` и `due_to` с датой, временем и часовым поясом. Фильтры сочетаются с поиском, статусом и другими условиями и применяются до расчёта пагинации.

Для демонстрации UI без изменения рабочей базы запустите `.\.venv\Scripts\python.exe scripts/demo_server.py`. Нужен работающий PostgreSQL и право CREATEDB у роли из `.env`, как для тестов. Скрипт создаёт новую временную базу, загружает схему и seed, запускает API на `127.0.0.1:8002`. При штатной остановке Ctrl+C удаляется только созданная им демонстрационная база. Подробный сценарий защиты — `../task_tracker_frontend/DEMO.md`.

```text
app/
├── __init__.py
├── main.py
├── config.py
├── database.py
├── dependencies.py
├── models/
│   ├── __init__.py
│   ├── auth_session.py
│   ├── enums.py
│   ├── project.py
│   ├── project_member.py
│   ├── task.py
│   ├── task_change.py
│   ├── task_comment.py
│   └── user.py
├── schemas/
│   ├── __init__.py
│   ├── common.py
│   ├── pagination.py
│   ├── project.py
│   ├── task.py
│   └── user.py
├── routers/
│   ├── __init__.py
│   ├── projects.py
│   ├── tasks.py
│   └── users.py
└── services/
    ├── __init__.py
    ├── crud.py
    ├── pagination.py
    └── user_service.py
.env
.env.example
requirements.txt
01_schema.sql
02_seed.sql
postman/
└── Task Tracker CRUD.postman_collection.json
README.md
```

## Запуск в Windows

Команды выполняются в PowerShell из корня проекта. Для нового экземпляра проекта создайте окружение командой `py -3.12 -m venv .venv`.

```powershell
. .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Если PowerShell блокирует активацию, используйте `.\.venv\Scripts\python.exe` вместо `python` в командах ниже.

### С подготовленной локальной базой

В этом рабочем каталоге база разработки `task_tracker_dev` хранится в `.postgres-data`. В `.env` уже указан адрес подключения. Из корня проекта запустите приложение и при необходимости PostgreSQL одной командой.

```powershell
.\start-dev.ps1
```

Если запускаете `app\main.py` кнопкой Run в PyCharm, сначала включите PostgreSQL из PowerShell.

```powershell
$pg = 'C:\Program Files\PostgreSQL\17\bin'
$data = Join-Path (Get-Location) '.postgres-data'
$log = Join-Path (Get-Location) '.postgres.log'
& "$pg\pg_ctl.exe" -D $data -l $log -o '-h 127.0.0.1 -p 55439' -w start
```

Чтобы остановить локальную базу после работы, выполните `& "$pg\pg_ctl.exe" -D $data -m fast -w stop`.

### С другой базой PostgreSQL

При первом запуске создайте отдельную пустую базу и выполните `01_schema.sql`, затем `02_seed.sql` для тестовых данных. Команды ниже предполагают, что PostgreSQL запущен на порту 5432, а `createdb` и `psql` доступны через `PATH`.

```powershell
$env:PGCLIENTENCODING = 'UTF8'
createdb -h 127.0.0.1 -U postgres -T template0 -E UTF8 --locale-provider=icu --icu-locale=ru task_tracker_dev
psql -X -h 127.0.0.1 -U postgres -d task_tracker_dev -v ON_ERROR_STOP=1 -f 01_schema.sql -f 02_seed.sql -f migrations/001_search_indexes.up.sql
```

Создайте `.env` по образцу `.env.example` и укажите фактические имя пользователя, пароль, хост, порт и имя базы. Специальные символы в пароле кодируйте для URL. Затем выполните `python -m app.main`. [Документация SQLAlchemy по строкам подключения](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls).

## Задание 2 Создание таблиц из ORM

Модели в `app/models` описывают все семь сущностей ER-диаграммы ПЗ 2. В `ProjectMember` ключ состоит из `project_id` и `user_id`. Исполнитель задачи связан с участием в том же проекте через составной внешний ключ `(project_id, assignee_id)`. Связи `Task.assignee_membership` и `ProjectMember.assigned_tasks` используются для чтения. Чтобы назначить исполнителя, запишите его идентификатор в `Task.assignee_id`.

Для демонстрации создайте пустую базу PostgreSQL `task_tracker_orm`. Укажите её `DATABASE_URL` в переменных запуска или в отдельной конфигурации PyCharm. Роли подключения нужно право на создание схемы в этой базе. В PowerShell с активным `.venv` запустите:

```powershell
$env:CREATE_TABLES = '1'
python -m app.main
```

FastAPI импортирует семь моделей в `app/main.py` и при старте создаёт схему `task_tracker` и её таблицы через `Base.metadata.create_all()`. Для обычной работы используйте базу, подготовленную скриптами `01_schema.sql` и `02_seed.sql`. Первый скрипт также устанавливает индексы, представление просрочки и триггеры бизнес-правил. [Документация SQLAlchemy по `create_all()`](https://docs.sqlalchemy.org/en/20/core/metadata.html#sqlalchemy.schema.MetaData.create_all).

Скриншоты DBeaver из проверочной базы:

- [Диаграмма семи таблиц и связей](screenshots/04-dbeaver-schema-diagram.jpg)
- [Столбцы и типы данных tasks](screenshots/01-dbeaver-tasks-columns.jpg)
- [Внешние ключи tasks](screenshots/02-dbeaver-tasks-foreign-keys.jpg)
- [Составной первичный ключ project_members](screenshots/03-dbeaver-project-members-primary-key.jpg)

## Проверка

В локальном `.env` задано `APP_PORT=8001`. Параметр применяется при запуске через `start-dev.ps1` и при прямом запуске `app\main.py` из PyCharm. Если порт занят, укажите другой свободный порт в `.env` и перезапустите приложение. Если `APP_PORT` отсутствует, используется `8000`.

В другом окне PowerShell выполните команды, пока приложение запущено.

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/users/me -Headers @{ Authorization = 'Bearer test-active-token' }
```

`GET /health` возвращает `{"status":"ok","database":"ok"}`. Приложение проверяет доступ к таблице `task_tracker.users` при запуске и при каждом запросе к `/health`. [Документация FastAPI по lifespan](https://fastapi.tiangolo.com/advanced/events/).

`GET /users/me` возвращает профиль Ольги Соколовой после свежей загрузки тестовых данных. Тестовый токен действует сутки с момента загрузки. Запрос с отсутствующим, истёкшим или отозванным токеном возвращает HTTP 401. Интерактивная документация доступна по адресу [Swagger UI](http://127.0.0.1:8001/docs).

## CRUD для проектов и задач

| Метод | Проекты | Задачи | Успешный ответ |
| --- | --- | --- | --- |
| POST | `/projects/` | `/tasks/` | `201` |
| GET | `/projects/` | `/tasks/` | `200`, объект с `items` и метаданными |
| GET | `/projects/{project_id}` | `/tasks/{task_id}` | `200`, одна запись |
| PUT | `/projects/{project_id}` | `/tasks/{task_id}` | `200`, полная замена редактируемых полей |
| PATCH | `/projects/{project_id}` | `/tasks/{task_id}` | `200`, обновление переданных полей |
| DELETE | `/projects/{project_id}` | `/tasks/{task_id}` | `204`, пустое тело |

Списки `/users/`, `/projects/` и `/tasks/` принимают `page` (от `1`, по умолчанию `1`), `per_page` (от `1` до `100`, по умолчанию `10`), `sort_by` и `sort_order` (`asc` или `desc`, по умолчанию `asc`). Старые `offset/limit` заменены этими параметрами. Неизвестные query-параметры возвращают `400`.

| Список | Разрешённые `sort_by` | По умолчанию |
| --- | --- | --- |
| `/users/` | `user_id`, `login`, `display_name`, `name`, `is_admin` | `user_id` |
| `/projects/` | `project_id`, `name`, `description` | `project_id` |
| `/tasks/` | `task_id`, `project_id`, `assignee_id`, `title`, `due_at`, `priority`, `status` | `task_id` |

`name` у пользователей — псевдоним `display_name`. Список пользователей доступен администратору и содержит только публичные поля профиля. `/users/me` по-прежнему доступен любому пользователю с действующим сеансом. При совпадении значений сортировки записи дополнительно упорядочиваются по ID по возрастанию. Приоритет и статус сортируются в порядке PostgreSQL ENUM: `low → medium → high` и `todo → in_progress → in_review → done`.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8001/users/?page=2&per_page=5&sort_by=name&sort_order=desc' -Headers @{ Authorization = 'Bearer test-admin-token' }
```

На свежих тестовых данных ответ содержит два пользователя в `items` и метаданные:

```json
{
  "items": [
    {"user_id": 3, "login": "anna", "display_name": "Анна Орлова", "is_admin": false},
    {"user_id": 1, "login": "admin", "display_name": "Алексей Волков", "is_admin": true}
  ],
  "total": 7,
  "page": 2,
  "per_page": 5,
  "total_pages": 2
}
```

Порядок строк зависит от collation базы PostgreSQL; состав `items` в примере иллюстративный. `total` считает только доступные пользователю записи до применения пагинации. Страница за пределами данных возвращает `items: []` с исходным `total`. Для пустого списка `total_pages: 0`.

## Валидация и единый формат ошибок

Исключения `NotFoundError`, `ConflictError`, `ValidationError`, `UnauthorizedError`, `ForbiddenError` и `ServiceUnavailableError` определены в `app/exceptions.py`. Глобальные обработчики в `app/error_handlers.py` преобразуют их, ошибки валидации FastAPI и ошибки маршрутизации в `ErrorResponse`:

```json
{
  "code": "validation_error",
  "message": "Invalid request data",
  "details": [
    {"loc": ["query", "per_page"], "msg": "Input should be less than or equal to 100", "type": "less_than_equal"}
  ]
}
```

`details` всегда является массивом; для ошибок без привязки к полям он пустой. Невалидные запросы возвращают `400` (`validation_error`), отсутствие сеанса — `401` (`unauthorized`), недостаточные права — `403` (`forbidden`), отсутствие записи — `404` (`not_found`), конфликт уникальности или удаления связанных записей — `409` (`conflict`). `/health` возвращает `503` (`service_unavailable`), когда база недоступна. Неожиданные ошибки возвращают `500` (`internal_error`) без внутренних данных; подробности записываются в журнал сервера. `401` сохраняет заголовок `WWW-Authenticate: Bearer`.

Схемы Pydantic проверяют положительные ID в диапазоне PostgreSQL `bigint`, непустой текст, отсутствие нулевого байта, приоритеты и статусы из заданных наборов, дату со смещением часового пояса, неизвестные поля. PATCH требует хотя бы одно поле и запрещает `null` для обязательных данных. `review_reason`, если задана, должна быть непустой и передаваться со статусом `in_progress`. Просроченные даты допустимы: проект поддерживает учёт просроченных задач. Проверки роли исполнителя, разрешений, переходов статуса и обязательной причины возврата с ревью выполняются с учётом состояния БД; триггеры PostgreSQL обеспечивают их в транзакции.

В Swagger нажмите **Authorize** и введите токен сеанса. В свежей тестовой базе `test-admin-token` даёт права администратора для записи проектов, `test-active-token` — права руководителя проекта `1`, а `test-executor-token` — права исполнителя с `user_id=3`. Пользователь видит проекты и задачи, доступные по его роли, администратор может читать все записи. Задача создаётся в статусе `todo`. При возврате задачи из `in_review` в `in_progress` руководитель передаёт `review_reason`. PostgreSQL сохраняет причину в комментарии и записывает историю перехода в той же транзакции.

## Коллекция Postman

Для прогона создайте отдельную пустую тестовую базу и загрузите `01_schema.sql` и `02_seed.sql` по инструкции выше. Действующие демонстрационные сеансы рассчитаны на первые сутки после загрузки. Если локальная база была заполнена предыдущей версией `02_seed.sql`, используйте свежую тестовую базу с обновлённым скриптом.

В Postman импортируйте [Task Tracker CRUD.postman_collection.json](postman/Task%20Tracker%20CRUD.postman_collection.json). В переменной коллекции `base_url` укажите адрес запущенного API и выполните **Run collection** в исходном порядке. Коллекция сохраняет ID созданных записей, проверяет их обновление и удаляет их в рамках прогона.

Коллекция содержит 116 запросов, включая фильтрацию, поиск, статистику и рейтинг проектов. Среди проверок пагинации — пример `/users/?page=2&per_page=5&sort_by=name&sort_order=desc`, страницы проектов и задач, значения по умолчанию, размер страницы `100`, сортировку по ID в обратном порядке, пустую страницу, ошибки диапазонов, форматов и неизвестных полей сортировки. Общий тест проверяет `ErrorResponse` для всех ответов с ошибками. CRUD-сценарии проверяют коды `400/401/403/404/409`, включая ошибки бизнес-правил PostgreSQL.

Ту же коллекцию можно запустить из корня проекта через Postman CLI или Newman. [Документация Postman CLI](https://learning.postman.com/docs/postman-cli/postman-cli-run-collection), [документация Newman](https://learning.postman.com/docs/reference/newman-cli/installing-running-newman).

```powershell
npx --yes --package=postman-cli -- postman collection run 'postman/Task Tracker CRUD.postman_collection.json'
npx --yes newman@6.2.2 run 'postman/Task Tracker CRUD.postman_collection.json'
```

## Автоматические тесты

Запустите PostgreSQL и установите зависимости для разработки:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q --tb=short
```

Тесты создают отдельную базу `task_tracker_test_<uuid>` на сервере из `DATABASE_URL`, загружают SQL-схему и свежие тестовые данные, а затем удаляют её. Роль подключения должна иметь право `CREATEDB`. Данные рабочей базы не меняются. Каждый тест выполняется в откатываемой транзакции. Проверяются три списка, все поля сортировки, доступность записей и метаданных, некорректные параметры, схемы входных данных, единый формат ошибок, переходы статуса и описание OpenAPI.

Для полного прогона Postman на такой же отдельной базе установите Node.js с `npx` и выполните:

```powershell
$env:RUN_POSTMAN = '1'
python -m pytest tests/test_postman.py -q -s --tb=short
Remove-Item Env:RUN_POSTMAN
```

Проверка сама запускает тестовый HTTP-сервер на свободном порту и Newman 6.2.2, затем останавливает сервер и удаляет временную базу. При первом запуске Newman загружается через `npx`.

## Фильтрация и поиск

Все параметры необязательны. Условия разных фильтров объединяются через AND. Параметр `search` ищет подстроку через ILIKE хотя бы в одном из двух полей. Символы `%`, `_` и `/` в строке поиска воспринимаются буквально.

| Список | Фильтры | Поля для `search` |
| --- | --- | --- |
| `GET /users/` | `is_admin`, `is_active`, `project_id` (действующее участие) | `login`, `display_name` |
| `GET /projects/` | `name` (точное совпадение), `member_id` (действующее участие), `has_tasks` | `name`, `description` |
| `GET /tasks/` | `project_id`, `assignee_id`, `status`, `priority`, диапазон `due_from` и `due_to` по сроку | `title`, `description` |

Границы срока включительны. Можно передать одну границу или обе. Укажите время с часовым поясом, например `2026-12-01T00:00:00Z`. Обратный диапазон возвращает HTTP 400. Ответ содержит число совпадений после применения фильтров, поиска и проверки доступа. Затем API сортирует совпадения и выдаёт запрошенную страницу.

```http
GET /tasks/?project_id=1&priority=high&search=api&sort_by=due_at&sort_order=desc&page=1&per_page=5
```

## Статистика и отчёт

Все три маршрута требуют Bearer-токен. Администратор получает данные по всем проектам, остальные пользователи — по проектам с действующим участием.

| Запрос | Результат |
| --- | --- |
| `GET /stats/summary` | Число видимых проектов, сумма задач и среднее число задач на проект. Проекты без задач входят в знаменатель. Если проектов нет, среднее равно `null`. |
| `GET /stats/tasks-by-status` | Число задач в каждой непустой группе по статусу. При отсутствии задач возвращается `[]`. |
| `GET /reports/top-projects?limit=5` | Рейтинг проектов по числу задач с названием, ID и количеством. При равенстве выше проект с меньшим ID. По умолчанию выдаются 5 строк, допустимо 1–100. |

На свежем наборе данных администратор получает `{"total_projects":2,"total_tasks":8,"avg_tasks_per_project":4.0}`. Руководитель первого проекта видит один проект с шестью задачами.

## Индексы и EXPLAIN ANALYZE

Для существующей базы запустите миграцию через psql, указав свои параметры подключения. Для новой базы миграция уже включена в команду установки выше.

```powershell
psql -X -h 127.0.0.1 -p 55439 -U task_tracker_dev -d task_tracker_dev -v ON_ERROR_STOP=1 -f migrations/001_search_indexes.up.sql
psql -X -h 127.0.0.1 -p 55439 -U task_tracker_dev -d task_tracker_dev -v ON_ERROR_STOP=1 -f scripts/explain_search.sql
```

Для отката выполните `migrations/001_search_indexes.down.sql`. Миграция добавляет пять GIN-индексов с `pg_trgm`, дополняя существующий индекс заголовка задачи. Это покрывает обе стороны каждого поискового OR. Исходная схема также содержит составные индексы по проекту, статусу, приоритету, исполнителю и сроку задач.

В измерении на временной копии структуры проектов было 30 000 строк и 30 совпадений по подстроке `marker`. До добавления индексов PostgreSQL выбрал Seq Scan, проверил 310 локальных буферов и выполнил запрос за 23,674 мс. С индексами план объединил два Bitmap Index Scan через BitmapOr, обратился к 52 буферам и вернул те же 30 строк за 0,097 мс. Это измерение одного селективного поиска. На малых таблицах или для частого слова планировщик может выбрать последовательное сканирование.

## Примеры запросов SQLAlchemy

Фильтры добавляются к базовому `select()` до подсчёта `total`, сортировки и пагинации. Например, задачи проекта с определённым статусом и исполнителем:

```python
from sqlalchemy import func, select
from app.models import Project, Task

statement = select(Task).where(
    Task.project_id == project_id,
    Task.status == "in_progress",
    Task.assignee_id == assignee_id,
)
# Нечувствительный к регистру поиск подстроки; %, _ и escape-символ экранируются.
statement = statement.where(Task.title.icontains(search, autoescape=True))
```


`JOIN` связывает строки таблиц, `LEFT OUTER JOIN` сохраняет проекты без задач. `GROUP BY` формирует группы, а `count`, `min`, `max`, `sum`, `avg` вычисляют агрегаты. Пример количества задач в каждом проекте, включая проекты с нулём задач:

```python
statement = (
    select(Project.project_id, Project.name, func.count(Task.task_id).label("task_count"))
    .outerjoin(Task, Task.project_id == Project.project_id)
    .group_by(Project.project_id, Project.name)
)
```

Здесь нужен `count(Task.task_id)`: `count(*)` посчитал бы также строку проекта без задачи. `WHERE` фильтрует строки до группировки, `HAVING` — результаты группировки, например `.having(func.count(Task.task_id) >= 3)`. [WHERE и JOIN](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#the-where-clause), [GROUP BY, HAVING и агрегаты](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#aggregate-functions-with-group-by-having).

## Подготовка к следующему занятию

В SQLAlchemy блок `with session.begin():` фиксирует изменения при успешном завершении и откатывает их при исключении. `flush()` отправляет накопленные изменения в базу внутри текущей транзакции. Это позволяет получить ID новой записи и использовать его в следующей операции до общего коммита. [Транзакции SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html).

Сценарий для следующей работы — передача открытых задач при выходе исполнителя из проекта. В одной транзакции руководитель блокирует записи участников и затронутых задач, проверяет роль нового исполнителя, переназначает задачи и завершает прежнее участие. Если одна из проверок не пройдена, вся операция откатывается вместе с историей переназначений.
