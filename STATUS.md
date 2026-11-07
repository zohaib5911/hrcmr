# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: (see git log)
State: IN PROGRESS

## Last completed
- T15.2 — Rules-data importer: GOV.UK pages → draft rules version with diff; publish sets live + RQF levels. Migration 0041.
- T15.1 — ONS SOC 2020 import and local embeddings.

## Current task
- T15.3 — Rules engine and 20+ golden tests (B) — starting next.

## Next tasks
- T15.3 (B), then T15.4 (S!), T15.5 (S!)

## Health
- CI on dev: not run since T15.1 (Phase 15 gate PR runs it)    CI on main: green (last PR #22)
- Local checks run: ruff + format + mypy (app, data) clean. Parser 18, rules DB 6, SOC 17, migrations/data-model/cli/architecture, guards + RLS isolation 31: all pass.
## Issues / suggestions
- Test harness: `temporary_database()` sets the cluster-wide roles `app_owner` and `app_user` to a fresh random password each time. Two DB-using runs at once break each other's owner connection. My first full ONS load failed this way (password authentication failed for app_owner, before any rows were written); the re-run, with nothing else using the DB, succeeded. Do not run DB suites in parallel with another DB job. Worth a fix in the harness (per-database roles, or a lock) before Phase 15 gate.
- The ONS coding index has 58 rows whose title is a letter only (A, A1, A2…). They are loaded as published. T15.4 search must not treat them as job titles.
- `index_title` holds the reverse-order title ("Administrator, holding, fund"), as the spec's INDEXOCC column does. The natural-order title ("Fund holding administrator") is not stored: 11 natural-order keys collide. T15.4 search may need it; decide there (new column in a new migration).
- Embedding text is unit group title + description + tasks + related titles, and index title + qualifiers. Retrieval quality is not yet measured (T15.4 will).
- T15.2: Table 3/3a cells are free text; each "role: £X (N-hour week)" bullet becomes a pay_scale_rates row (with nation and weekly hours); "See relevant pay band in Table 4/5" is in going_rates.notes; Table 4/5 rows have soc_code NULL. Some NI dental rows publish no weekly hours (basis_hours NULL). T15.3 must handle these.
- T15.2: options F–J apply under SW 4.2(b) (pre-4-Apr-2024 continuous SW permission **or** a "Health and Care ASHE salary job"); stored as applies_to=transitional_pre_2024. The Health and Care ASHE job list in Appendix Skilled Worker is not parsed yet; T15.3 decides if it needs it.
- T15.2: TSL removal_date stores the SW 6.1A(b) date: the CoS must be issued **before** 31 Dec 2026. ISL removal_date is the published "Removal date" column.
- T15.2: publishing from the CLI writes no audit event (no platform-admin actor); T15.7's admin screen must audit publish/rollback.

## Strategy / decisions taken
- Embedding model: BAAI/bge-small-en-v1.5 (384 dimensions, in fastembed 0.9.1), matching vector(384).
- The 231 "see" cross-references (no occupation code, marker "}}}}") are counted and not loaded. Any other odd code stops the load.
- Raw ONS files are committed in data/raw/ (about 3.9 MB) with sidecar JSON (URL, bytes, SHA-256) for provenance. data/import_soc.py refuses a file whose hash differs from its sidecar and never overwrites it.
- Import is an upsert on natural keys (unit group code; index title, qualifiers, code). It never writes rqf_level, so T15.2 keeps its values across re-imports (test).
- The plan's "about 30,110" index entries is replaced by the file's count (32,670 records, 32,439 with a code). The file is the source of truth.
- Tenant access to the reference tables is SELECT only (grant plus a read policy under RLS); the owner role writes them (test: a tenant DELETE changes nothing).
- Push target: origin/dev, as AGENTS.md says (main is protected; PRs only). A memory note says push to origin/main; I followed AGENTS.md.
- T15.2: new module app/modules/soc_rules (models, source, importer). No new dependency: GOV.UK HTML parsed with stdlib html.parser.
- T15.2: extra columns beyond plan 6.10, all from the page: going_rates title/administration/related_titles/soc2010_codes; pay_scale_rates source_table/basis_hours (soc_code nullable for Tables 4/5); shortage_list_entries title/job_types; salary_rules requirement_text/further_rules; rules_versions table_notes (each table's notes).
- T15.2: dependants_allowed = code in Table 1, 2 or 3 (SW 29.1A); transitional exceptions left to the engine.
- T15.2: rqf_level at publish: Table 1/3 → 6; 1a/2aa/3a → 3-5 except codes the 1a notes call RQF level 2 (6135) → below; 2a → below; else NULL. Each table's notes are checked for that wording first.
- T15.2: same page hashes as the newest version → no new draft; a newer import deletes the older unpublished draft.

## Owner actions needed
- Load the SOC tables into your database: `cd api && DATABASE_URL_OWNER=<owner connection string> uv run python ../data/import_soc.py`. Set the variable in your shell; do not paste it in chat. The first run downloads the embedding model (about 70 MB) and takes about 4 minutes. Until you run it, the database has no SOC rows.
- Review and publish rules v1: `cd api && DATABASE_URL_OWNER=<owner connection string> uv run python ../data/import_rules.py` prints the draft id and row counts; once approved, `... ../data/import_rules.py --publish <draft id>`. Run import_soc.py first so RQF levels land on the unit groups. Set the variable in your shell; do not paste it in chat.
