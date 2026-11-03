"""Sponsor document and visa route choices, kept in plan 8.5 order."""

DOCUMENT_TYPES = (
    ("visa", "Visa"),
    ("passport", "Passport"),
    ("dbs", "DBS certificate"),
    ("euss", "EUSS status"),
    ("national_id", "National ID"),
    ("other", "Other"),
)
VISA_ROUTES = (
    ("skilled_worker", "Skilled Worker"),
    ("health_care_worker", "Health and Care Worker"),
    ("global_business_mobility", "Global Business Mobility"),
    ("scale_up", "Scale-up"),
    ("temporary_worker", "Temporary Worker"),
    ("graduate", "Graduate"),
    ("student", "Student"),
    ("euss_settled", "EUSS settled"),
    ("euss_pre_settled", "EUSS pre-settled"),
    ("family", "Family"),
    ("other", "Other"),
)
SPONSORED_ROUTES = frozenset(route for route, _ in VISA_ROUTES[:5])
