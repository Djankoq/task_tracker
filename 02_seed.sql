-- Test fixtures for an empty task_tracker schema. Demo password: TaskTrackerDemo2026!
BEGIN;
SET LOCAL search_path = task_tracker, pg_catalog;

INSERT INTO users (login, display_name, password_hash, is_admin, is_active) VALUES
    ('admin', 'Алексей Волков', '$2b$12$57gLASikQivYuIDNWDT/OuNDql8PtS87i551QzRIlvNsnc4LDOL5W', true, true),
    ('olga', 'Ольга Соколова', '$2b$12$.8QP7ctiTJ9AiZ.cKR8k8eQb8kah7WtaTGd0g.Odj3NapX7QI2sUq', false, true),
    ('anna', 'Анна Орлова', '$2b$12$4knBNcczgl4VYUSHGSmTy.Ra/zx.ItCJqvLcmoUhN2en4wG5NQTDW', false, true),
    ('ivan', 'Иван Егоров', '$2b$12$xrLHuE3Dq5TlqVtk5KN3LuN89kvGilJobVLackivuRf8ShUQ6t9va', false, true),
    ('maria', 'Мария Котова', '$2b$12$lysXujdGGXa3/vzHF/RAZuE7yPGOLEO6zp1haaPxSttXM5yljziMu', false, true),
    ('dmitry', 'Дмитрий Беляев', '$2b$12$jNm9zx6bvbslCtKE0/UiR.n5OQ1Ol9bOK1uUaJwSoXYmGkdF8rQ6u', false, true),
    ('pavel', 'Павел Морозов', '$2b$12$5FHia8NjVmSCXlWhLlhAj.g3QqmKZ/t4aXO0MTH73cOH1uZWdEpGa', false, false);

INSERT INTO projects (name, description) VALUES
    ('Личный кабинет', 'Разработка кабинета для клиентов'),
    ('Отчёты', 'Разработка отчётов для команды');

INSERT INTO project_members (project_id, user_id, role, removed_at)
SELECT p.project_id, u.user_id, seed.role::project_role,
       CASE WHEN seed.removed THEN CURRENT_TIMESTAMP - interval '7 days' END
FROM (VALUES
    ('Личный кабинет', 'olga', 'manager', false),
    ('Личный кабинет', 'anna', 'executor', false),
    ('Личный кабинет', 'ivan', 'executor', false),
    ('Личный кабинет', 'maria', 'observer', false),
    ('Личный кабинет', 'pavel', 'executor', true),
    ('Отчёты', 'anna', 'manager', false),
    ('Отчёты', 'maria', 'executor', false),
    ('Отчёты', 'dmitry', 'observer', false)
) AS seed(project_name, login, role, removed)
JOIN projects AS p ON p.name = seed.project_name
JOIN users AS u ON u.login = seed.login;

INSERT INTO auth_sessions (user_id, token_hash, created_at, expires_at, revoked_at)
SELECT u.user_id, sha256(convert_to(seed.token, 'UTF8')),
       CURRENT_TIMESTAMP - interval '1 day',
       CURRENT_TIMESTAMP + seed.expiry,
       CASE WHEN seed.revoked THEN CURRENT_TIMESTAMP - interval '1 hour' END
FROM (VALUES
    ('admin', 'test-admin-token', interval '1 day', false),
    ('olga', 'test-active-token', interval '1 day', false),
    ('anna', 'test-executor-token', interval '1 day', false),
    ('anna', 'test-expired-token', interval '-1 hour', false),
    ('ivan', 'test-revoked-token', interval '1 day', true)
) AS seed(login, token, expiry, revoked)
JOIN users AS u ON u.login = seed.login;

SELECT set_config('task_tracker.actor_id', user_id::text, true) FROM users WHERE login = 'olga';

INSERT INTO tasks (project_id, assignee_id, title, description, due_at, priority)
SELECT p.project_id, u.user_id, seed.title, seed.body,
       CURRENT_TIMESTAMP + seed.due_offset, seed.priority::task_priority
FROM (VALUES
    ('anna', 'Настроить окружение', 'Подготовить инструкцию по локальному запуску.', interval '4 days', 'low'),
    ('ivan', 'Согласовать макет', 'Согласовать экран входа и сценарий восстановления пароля.', interval '-2 days', 'medium'),
    ('ivan', 'Реализовать API входа', 'Обработать вход с действующими учётными данными.', interval '1 day', 'medium'),
    ('ivan', 'Подготовить документацию', 'Описать работу с настройками кабинета.', interval '-3 days', 'low'),
    ('anna', 'Подготовить стенд', 'Развернуть стенд для приёмочного тестирования.', interval '-1 day', 'high'),
    ('ivan', 'Проверить форму профиля', 'Проверить сохранение и валидацию данных профиля.', interval '5 days', 'medium')
) AS seed(login, title, body, due_offset, priority)
CROSS JOIN projects AS p
JOIN users AS u ON u.login = seed.login
WHERE p.name = 'Личный кабинет';

UPDATE tasks
SET assignee_id = (SELECT user_id FROM users WHERE login = 'anna'),
    priority = 'high',
    due_at = CURRENT_TIMESTAMP - interval '1 hour'
WHERE title = 'Реализовать API входа';

SELECT set_config('task_tracker.actor_id', user_id::text, true) FROM users WHERE login = 'ivan';

UPDATE tasks SET status = 'in_progress'
WHERE title IN ('Согласовать макет', 'Подготовить документацию', 'Проверить форму профиля');

INSERT INTO task_comments (task_id, author_id, body)
SELECT task_id, current_actor(), 'Макет готов. Уточняю сценарий восстановления пароля.'
FROM tasks WHERE title = 'Согласовать макет';

UPDATE tasks SET status = 'in_review'
WHERE title IN ('Подготовить документацию', 'Проверить форму профиля');

SELECT set_config('task_tracker.actor_id', user_id::text, true) FROM users WHERE login = 'olga';
UPDATE tasks SET status = 'done' WHERE title = 'Подготовить документацию';

SELECT set_config('task_tracker.actor_id', user_id::text, true) FROM users WHERE login = 'anna';
UPDATE tasks SET status = 'in_progress' WHERE title = 'Реализовать API входа';
UPDATE tasks SET status = 'in_review' WHERE title = 'Реализовать API входа';

SELECT set_config('task_tracker.actor_id', user_id::text, true) FROM users WHERE login = 'olga';
SELECT set_config('task_tracker.review_reason', 'Добавьте обработку деактивированных учётных записей.', true);
UPDATE tasks SET status = 'in_progress' WHERE title = 'Реализовать API входа';

SELECT set_config('task_tracker.actor_id', user_id::text, true) FROM users WHERE login = 'anna';
UPDATE tasks SET status = 'in_review' WHERE title = 'Реализовать API входа';

INSERT INTO task_comments (task_id, author_id, body)
SELECT task_id, current_actor(), 'Добавила проверку активности учётной записи. Повторно отправляю на проверку.'
FROM tasks WHERE title = 'Реализовать API входа';

INSERT INTO tasks (project_id, assignee_id, title, description, due_at, priority)
SELECT p.project_id, u.user_id, seed.title, seed.body,
       CURRENT_TIMESTAMP + seed.due_offset, seed.priority::task_priority
FROM (VALUES
    ('Спроектировать выгрузку', 'Согласовать состав полей отчёта.', interval '6 days', 'high'),
    ('Настроить фильтр периода', 'Добавить фильтр по диапазону дат.', interval '-2 days', 'medium')
) AS seed(title, body, due_offset, priority)
CROSS JOIN projects AS p
JOIN users AS u ON u.login = 'maria'
WHERE p.name = 'Отчёты';

SELECT set_config('task_tracker.actor_id', user_id::text, true) FROM users WHERE login = 'maria';
UPDATE tasks SET status = 'in_progress' WHERE title = 'Настроить фильтр периода';

COMMIT;
