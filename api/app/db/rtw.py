"""Read-only SQLAlchemy reference to the security-invoker RTW status view."""

from sqlalchemy import Date, String, Uuid, column, table

employee_rtw_status = table(
    "employee_rtw_status",
    column("employee_id", Uuid),
    column("company_id", Uuid),
    column("current_check_id", Uuid),
    column("follow_up_due_on", Date),
    column("status", String),
)
