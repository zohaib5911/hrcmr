"""Policy categories and confirmation/audience choices from plan.md 8.10."""

from typing import Literal

PolicyCategory = Literal[
    "employment_contract",
    "job_description",
    "offer_letter",
    "contract_change",
    "company_policy",
    "employee_handbook",
    "code_of_conduct",
    "it_email_social_media",
    "drugs_alcohol",
    "sickness_sick_pay",
    "attendance_punctuality",
    "holiday_annual_leave",
    "flexible_hybrid_working",
    "family_leave",
    "equality_diversity",
    "anti_harassment",
    "grievance",
    "disciplinary",
    "whistleblowing",
    "health_safety",
    "privacy_notice",
    "sponsor_duties",
    "other",
]
POLICY_CATEGORIES = (
    "employment_contract",
    "job_description",
    "offer_letter",
    "contract_change",
    "company_policy",
    "employee_handbook",
    "code_of_conduct",
    "it_email_social_media",
    "drugs_alcohol",
    "sickness_sick_pay",
    "attendance_punctuality",
    "holiday_annual_leave",
    "flexible_hybrid_working",
    "family_leave",
    "equality_diversity",
    "anti_harassment",
    "grievance",
    "disciplinary",
    "whistleblowing",
    "health_safety",
    "privacy_notice",
    "sponsor_duties",
    "other",
)
ConfirmationMode = Literal["accept", "sign"]
AudienceType = Literal["everyone", "departments", "locations", "named", "visa_holders"]
PolicyStatus = Literal["draft", "sent", "archived"]
AcceptanceStatus = Literal["pending", "accepted", "signed", "overdue"]
