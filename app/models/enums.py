from sqlalchemy.dialects.postgresql import ENUM


project_role = ENUM(
    "manager", "executor", "observer", name="project_role", schema="task_tracker"
)
task_status = ENUM(
    "todo", "in_progress", "in_review", "done", name="task_status", schema="task_tracker"
)
task_priority = ENUM(
    "low", "medium", "high", name="task_priority", schema="task_tracker"
)
