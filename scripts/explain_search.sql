-- Run after the migration. The temporary copy keeps benchmark rows out of the application.
BEGIN;
CREATE TEMP TABLE search_projects (LIKE task_tracker.projects INCLUDING DEFAULTS) ON COMMIT DROP;
INSERT INTO search_projects (project_id, name, description)
SELECT i, 'Project ' || i, CASE WHEN i % 1000 = 0 THEN 'audit marker' ELSE md5(i::text) END
FROM generate_series(1, 30000) AS i;
ANALYZE search_projects;
EXPLAIN (ANALYZE, BUFFERS)
SELECT project_id FROM search_projects WHERE name ILIKE '%marker%' OR description ILIKE '%marker%';

CREATE INDEX ON search_projects USING gin (name public.gin_trgm_ops);
CREATE INDEX ON search_projects USING gin (description public.gin_trgm_ops);
ANALYZE search_projects;
EXPLAIN (ANALYZE, BUFFERS)
SELECT project_id FROM search_projects WHERE name ILIKE '%marker%' OR description ILIKE '%marker%';
ROLLBACK;
