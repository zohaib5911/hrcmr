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

## `invitations`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `company_id` | UUID | no |  | references `companies` |
| `email` | CITEXT | no |  |  |
| `role` | VARCHAR(20) | no |  |  |
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
| `employee_id` | UUID | yes |  |  |
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
