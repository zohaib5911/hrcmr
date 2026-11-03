# Data model

Generated from the SQLAlchemy models by `python -m app.cli export-data-model`.
Do not edit by hand: a test fails when this file is out of date.

## `audit_events`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | yes |  |  |
| `actor_user_id` | UUID | yes |  |  |
| `actor_type` | VARCHAR(20) | no |  |  |
| `action` | VARCHAR(100) | no |  |  |
| `entity_type` | VARCHAR(60) | yes |  |  |
| `entity_id` | UUID | yes |  |  |
| `summary` | TEXT | yes |  |  |
| `before` | JSONB | yes |  |  |
| `after` | JSONB | yes |  |  |
| `reason` | TEXT | yes |  |  |
| `ip` | INET | yes |  |  |
| `user_agent` | VARCHAR(400) | yes |  |  |
| `request_id` | VARCHAR(64) | yes |  |  |
| `impersonation_session_id` | UUID | yes |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |

Checks:

- `actor_type in ('user', 'platform_admin', 'system')`

## `bank_holidays`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `region` | VARCHAR(20) | no |  |  |
| `on_date` | DATE | no |  |  |
| `title` | VARCHAR(120) | no |  |  |
| `source` | VARCHAR(200) | no |  |  |
| `fetched_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `region in ('england-and-wales', 'scotland', 'northern-ireland')`

## `change_of_circumstances`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `change_type` | VARCHAR(32) | no |  |  |
| `deadline_date` | DATE | no |  |  |
| `employment_type` | VARCHAR(12) | yes |  |  |
| `job_title` | VARCHAR(160) | yes |  |  |
| `nationality` | VARCHAR(80) | yes |  |  |
| `contact_number` | VARCHAR(40) | yes |  |  |
| `address` | TEXT | yes |  |  |
| `ack_inform_hr` | BOOLEAN | no | `false` |  |
| `ack_home_office_interview` | BOOLEAN | no | `false` |  |
| `documents_snapshot` | JSONB | no | `[]` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |
| `change_date` | DATE | no |  |  |
| `calendar_region` | VARCHAR(20) | no |  |  |
| `calendar_checked_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `calendar_holidays` | JSONB | no | `[]` |  |
| `reported_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `reported_by_user_id` | UUID | yes |  | references `users` |
| `reported_reference` | VARCHAR(160) | yes |  |  |
| `report_recorded_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `remarks` | TEXT | yes |  |  |

Checks:

- `(reported_at is null and reported_by_user_id is null and reported_reference is null and report_recorded_at is null) or (reported_at is not null and reported_by_user_id is not null and reported_reference is not null and length(trim(reported_reference)) > 0 and report_recorded_at is not null)`
- `calendar_checked_at is not null`
- `calendar_region in ('england-and-wales', 'scotland', 'northern-ireland')`
- `change_type in ('did_not_start', 'unauthorised_absence', 'sponsorship_stopped', 'salary_reduced', 'job_or_soc_changed', 'work_location_changed', 'working_hours_changed', 'unpaid_reduced_absence', 'other')`
- `deadline_date > change_date`

## `companies`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `name` | VARCHAR(200) | no |  |  |
| `trading_name` | VARCHAR(200) | yes |  |  |
| `slug` | VARCHAR(80) | no |  | unique |
| `registered_number` | VARCHAR(20) | yes |  |  |
| `type_of_organisation` | VARCHAR(60) | yes |  |  |
| `trading_period` | VARCHAR(40) | yes |  |  |
| `sector` | VARCHAR(10) | yes |  |  |
| `size_band` | VARCHAR(20) | yes |  |  |
| `contact_email` | VARCHAR(254) | yes |  |  |
| `contact_phone` | VARCHAR(40) | yes |  |  |
| `website` | VARCHAR(300) | yes |  |  |
| `logo_file_id` | UUID | yes |  |  |
| `country` | VARCHAR(2) | no | `GB` |  |
| `region` | VARCHAR(2) | no | `uk` |  |
| `bank_holiday_region` | VARCHAR(20) | no | `england-and-wales` |  |
| `timezone` | VARCHAR(64) | no | `Europe/London` |  |
| `default_currency` | VARCHAR(3) | no | `GBP` |  |
| `week_starts_on` | SMALLINT | no | `1` |  |
| `leave_year_start_month_day` | VARCHAR(5) | no | `01-01` |  |
| `allow_negative_leave_balance` | BOOLEAN | no | `false` |  |
| `mfa_policy` | VARCHAR(10) | no | `optional` |  |
| `bank_holidays_non_working` | BOOLEAN | no | `true` |  |
| `ai_features_enabled` | BOOLEAN | no | `true` |  |
| `changed_name_last_5_years` | BOOLEAN | no | `false` |  |
| `previous_company_name` | VARCHAR(200) | yes |  |  |
| `penalty_illegal_working_last_3_years` | BOOLEAN | no | `false` |  |
| `penalty_illegal_working_status` | TEXT | yes |  |  |
| `status` | VARCHAR(20) | no | `active` |  |
| `plan` | VARCHAR(10) | no | `free` |  |
| `subscription_status` | VARCHAR(30) | yes |  |  |
| `subscription_started_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `subscription_ends_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `cooling_off_ends_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `stripe_customer_id` | VARCHAR(80) | yes |  | unique |
| `stripe_subscription_id` | VARCHAR(80) | yes |  | unique |
| `setup_checklist_dismissed_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `bank_holiday_region in ('england-and-wales', 'scotland', 'northern-ireland')`
- `leave_year_start_month_day ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'`
- `mfa_policy in ('optional', 'admins', 'all')`
- `plan in ('free', 'annual', 'ten_year')`
- `region in ('uk', 'us', 'au')`
- `sector in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U')`
- `status in ('active', 'suspended', 'pending_deletion', 'deleted')`
- `trading_period in ('0_6_months', '6_12_months', '12_18_months', '18_36_months', 'over_36_months')`
- `type_of_organisation in ('private_limited_by_shares', 'charitable_incorporated_organisation', 'industrial_provident_society', 'general_partnership', 'limited_liability_partnership', 'scottish_limited_partnership', 'limited_partnership', 'community_interest_company', 'private_limited_by_guarantee', 'public_limited_company', 'sole_proprietorship', 'other')`
- `week_starts_on between 1 and 7`

## `company_bank_accounts`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `label` | VARCHAR(80) | no |  |  |
| `bank_name` | VARCHAR(120) | no |  |  |
| `account_holder` | VARCHAR(120) | no |  |  |
| `sort_code` | TEXT | no |  |  |
| `account_number` | TEXT | no |  |  |
| `is_primary` | BOOLEAN | no | `false` |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `company_compliance_documents`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `doc_type` | VARCHAR(40) | no |  |  |
| `file_id` | UUID | no |  | references `files` |
| `expires_on` | DATE | yes |  |  |
| `notes` | TEXT | yes |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `doc_type in ('paye_reference_letter', 'latest_rti', 'employers_liability_insurance', 'premises_proof', 'lease_or_freehold', 'bank_statement_1', 'bank_statement_2', 'bank_statement_3', 'signed_annual_accounts', 'vat_certificate', 'food_hygiene_rating', 'business_licence', 'franchise_agreement', 'governing_body_registration', 'health_safety_rating', 'audited_annual_accounts', 'regulatory_body_certificate', 'other')`

## `company_holidays`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `name` | VARCHAR(120) | no |  |  |
| `start_date` | DATE | no |  |  |
| `end_date` | DATE | no |  |  |
| `holiday_type_id` | UUID | yes |  | references `holiday_types` |
| `description` | TEXT | yes |  |  |
| `deduct_from_annual_leave` | BOOLEAN | no | `false` |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `end_date >= start_date`

## `departments`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `name` | VARCHAR(100) | no |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `designations`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `department_id` | UUID | no |  | references `departments` |
| `title` | VARCHAR(120) | no |  |  |
| `soc_code` | VARCHAR(4) | yes |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `soc_code ~ '^[0-9]{4}$'`

## `dossier_links`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `section` | VARCHAR(10) | no |  |  |
| `title` | VARCHAR(160) | no |  |  |
| `url` | VARCHAR(1000) | no |  |  |
| `checked_on` | DATE | no |  |  |
| `position` | INTEGER | no | `0` |  |
| `active` | BOOLEAN | no | `true` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `position >= 0`
- `section in ('licence', 'rtw', 'sms')`
- `url ~ '^https://www[.]gov[.]uk/[^[:space:]]+$'`

## `email_outbox`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `to_address` | VARCHAR(320) | no |  |  |
| `template` | VARCHAR(40) | no |  |  |
| `payload` | TEXT | yes |  |  |
| `status` | VARCHAR(10) | no | `pending` |  |
| `attempts` | INTEGER | no | `0` |  |
| `next_attempt_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `last_error` | VARCHAR(200) | yes |  |  |
| `sent_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `provider_id` | VARCHAR(100) | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `attempts >= 0`
- `status in ('pending', 'sent', 'failed')`

## `email_tokens`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `user_id` | UUID | no |  | references `users` |
| `purpose` | VARCHAR(20) | no |  |  |
| `token_hash` | VARCHAR(64) | no |  | unique |
| `expires_at` | TIMESTAMP WITH TIME ZONE | no |  |  |
| `used_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `purpose in ('verify', 'reset', 'deletion_code', 'login_alert')`

## `emergency_contacts`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `name` | VARCHAR(120) | no |  |  |
| `relationship` | VARCHAR(20) | no |  |  |
| `phone` | VARCHAR(40) | no |  |  |
| `email` | VARCHAR(254) | yes |  |  |
| `address` | TEXT | yes |  |  |
| `details` | TEXT | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `relationship in ('spouse', 'civil_partner', 'partner', 'parent', 'child', 'sibling', 'guardian', 'other_relative', 'friend', 'other')`

## `employee_addresses`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `postcode` | VARCHAR(12) | yes |  |  |
| `line1` | VARCHAR(120) | no |  |  |
| `line2` | VARCHAR(120) | yes |  |  |
| `line3` | VARCHAR(120) | yes |  |  |
| `city_county` | VARCHAR(120) | yes |  |  |
| `country` | VARCHAR(80) | yes |  |  |
| `is_current` | BOOLEAN | no | `true` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `employee_assignments`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `department_id` | UUID | yes |  | references `departments` |
| `designation_id` | UUID | yes |  | references `designations` |
| `location_id` | UUID | yes |  | references `locations` |
| `reporting_authority_employee_id` | UUID | yes |  | references `employees` |
| `leave_sanctioning_employee_id` | UUID | yes |  | references `employees` |
| `organogram_level_id` | UUID | yes |  |  |
| `employment_type` | VARCHAR(12) | no |  |  |
| `custom_working_days` | JSONB | yes |  |  |
| `hours_per_day` | NUMERIC(4, 2) | yes |  |  |
| `effective_from` | DATE | no |  |  |
| `ended_at` | DATE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `employment_type in ('full_time', 'part_time', 'fixed_term', 'zero_hours', 'casual', 'apprentice', 'agency')`

## `employee_bank_details`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `account_holder` | VARCHAR(120) | no |  |  |
| `bank_name` | VARCHAR(120) | no |  |  |
| `sort_code` | TEXT | no |  |  |
| `account_number` | TEXT | no |  |  |
| `is_current` | BOOLEAN | no | `true` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `employee_compensation`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `amount` | NUMERIC(12, 2) | no |  |  |
| `frequency` | VARCHAR(10) | no |  |  |
| `contracted_hours_per_week` | NUMERIC(5, 2) | yes |  |  |
| `tax_code_id` | UUID | yes |  | references `tax_codes` |
| `payment_type_id` | UUID | yes |  | references `payment_types` |
| `pay_band_id` | UUID | yes |  | references `pay_bands` |
| `pay_schedule_id` | UUID | yes |  | references `pay_schedules` |
| `effective_from` | DATE | no |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `amount >= 0`
- `frequency in ('annual', 'monthly', 'hourly')`

## `employee_documents`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `file_id` | UUID | no |  | references `files` |
| `category` | VARCHAR(24) | no |  |  |
| `notes` | TEXT | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `category in ('employment_contract', 'letter', 'hr_record', 'id_document', 'rtw_evidence', 'certificate', 'payslip', 'other')`

## `employee_education`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `qualification` | VARCHAR(120) | no |  |  |
| `subject` | VARCHAR(120) | yes |  |  |
| `institution` | VARCHAR(120) | yes |  |  |
| `awarding_body` | VARCHAR(120) | yes |  |  |
| `year` | SMALLINT | yes |  |  |
| `percentage` | NUMERIC(5, 2) | yes |  |  |
| `grade` | VARCHAR(40) | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `employee_memberships`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `licence_title` | VARCHAR(160) | no |  |  |
| `licence_number` | VARCHAR(80) | yes |  |  |
| `started_on` | DATE | yes |  |  |
| `ended_on` | DATE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `employee_previous_employment`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `job_title` | VARCHAR(120) | yes |  |  |
| `started_on` | DATE | yes |  |  |
| `left_on` | DATE | yes |  |  |
| `total_experience_years` | NUMERIC(4, 1) | yes |  |  |
| `description` | TEXT | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `employee_responsibilities`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `text` | TEXT | no |  |  |
| `sort` | INTEGER | no | `0` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `employee_training_records`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `title` | VARCHAR(160) | no |  |  |
| `started_on` | DATE | yes |  |  |
| `ended_on` | DATE | yes |  |  |
| `description` | TEXT | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `employees`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_number` | VARCHAR(50) | no |  |  |
| `first_name` | VARCHAR(100) | no |  |  |
| `last_name` | VARCHAR(100) | no |  |  |
| `email` | VARCHAR(254) | no |  |  |
| `phone` | VARCHAR(40) | yes |  |  |
| `alt_phone` | VARCHAR(40) | yes |  |  |
| `date_of_birth` | DATE | yes |  |  |
| `gender` | VARCHAR(30) | yes |  |  |
| `marital_status` | VARCHAR(30) | yes |  |  |
| `nationality` | VARCHAR(80) | yes |  |  |
| `photo_file_id` | UUID | yes |  | references `files` |
| `hire_date` | DATE | no |  |  |
| `status` | VARCHAR(10) | no | `active` |  |
| `leave_date` | DATE | yes |  |  |
| `opted_out_48h_week` | BOOLEAN | no | `false` |  |
| `ni_number` | TEXT | yes |  |  |
| `ni_number_index` | VARCHAR(64) | yes |  |  |
| `passport_number` | TEXT | yes |  |  |
| `passport_country` | VARCHAR(80) | yes |  |  |
| `passport_expiry` | DATE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `status in ('active', 'on_leave', 'leaver', 'archived')`

## `files`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `storage_key` | VARCHAR(300) | no |  | unique |
| `original_name` | VARCHAR(255) | no |  |  |
| `mime` | VARCHAR(100) | no |  |  |
| `size` | BIGINT | no |  |  |
| `sha256` | VARCHAR(64) | no |  |  |
| `scan_status` | VARCHAR(10) | no | `pending` |  |
| `scanned_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `owner_type` | VARCHAR(40) | yes |  |  |
| `owner_id` | UUID | yes |  |  |
| `category` | VARCHAR(40) | yes |  |  |
| `uploaded_by` | UUID | yes |  | references `users` |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `scan_status in ('pending', 'clean', 'infected', 'error')`
- `size >= 0`

## `holiday_types`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `name` | VARCHAR(80) | no |  |  |
| `colour` | VARCHAR(10) | no | `blue` |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `colour in ('blue', 'green', 'orange', 'red', 'gray')`

## `invitations`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `email` | CITEXT | no |  |  |
| `role` | VARCHAR(20) | no |  |  |
| `first_name` | VARCHAR(100) | yes |  |  |
| `last_name` | VARCHAR(100) | yes |  |  |
| `token_hash` | VARCHAR(64) | no |  | unique |
| `expires_at` | TIMESTAMP WITH TIME ZONE | no |  |  |
| `accepted_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `invited_by` | UUID | yes |  | references `users` |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `role in ('company_admin', 'hr_admin', 'people_manager', 'recruiter', 'employee', 'read_only_auditor')`

## `key_persons`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `role` | VARCHAR(20) | no |  |  |
| `first_name` | VARCHAR(100) | no |  |  |
| `last_name` | VARCHAR(100) | no |  |  |
| `designation` | VARCHAR(120) | yes |  |  |
| `phone` | VARCHAR(40) | yes |  |  |
| `email` | VARCHAR(254) | yes |  |  |
| `proof_of_id_file_id` | UUID | yes |  |  |
| `same_as_authorising_officer` | BOOLEAN | no | `false` |  |
| `is_settled_or_british` | BOOLEAN | yes |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `role in ('authorising_officer', 'key_contact', 'level1_user', 'level2_user')`

## `leave_types`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `seed_key` | VARCHAR(24) | yes |  |  |
| `name` | VARCHAR(80) | no |  |  |
| `is_paid` | BOOLEAN | no | `true` |  |
| `counts_toward_statutory` | BOOLEAN | no | `false` |  |
| `days_per_year` | NUMERIC(6, 2) | yes |  |  |
| `carry_over_limit_days` | NUMERIC(6, 2) | no | `0` |  |
| `accrual_method` | VARCHAR(12) | no | `front_loaded` |  |
| `requires_approval` | BOOLEAN | no | `true` |  |
| `colour` | VARCHAR(10) | no | `blue` |  |
| `rule_text` | TEXT | no | `` |  |
| `source_url` | VARCHAR(500) | yes |  |  |
| `checked_on` | DATE | yes |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `accrual_method in ('front_loaded','monthly')`
- `carry_over_limit_days >= 0`
- `colour in ('blue','green','orange','red','gray')`
- `days_per_year IS NULL OR days_per_year >= 0`
- `length(trim(name)) > 0`

## `locations`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `name` | VARCHAR(120) | no |  |  |
| `postcode` | VARCHAR(10) | no |  |  |
| `address_line1` | VARCHAR(120) | no |  |  |
| `address_line2` | VARCHAR(120) | yes |  |  |
| `address_line3` | VARCHAR(120) | yes |  |  |
| `city` | VARCHAR(80) | no |  |  |
| `county` | VARCHAR(80) | yes |  |  |
| `country` | VARCHAR(60) | no | `United Kingdom` |  |
| `is_default` | BOOLEAN | no | `false` |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `memberships`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `user_id` | UUID | no |  | references `users` |
| `company_id` | UUID | no |  | references `companies` |
| `role` | VARCHAR(20) | no |  |  |
| `status` | VARCHAR(10) | no | `active` |  |
| `employee_id` | UUID | yes |  | references `employees` |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `role in ('company_admin', 'hr_admin', 'people_manager', 'recruiter', 'employee', 'read_only_auditor')`
- `status in ('active', 'suspended')`

## `notifications`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `user_id` | UUID | no |  | references `users` |
| `kind` | VARCHAR(60) | no |  |  |
| `title` | VARCHAR(200) | no |  |  |
| `body` | TEXT | yes |  |  |
| `link` | VARCHAR(300) | yes |  |  |
| `read_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `org_changes`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `change_type` | VARCHAR(20) | no |  |  |
| `deadline_date` | DATE | yes |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `archive_reason` | TEXT | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |
| `change_date` | DATE | no |  |  |
| `calendar_region` | VARCHAR(20) | no |  |  |
| `calendar_checked_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `calendar_holidays` | JSONB | no | `[]` |  |
| `reported_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `reported_by_user_id` | UUID | yes |  | references `users` |
| `reported_reference` | VARCHAR(160) | yes |  |  |
| `report_recorded_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `remarks` | TEXT | yes |  |  |

Checks:

- `(archived_at is null and archive_reason is null) or (archived_at is not null and archive_reason is not null and length(trim(archive_reason)) > 0 and reported_at is null)`
- `(change_type = 'ao_or_key_contact' and deadline_date is null) or (change_type <> 'ao_or_key_contact' and deadline_date is not null and deadline_date > change_date and calendar_checked_at is not null)`
- `(reported_at is null and reported_by_user_id is null and reported_reference is null and report_recorded_at is null) or (reported_at is not null and reported_by_user_id is not null and reported_reference is not null and length(trim(reported_reference)) > 0 and report_recorded_at is not null)`
- `calendar_region in ('england-and-wales', 'scotland', 'northern-ireland')`
- `change_type in ('address', 'ownership', 'name', 'key_personnel', 'ao_or_key_contact', 'other')`

## `pay_bands`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `name` | VARCHAR(80) | no |  |  |
| `min_annual` | NUMERIC(12, 2) | no |  |  |
| `max_annual` | NUMERIC(12, 2) | no |  |  |
| `currency` | VARCHAR(3) | no | `GBP` |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `currency ~ '^[A-Z]{3}$'`
- `min_annual >= 0 and max_annual >= min_annual`

## `pay_schedules`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `name` | VARCHAR(80) | no |  |  |
| `frequency` | VARCHAR(12) | no |  |  |
| `pay_day_kind` | VARCHAR(20) | no |  |  |
| `pay_day_value` | SMALLINT | yes |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `(pay_day_kind = 'weekday' and pay_day_value between 1 and 7) or (pay_day_kind = 'day_of_month' and pay_day_value between 1 and 28) or (pay_day_kind in ('last_day', 'last_working_day') and pay_day_value is null)`
- `frequency in ('weekly', 'fortnightly', 'four_weekly', 'monthly')`
- `pay_day_kind in ('weekday', 'day_of_month', 'last_day', 'last_working_day')`

## `payment_types`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `name` | VARCHAR(80) | no |  |  |
| `min_hourly_rate` | NUMERIC(8, 2) | no |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `min_hourly_rate >= 0`

## `platform_admins`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `user_id` | UUID | no |  | references `users`, unique |
| `level` | VARCHAR(10) | no |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `level in ('support', 'owner')`

## `reminders`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `sponsor_document_id` | UUID | yes |  | references `sponsor_documents` |
| `rtw_check_id` | UUID | yes |  | references `rtw_checks` |
| `threshold_days` | SMALLINT | no |  |  |
| `expires_on` | DATE | no |  |  |
| `due_on` | DATE | no |  |  |
| `status` | VARCHAR(9) | no | `scheduled` |  |
| `message_draft` | TEXT | yes |  |  |
| `sent_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `sent_by_user_id` | UUID | yes |  | references `users` |
| `email_outbox_id` | UUID | yes |  | references `email_outbox` |
| `snoozed_until` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `cancel_reason` | VARCHAR(80) | yes |  |  |
| `admin_notified_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `(sponsor_document_id is not null and rtw_check_id is null) or (sponsor_document_id is null and rtw_check_id is not null)`
- `(status = 'cancelled' and cancel_reason is not null and length(trim(cancel_reason)) > 0) or (status <> 'cancelled' and cancel_reason is null)`
- `(status = 'sent' and sent_at is not null and sent_by_user_id is not null and email_outbox_id is not null and message_draft is not null) or (status <> 'sent' and sent_at is null and sent_by_user_id is null and email_outbox_id is null)`
- `(status = 'snoozed' and snoozed_until is not null) or (status <> 'snoozed' and snoozed_until is null)`
- `due_on = expires_on - threshold_days`
- `message_draft is null or (length(trim(message_draft)) > 0 and length(message_draft) <= 2000)`
- `status in ('scheduled', 'due', 'sent', 'snoozed', 'cancelled')`
- `threshold_days in (90, 60, 30)`

## `rtw_checks`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `subject_type` | VARCHAR(9) | no |  |  |
| `subject_id` | UUID | no |  |  |
| `check_type` | VARCHAR(24) | no |  |  |
| `share_code` | TEXT | yes |  |  |
| `idsp_provider` | VARCHAR(160) | yes |  |  |
| `idsp_document` | VARCHAR(24) | yes |  |  |
| `list_b_group` | VARCHAR(6) | yes |  |  |
| `permission_expires` | BOOLEAN | no | `false` |  |
| `permission_expires_on` | DATE | yes |  |  |
| `follow_up_due_on` | DATE | yes |  |  |
| `check_date` | DATE | yes |  |  |
| `checked_by_user_id` | UUID | yes |  | references `users` |
| `outcome` | VARCHAR(8) | no |  |  |
| `evidence_file_id` | UUID | yes |  | references `files` |
| `superseded_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `superseded_by` | UUID | yes |  | references `rtw_checks` |
| `corrected_from_id` | UUID | yes |  | references `rtw_checks`, unique |
| `correction_reason` | TEXT | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `(check_type = 'idsp_digital' and idsp_provider is not null and idsp_document is not null and idsp_document in ('british_passport', 'irish_passport', 'irish_passport_card')) or (check_type <> 'idsp_digital' and idsp_provider is null and idsp_document is null)`
- `(check_type = 'manual_list_b' and list_b_group is not null and list_b_group in ('group1', 'group2') and permission_expires) or (check_type <> 'manual_list_b' and list_b_group is null)`
- `(check_type = 'online_share_code' and share_code is not null) or (check_type <> 'online_share_code' and share_code is null)`
- `(corrected_from_id is null and correction_reason is null) or (corrected_from_id is not null and correction_reason is not null and length(trim(correction_reason)) > 0)`
- `(permission_expires and permission_expires_on is not null) or (not permission_expires and permission_expires_on is null)`
- `(superseded_at is null and superseded_by is null) or superseded_at is not null`
- `check_type in ('online_share_code', 'idsp_digital', 'manual_list_a', 'manual_list_b')`
- `check_type not in ('idsp_digital', 'manual_list_a') or not permission_expires`
- `outcome in ('pending', 'verified', 'failed')`
- `subject_type <> 'employee' or (check_date is not null and checked_by_user_id is not null)`
- `subject_type in ('employee', 'candidate')`

## `sessions`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `token_hash` | VARCHAR(64) | no |  | unique |
| `user_id` | UUID | no |  | references `users` |
| `company_id` | UUID | yes |  | references `companies` |
| `ip` | INET | yes |  |  |
| `user_agent` | VARCHAR(400) | yes |  |  |
| `last_seen_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `expires_at` | TIMESTAMP WITH TIME ZONE | no |  |  |
| `revoked_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `mfa_passed_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `step_up_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |

## `sponsor_documents`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `employee_id` | UUID | no |  | references `employees` |
| `doc_type` | VARCHAR(11) | no |  |  |
| `reference_number` | TEXT | yes |  |  |
| `issuing_country` | VARCHAR(2) | yes |  |  |
| `visa_route` | VARCHAR(24) | yes |  |  |
| `cos_number` | TEXT | yes |  |  |
| `soc_code` | VARCHAR(4) | yes |  |  |
| `sponsored_salary` | NUMERIC(12, 2) | yes |  |  |
| `issue_date` | DATE | yes |  |  |
| `expiry_date` | DATE | yes |  |  |
| `review_date` | DATE | yes |  |  |
| `evidence_file_id` | UUID | yes |  | references `files` |
| `remarks` | TEXT | yes |  |  |
| `version` | INTEGER | no |  |  |
| `superseded_by` | UUID | yes |  | references `sponsor_documents` |
| `withdrawn_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `withdraw_reason` | TEXT | yes |  |  |
| `renewal_date` | DATE | yes |  |  |
| `renewal_notes` | TEXT | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `(doc_type = 'visa' and visa_route is not null) or (doc_type <> 'visa' and visa_route is null and cos_number is null and soc_code is null and sponsored_salary is null)`
- `(withdrawn_at is null and withdraw_reason is null) or (withdrawn_at is not null and withdraw_reason is not null and length(trim(withdraw_reason)) > 0 and superseded_by is null)`
- `doc_type in ('visa', 'passport', 'dbs', 'euss', 'national_id', 'other')`
- `issue_date is null or expiry_date is null or expiry_date >= issue_date`
- `issuing_country is null or issuing_country ~ '^[A-Z]{2}$'`
- `renewal_date is not null or renewal_notes is null`
- `soc_code is null or soc_code ~ '^[0-9]{4}$'`
- `sponsored_salary is null or sponsored_salary >= 0`
- `version > 0`
- `visa_route is null or visa_route in ('skilled_worker', 'health_care_worker', 'global_business_mobility', 'scale_up', 'temporary_worker', 'graduate', 'student', 'euss_settled', 'euss_pre_settled', 'family', 'other')`

## `tax_codes`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `code` | VARCHAR(12) | no |  |  |
| `reference` | VARCHAR(80) | yes |  |  |
| `deduction_percentage` | NUMERIC(5, 2) | no |  |  |
| `archived_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `deduction_percentage between 0 and 100`

## `terms_acceptances`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `user_id` | UUID | no |  | references `users` |
| `version` | VARCHAR(40) | no |  | references `terms_versions` |
| `accepted_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `ip` | INET | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `terms_versions`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `version` | VARCHAR(40) | no |  | unique |
| `published_at` | TIMESTAMP WITH TIME ZONE | no |  |  |
| `url` | VARCHAR(300) | no |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

## `trading_hours_days`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `weekday` | SMALLINT | no |  |  |
| `is_open` | BOOLEAN | no | `false` |  |
| `opens_at` | TIME WITHOUT TIME ZONE | yes |  |  |
| `closes_at` | TIME WITHOUT TIME ZONE | yes |  |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `(is_open and opens_at is not null and closes_at is not null and opens_at < closes_at) or (not is_open and opens_at is null and closes_at is null)`
- `weekday between 1 and 7`

## `users`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `email` | CITEXT | no |  | unique |
| `first_name` | VARCHAR(100) | no |  |  |
| `last_name` | VARCHAR(100) | no |  |  |
| `password_hash` | TEXT | yes |  |  |
| `email_verified_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `is_active` | BOOLEAN | no | `true` |  |
| `mfa_enabled` | BOOLEAN | no | `false` |  |
| `mfa_secret` | TEXT | yes |  |  |
| `recovery_codes_hash` | TEXT[] | no | `{}` |  |
| `requires_password_change` | BOOLEAN | no | `false` |  |
| `last_login_at` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `failed_login_count` | INTEGER | no | `0` |  |
| `locked_until` | TIMESTAMP WITH TIME ZONE | yes |  |  |
| `theme_pref` | VARCHAR(10) | no | `system` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `failed_login_count >= 0`
- `theme_pref in ('system', 'light', 'dark')`

## `working_pattern_days`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `weekday` | SMALLINT | no |  |  |
| `is_working` | BOOLEAN | no | `false` |  |
| `hours` | NUMERIC(4, 2) | no | `0` |  |
| `id` | UUID | no | `uuid_generate_v7()` | primary key |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | `now()` |  |
| `created_by` | UUID | yes |  |  |
| `updated_by` | UUID | yes |  |  |

Checks:

- `hours >= 0 and hours <= 24`
- `weekday between 1 and 7`
