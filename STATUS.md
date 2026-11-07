# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: 32f6d41
State: IN PROGRESS

## Last completed
- T15.1 — ONS SOC 2020 import and local embeddings (S!). 412 unit groups, 32,439 index entries.

## Current task
- T15.2 — Rules-data importer (draft rules version, fixtures, salary rules) (B)
  - [ ] 1 fetch GOV.UK pages (Appendix Skilled Occupations, ISL, TSL, caseworker guidance) into saved HTML fixtures with sidecars
  - [ ] 2 models + migration 0041 (rules_versions, going_rates, pay_scale_rates, ineligible_codes, shortage_list_entries, salary_rules)
  - [ ] 3 HTML table parsers + unit tests on fixtures
  - [ ] 4 importer into a draft rules_version, diff vs live, rqf_level; CLI data/import_rules.py; DB tests
  - [ ] 5 full run counts, PROGRESS, tick
- Resume note: see journal and last commit Next: line.

## Next tasks
- T15.3 (B) rules engine; T15.4 (S!), T15.5 (S!) after it

## Health
- CI on dev: not run since T15.1    CI on main: green (last PR #22)
- Local checks run: none yet this session

## Issues / suggestions
- Test harness: `temporary_database()` sets the cluster-wide roles `app_owner` and `app_user` to a fresh random password each time. Two DB-using runs at once break each other's owner connection. My first full ONS load failed this way (password authentication failed for app_owner, before any rows were written); the re-run, with nothing else using the DB, succeeded. Do not run DB suites in parallel with another DB job. Worth a fix in the harness (per-database roles, or a lock) before Phase 15 gate.
- The ONS coding index has 58 rows whose title is a letter only (A, A1, A2…). They are loaded as published. T15.4 search must not treat them as job titles.
- `index_title` holds the reverse-order title ("Administrator, holding, fund"), as the spec's INDEXOCC column does. The natural-order title ("Fund holding administrator") is not stored: 11 natural-order keys collide. T15.4 search may need it; decide there (new column in a new migration).
- rqf_level is NULL on every unit group until T15.2 fills it from the Skilled Occupations appendix.
- Embedding text is unit group title + description + tasks + related titles, and index title + qualifiers. Retrieval quality is not yet measured (T15.4 will).

## Strategy / decisions taken
- Embedding model: BAAI/bge-small-en-v1.5 (384 dimensions, in fastembed 0.9.1), matching vector(384).
- The 231 "see" cross-references (no occupation code, marker "}}}}") are counted and not loaded. Any other odd code stops the load.
- Raw ONS files are committed in data/raw/ (about 3.9 MB) with sidecar JSON (URL, bytes, SHA-256) for provenance. data/import_soc.py refuses a file whose hash differs from its sidecar and never overwrites it.
- Import is an upsert on natural keys (unit group code; index title, qualifiers, code). It never writes rqf_level, so T15.2 keeps its values across re-imports (test).
- The plan's "about 30,110" index entries is replaced by the file's count (32,670 records, 32,439 with a code). The file is the source of truth.
- Tenant access to the reference tables is SELECT only (grant plus a read policy under RLS); the owner role writes them (test: a tenant DELETE changes nothing).
- Push target: origin/dev, as AGENTS.md says (main is protected; PRs only). A memory note says push to origin/main; I followed AGENTS.md.

## Owner actions needed
- Load the SOC tables into your database: `cd api && DATABASE_URL_OWNER=<owner connection string> uv run python ../data/import_soc.py`. Set the variable in your shell; do not paste it in chat. The first run downloads the embedding model (about 70 MB) and takes about 4 minutes. Until you run it, the database has no SOC rows.
