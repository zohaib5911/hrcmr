# Sponsor register: optional Companies House bulk matches

This enrichment is separate from the authenticated Companies House API integration. It uses
only a saved **Free Company Data Product** CSV. No API key or per-sponsor network call is needed.
`REGISTER_BULK_MATCH_ENABLED` defaults to `false`; set it to `true` for the worker and operator
command to enable register matches. Loading a file while disabled stores the dataset but leaves
all sponsor records unchanged. With the flag off, later imports also leave matches unchanged.

## Load a monthly edition

Download the monthly Free Company Data Product from Companies House. Extract the CSV locally.
The loader expects `CompanyName`, `CompanyNumber`, and `SICCode.SicText_1` columns; extra columns
and whitespace around headers are accepted. If the edition comes in multiple CSV parts, combine
all parts into one CSV with a single header before loading. Loading parts independently would
miss names duplicated across parts. Use the complete edition so duplicate-name rejection works.

From `api/`, with `DATABASE_URL_OWNER` and `REGISTER_BULK_MATCH_ENABLED=true` set:

```bash
uv run python -m app.cli load-companies /path/to/BasicCompanyData-2026-11.csv --version 2026-11
```

The command stores the file, source filename, edition, SHA-256, unambiguous-name count and load
time in the owner-only `register_company_datasets` table. Sponsors matched by the bulk loader
link to that dataset through `companies_dataset_id`. The newest loaded dataset is active.
Malformed or wholly unusable files are refused atomically.

Matches use the existing exact normalised-name service: no fuzzy guesses. Duplicate names
remain unmatched. Company numbers retain leading zeros and prefixes. The first SIC code gives
the industry section used by the public explorer's industry filter and counts.

## Refresh and imports

Repeat the command with the complete new edition each month, using a new version label. With
matching enabled, loading refreshes prior bulk matches, including clearing a match if its name
has disappeared or become ambiguous. Other company numbers without bulk provenance are preserved.
Scheduled and manual register imports reuse the newest stored file for newly imported sponsors;
if a newer file was loaded while disabled, its matches replace older bulk matches on the next
enabled import. Restart the worker after changing its environment flag. If enabled without a
loaded dataset, imports still succeed and log `register_companies_missing`.

Old datasets remain available for provenance. The bulk file is large: allow database storage and
worker memory for the retained files and in-memory exact-name index. Enrichment runs only after
a changed register import; an unchanged GOV.UK file is skipped as usual. To apply a dataset
immediately after enabling the flag, rerun `load-companies` with that edition.
