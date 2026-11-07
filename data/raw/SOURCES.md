# SOC 2020 source files (T15.1)

Downloaded 2026-11-08 from the Office for National Statistics. Each file has a sidecar `.json` with
its source URL, byte count and SHA-256. `data/import_soc.py` checks the checksum before it loads a
file, and downloads it again only when the file is missing or does not match.

| File | Content | Source page | Download URL | Bytes | SHA-256 |
|---|---|---|---|---|---|
| `soc2020-coding-index-2026-08-27.xlsx` | SOC 2020 coding index (Version 14): job titles to 4-digit codes. 32,670 records; 32,439 carry a code, 231 are "see" cross-references with no code and are not loaded. | [Volume 2](https://www.ons.gov.uk/methodology/classificationsandstandards/standardoccupationalclassificationsoc/soc2020/soc2020volume2codingrulesandconventions) | [xlsx](https://www.ons.gov.uk/file?uri=/methodology/classificationsandstandards/standardoccupationalclassificationsoc/soc2020/soc2020volume2codingrulesandconventions/soc2020volume2thecodingindexexcel20260827v3.xlsx) | 3719121 | `25dbe51cf21d4c3bb74b7e087aaa748eda1d443bade76a4e801685cee5966a57` |
| `soc2020-unit-groups-2026-08-27.xlsx` | SOC 2020 structure and descriptions of the 412 unit groups (group title, description, tasks, entry routes, related job titles). | [Volume 1](https://www.ons.gov.uk/methodology/classificationsandstandards/standardoccupationalclassificationsoc/soc2020/soc2020volume1structureanddescriptionsofunitgroups) | [xlsx](https://www.ons.gov.uk/file?uri=/methodology/classificationsandstandards/standardoccupationalclassificationsoc/soc2020/soc2020volume1structureanddescriptionsofunitgroups/soc2020volume1structureanddescriptionofunitgroupsexcel20260827.xlsx) | 289135 | `b9e3e464b877418ef1258ab4cb9e3b0ffe43ee9fd418d872068c2749b2337de3` |

Licence: Open Government Licence v3.0, as recorded in plan.md 6.10. The ONS licence line on each page was not re-read.

The coding-index count in plan.md (about 30,110) is lower than the file (32,670 records, 32,439 with a code).
The file is the source of truth; the row counts loaded are recorded in PROGRESS.md.
