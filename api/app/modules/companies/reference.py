"""The fixed lists a company's details are chosen from (plan.md 8.15). Each is stored as its short
value; the label is what people read. The web app gets both from ``GET /company/options``, so the
words live here only."""

from __future__ import annotations

from typing import Final

# Legal structure, in the order the plan lists them.
LEGAL_STRUCTURES: Final[dict[str, str]] = {
    "private_limited_by_shares": "Private company limited by shares",
    "charitable_incorporated_organisation": "Charitable incorporated organisation",
    "industrial_provident_society": "Industrial and provident society",
    "general_partnership": "General partnership",
    "limited_liability_partnership": "Limited liability partnership",
    "scottish_limited_partnership": "Scottish limited partnership",
    "limited_partnership": "Limited partnership",
    "community_interest_company": "Community interest company",
    "private_limited_by_guarantee": "Private company limited by guarantee",
    "public_limited_company": "Public limited company",
    "sole_proprietorship": "Sole proprietorship",
    "other": "Other",
}

TRADING_PERIODS: Final[dict[str, str]] = {
    "0_6_months": "0 to 6 months",
    "6_12_months": "Over 6 to 12 months",
    "12_18_months": "Over 12 to 18 months",
    "18_36_months": "Over 18 to 36 months",
    "over_36_months": "Over 36 months",
}

# The 21 sections of the UK Standard Industrial Classification 2007 (ONS).
SECTORS: Final[dict[str, str]] = {
    "A": "Agriculture, forestry and fishing",
    "B": "Mining and quarrying",
    "C": "Manufacturing",
    "D": "Electricity, gas, steam and air conditioning supply",
    "E": "Water supply, sewerage, waste management and remediation activities",
    "F": "Construction",
    "G": "Wholesale and retail trade; repair of motor vehicles and motorcycles",
    "H": "Transportation and storage",
    "I": "Accommodation and food service activities",
    "J": "Information and communication",
    "K": "Financial and insurance activities",
    "L": "Real estate activities",
    "M": "Professional, scientific and technical activities",
    "N": "Administrative and support service activities",
    "O": "Public administration and defence; compulsory social security",
    "P": "Education",
    "Q": "Human health and social work activities",
    "R": "Arts, entertainment and recreation",
    "S": "Other service activities",
    "T": "Activities of households as employers; undifferentiated goods and services for own use",
    "U": "Activities of extraterritorial organisations and bodies",
}

BANK_HOLIDAY_REGION_LABELS: Final[dict[str, str]] = {
    "england-and-wales": "England and Wales",
    "scotland": "Scotland",
    "northern-ireland": "Northern Ireland",
}

# What Companies House calls a company's type, mapped to ours. Anything else becomes "other".
COMPANIES_HOUSE_TYPES: Final[dict[str, str]] = {
    "ltd": "private_limited_by_shares",
    "private-limited-guarant-nsc": "private_limited_by_guarantee",
    "private-limited-guarant-nsc-limited-exemption": "private_limited_by_guarantee",
    "plc": "public_limited_company",
    "llp": "limited_liability_partnership",
    "limited-partnership": "limited_partnership",
    "scottish-partnership": "general_partnership",
    "industrial-and-provident-society": "industrial_provident_society",
    "charitable-incorporated-organisation": "charitable_incorporated_organisation",
    "scottish-charitable-incorporated-organisation": "charitable_incorporated_organisation",
    "private-limited-shares-section-30-exemption": "private_limited_by_shares",
}


def check_sql(column: str, values: dict[str, str]) -> str:
    return f"{column} in ({', '.join(repr(v) for v in values)})"


# The 18 documents a sponsor is expected to hold (plan.md 8.15), in the plan's order.
COMPLIANCE_DOCUMENT_TYPES: Final[dict[str, str]] = {
    "paye_reference_letter": "PAYE and Accounts Office reference letter from HMRC",
    "latest_rti": "Latest RTI from accountant",
    "employers_liability_insurance": "Employer's liability insurance certificate",
    "premises_proof": "Proof of business premises (tenancy agreement)",
    "lease_or_freehold": "Copy of lease or freehold",
    "bank_statement_1": "Business bank statement month 1",
    "bank_statement_2": "Business bank statement month 2",
    "bank_statement_3": "Business bank statement month 3",
    "signed_annual_accounts": "Signed annual accounts (if over 18 months old)",
    "vat_certificate": "VAT certificate (if registered)",
    "food_hygiene_rating": "Food hygiene rating (food businesses)",
    "business_licence": "Registered business licence/certificate",
    "franchise_agreement": "Franchise agreement",
    "governing_body_registration": "Governing body registration",
    "health_safety_rating": "Health & safety rating copy",
    "audited_annual_accounts": "Audited annual accounts",
    "regulatory_body_certificate": (
        "Regulatory body certificate (e.g. ACCA, FCA, Ofcom, IATA, ARLA)"
    ),
    "other": "Other",
}

# A document that runs out within this many days is shown as expiring (reminders come from T7).
EXPIRING_DAYS: Final[int] = 60
