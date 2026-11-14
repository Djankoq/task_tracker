# Task Tracker

Backend на FastAPI с подключением к PostgreSQL через SQLAlchemy и psycopg2. Приложение использует схему `task_tracker` из предыдущего задания.

```text
app/
├── __init__.py
├── main.py
├── config.py
├── database.py
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
│   └── user.py
├── routers/
│   ├── __init__.py
│   └── users.py
└── services/
    ├── __init__.py
    └── user_service.py
.env
.env.example
requirements.txt
01_schema.sql
02_seed.sql
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
psql -X -h 127.0.0.1 -U postgres -d task_tracker_dev -v ON_ERROR_STOP=1 -f 01_schema.sql -f 02_seed.sql
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
