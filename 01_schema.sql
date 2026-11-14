BEGIN;

CREATE SCHEMA task_tracker;
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;

CREATE TYPE task_tracker.project_role AS ENUM ('manager', 'executor', 'observer');
CREATE TYPE task_tracker.task_status AS ENUM ('todo', 'in_progress', 'in_review', 'done');
CREATE TYPE task_tracker.task_priority AS ENUM ('low', 'medium', 'high');

CREATE TABLE task_tracker.users (
    user_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login text NOT NULL UNIQUE,
    display_name text NOT NULL CHECK (btrim(display_name) <> ''),
    password_hash text NOT NULL CHECK (btrim(password_hash) <> ''),
    is_admin boolean NOT NULL DEFAULT false,
    is_active boolean NOT NULL DEFAULT true,
    CHECK (login <> '' AND login = lower(btrim(login)))
);

CREATE TABLE task_tracker.auth_sessions (
    session_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES task_tracker.users,
    token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CHECK (expires_at > created_at),
    CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);

CREATE TABLE task_tracker.projects (
    project_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL CHECK (btrim(name) <> ''),
    description text NOT NULL DEFAULT ''
);

CREATE TABLE task_tracker.project_members (
    project_id bigint NOT NULL REFERENCES task_tracker.projects,
    user_id bigint NOT NULL REFERENCES task_tracker.users,
    role task_tracker.project_role NOT NULL,
    removed_at timestamptz,
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE task_tracker.tasks (
    task_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id bigint NOT NULL REFERENCES task_tracker.projects,
    assignee_id bigint NOT NULL,
    title text NOT NULL CHECK (btrim(title) <> ''),
    description text NOT NULL CHECK (btrim(description) <> ''),
    due_at timestamptz NOT NULL,
    priority task_tracker.task_priority NOT NULL,
    status task_tracker.task_status NOT NULL DEFAULT 'todo',
    CONSTRAINT tasks_project_assignee_fk
        FOREIGN KEY (project_id, assignee_id)
        REFERENCES task_tracker.project_members (project_id, user_id)
);

CREATE TABLE task_tracker.task_comments (
    comment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id bigint NOT NULL REFERENCES task_tracker.tasks,
    author_id bigint NOT NULL REFERENCES task_tracker.users,
    body text NOT NULL CHECK (btrim(body, E' \t\n\r') <> ''),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE task_tracker.task_changes (
    change_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id bigint NOT NULL REFERENCES task_tracker.tasks,
    actor_id bigint NOT NULL REFERENCES task_tracker.users,
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    old_status task_tracker.task_status,
    new_status task_tracker.task_status,
    old_assignee_id bigint REFERENCES task_tracker.users,
    new_assignee_id bigint REFERENCES task_tracker.users,
    old_priority task_tracker.task_priority,
    new_priority task_tracker.task_priority,
    old_due_at timestamptz,
    new_due_at timestamptz,
    CHECK ((old_status IS NULL AND new_status IS NULL)
        OR (old_status IS NOT NULL AND new_status IS NOT NULL AND old_status <> new_status)),
    CHECK ((old_assignee_id IS NULL AND new_assignee_id IS NULL)
        OR (old_assignee_id IS NOT NULL AND new_assignee_id IS NOT NULL AND old_assignee_id <> new_assignee_id)),
    CHECK ((old_priority IS NULL AND new_priority IS NULL)
        OR (old_priority IS NOT NULL AND new_priority IS NOT NULL AND old_priority <> new_priority)),
    CHECK ((old_due_at IS NULL AND new_due_at IS NULL)
        OR (old_due_at IS NOT NULL AND new_due_at IS NOT NULL AND old_due_at <> new_due_at)),
    CHECK (num_nonnulls(old_status, old_assignee_id, old_priority, old_due_at) > 0)
);

CREATE INDEX auth_sessions_user_expiry_idx ON task_tracker.auth_sessions (user_id, expires_at);
CREATE INDEX project_members_user_idx ON task_tracker.project_members (user_id);
CREATE INDEX tasks_assignee_project_due_idx ON task_tracker.tasks (assignee_id, project_id, due_at);
CREATE INDEX tasks_project_status_due_idx ON task_tracker.tasks (project_id, status, due_at);
CREATE INDEX tasks_project_priority_due_idx ON task_tracker.tasks (project_id, priority, due_at);
CREATE INDEX tasks_project_due_idx ON task_tracker.tasks (project_id, due_at);
CREATE INDEX tasks_project_open_due_idx ON task_tracker.tasks (project_id, due_at) WHERE status <> 'done';
CREATE INDEX tasks_title_trgm_idx ON task_tracker.tasks USING gin (title public.gin_trgm_ops);
CREATE INDEX task_comments_task_time_idx ON task_tracker.task_comments (task_id, created_at, comment_id);
CREATE INDEX task_comments_author_idx ON task_tracker.task_comments (author_id);
CREATE INDEX task_changes_task_time_idx ON task_tracker.task_changes (task_id, changed_at, change_id);
CREATE INDEX task_changes_actor_idx ON task_tracker.task_changes (actor_id);
CREATE INDEX task_changes_old_assignee_idx ON task_tracker.task_changes (old_assignee_id) WHERE old_assignee_id IS NOT NULL;
CREATE INDEX task_changes_new_assignee_idx ON task_tracker.task_changes (new_assignee_id) WHERE new_assignee_id IS NOT NULL;

CREATE VIEW task_tracker.task_overview AS
SELECT tasks.*,
       (status <> 'done' AND due_at < statement_timestamp()) AS is_overdue
FROM task_tracker.tasks;

-- FastAPI sets this transaction-local value from the authenticated user.
CREATE FUNCTION task_tracker.current_actor()
RETURNS bigint
LANGUAGE sql STABLE
AS $$
    SELECT nullif(current_setting('task_tracker.actor_id', true), '')::bigint
$$;

CREATE FUNCTION task_tracker.active_role(target_project_id bigint, target_user_id bigint)
RETURNS task_tracker.project_role
LANGUAGE sql
AS $$
    SELECT member.role
    FROM task_tracker.project_members AS member
    JOIN task_tracker.users AS account ON account.user_id = member.user_id
    WHERE member.project_id = target_project_id
      AND member.user_id = target_user_id
      AND member.removed_at IS NULL
      AND account.is_active
    FOR SHARE OF member, account
$$;

CREATE FUNCTION task_tracker.guard_member_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND (OLD.project_id, OLD.user_id) <> (NEW.project_id, NEW.user_id) THEN
        RAISE EXCEPTION 'Membership identity is immutable' USING ERRCODE = '23514';
    END IF;

    IF OLD.role = 'executor' AND OLD.removed_at IS NULL
       AND (TG_OP = 'DELETE' OR NEW.role <> 'executor' OR NEW.removed_at IS NOT NULL)
       AND EXISTS (
           SELECT 1 FROM task_tracker.tasks
           WHERE project_id = OLD.project_id AND assignee_id = OLD.user_id AND status <> 'done'
       ) THEN
        RAISE EXCEPTION 'Reassign open tasks before removing the executor role' USING ERRCODE = '23514';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER guard_member_change
BEFORE UPDATE OR DELETE ON task_tracker.project_members
FOR EACH ROW EXECUTE FUNCTION task_tracker.guard_member_change();

CREATE FUNCTION task_tracker.guard_task_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    actor_id bigint := task_tracker.current_actor();
    actor_role task_tracker.project_role := task_tracker.active_role(NEW.project_id, actor_id);
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF actor_role IS DISTINCT FROM 'manager' THEN
            RAISE EXCEPTION 'Only a project manager can create tasks' USING ERRCODE = '42501';
        END IF;
        IF NEW.status IS DISTINCT FROM 'todo' THEN
            RAISE EXCEPTION 'New tasks must start in todo' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF (OLD.task_id, OLD.project_id) <> (NEW.task_id, NEW.project_id) THEN
            RAISE EXCEPTION 'Task identity and project are immutable' USING ERRCODE = '23514';
        END IF;

        IF actor_role IS DISTINCT FROM 'manager'
           AND (actor_role IS DISTINCT FROM 'executor' OR actor_id IS DISTINCT FROM OLD.assignee_id
                OR (OLD.assignee_id, OLD.title, OLD.description, OLD.due_at, OLD.priority)
                   IS DISTINCT FROM
                   (NEW.assignee_id, NEW.title, NEW.description, NEW.due_at, NEW.priority)) THEN
            RAISE EXCEPTION 'This user cannot edit the task' USING ERRCODE = '42501';
        END IF;

        IF OLD.status IS DISTINCT FROM NEW.status AND NOT coalesce(
            (actor_role = 'executor' AND (
                (OLD.status = 'todo' AND NEW.status = 'in_progress')
                OR (OLD.status = 'in_progress' AND NEW.status = 'in_review')
            ))
            OR (actor_role = 'manager' AND OLD.status = 'in_review'
                AND NEW.status IN ('in_progress', 'done')),
            false
        ) THEN
            RAISE EXCEPTION 'Invalid status transition' USING ERRCODE = '23514';
        END IF;
    END IF;

    IF TG_OP = 'INSERT' OR NEW.assignee_id IS DISTINCT FROM OLD.assignee_id THEN
        IF task_tracker.active_role(NEW.project_id, NEW.assignee_id) IS DISTINCT FROM 'executor' THEN
            RAISE EXCEPTION 'The assignee must be an active executor of the project' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER guard_task_write
BEFORE INSERT OR UPDATE ON task_tracker.tasks
FOR EACH ROW EXECUTE FUNCTION task_tracker.guard_task_write();

CREATE FUNCTION task_tracker.guard_comment_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target task_tracker.tasks%ROWTYPE;
    author_role task_tracker.project_role;
BEGIN
    IF NEW.author_id IS DISTINCT FROM task_tracker.current_actor() THEN
        RAISE EXCEPTION 'The author must match the authenticated actor' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO STRICT target FROM task_tracker.tasks WHERE task_id = NEW.task_id FOR SHARE;
    author_role := task_tracker.active_role(target.project_id, NEW.author_id);
    IF author_role IS DISTINCT FROM 'manager'
       AND (author_role IS DISTINCT FROM 'executor' OR NEW.author_id IS DISTINCT FROM target.assignee_id) THEN
        RAISE EXCEPTION 'Only the project manager or assigned executor can comment' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER guard_comment_insert
BEFORE INSERT ON task_tracker.task_comments
FOR EACH ROW EXECUTE FUNCTION task_tracker.guard_comment_insert();

CREATE FUNCTION task_tracker.record_task_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    actor_id bigint := task_tracker.current_actor();
    review_reason text;
BEGIN
    IF OLD.status = 'in_review' AND NEW.status = 'in_progress' THEN
        review_reason := nullif(btrim(current_setting('task_tracker.review_reason', true), E' \t\n\r'), '');
        IF review_reason IS NULL THEN
            RAISE EXCEPTION 'A review return requires a reason' USING ERRCODE = '23514';
        END IF;
        INSERT INTO task_tracker.task_comments (task_id, author_id, body)
        VALUES (NEW.task_id, actor_id, review_reason);
        PERFORM set_config('task_tracker.review_reason', '', true);
    END IF;

    IF (OLD.status, OLD.assignee_id, OLD.priority, OLD.due_at)
       IS DISTINCT FROM (NEW.status, NEW.assignee_id, NEW.priority, NEW.due_at) THEN
        INSERT INTO task_tracker.task_changes (
            task_id, actor_id, old_status, new_status, old_assignee_id, new_assignee_id,
            old_priority, new_priority, old_due_at, new_due_at
        ) VALUES (
            NEW.task_id, actor_id,
            CASE WHEN OLD.status <> NEW.status THEN OLD.status END,
            CASE WHEN OLD.status <> NEW.status THEN NEW.status END,
            CASE WHEN OLD.assignee_id <> NEW.assignee_id THEN OLD.assignee_id END,
            CASE WHEN OLD.assignee_id <> NEW.assignee_id THEN NEW.assignee_id END,
            CASE WHEN OLD.priority <> NEW.priority THEN OLD.priority END,
            CASE WHEN OLD.priority <> NEW.priority THEN NEW.priority END,
            CASE WHEN OLD.due_at <> NEW.due_at THEN OLD.due_at END,
            CASE WHEN OLD.due_at <> NEW.due_at THEN NEW.due_at END
        );
    END IF;
    RETURN NULL;
END
$$;

CREATE TRIGGER record_task_change
AFTER UPDATE ON task_tracker.tasks
FOR EACH ROW EXECUTE FUNCTION task_tracker.record_task_change();

COMMIT;
