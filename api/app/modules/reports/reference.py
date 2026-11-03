"""The seven XLSX reports in plan.md 8.10."""

from typing import Literal

ReportType = Literal[
    "employee_directory",
    "employee_detail",
    "archived_employees",
    "company",
    "sponsor_workers",
    "leave_taken",
    "training_completion",
]
REPORT_TYPES = (
    "employee_directory",
    "employee_detail",
    "archived_employees",
    "company",
    "sponsor_workers",
    "leave_taken",
    "training_completion",
)
REPORT_LABELS = {
    "employee_directory": "Employee Directory",
    "employee_detail": "Employee Detail",
    "archived_employees": "Archived Employees",
    "company": "Company Report",
    "sponsor_workers": "Sponsor Workers Report",
    "leave_taken": "Leave Taken Report",
    "training_completion": "Training Completion Report",
}
