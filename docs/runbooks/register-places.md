# Sponsor register: ONS place names for regions

The public register pages place each sponsor in one of the 12 ITL1 regions by matching its
town (and county) against the ONS **Index of Place Names** (IPN). The match is local: no
per-sponsor network lookup is ever made. Towns that are missing or ambiguous (same name in two
regions, no county match) stay unplaced (`place_precision = none`).

## Get the file

1. Open the ONS Open Geography Portal (geoportal.statistics.gov.uk) and search for
   "Index of Place Names in Great Britain". Take the newest edition (e.g. `IPN_GB_2024`).
2. Download the CSV. It is public data (Open Government Licence); no account or key is needed.
3. Keep the edition name: it is recorded as the dataset version.

The loader reads the IPN columns by pattern, so a new edition's year digits do not matter:
`place<yy>nm` (place), `cty<yy>nm` / `ctyhistnm` / `ctyltnm` (county spellings),
`rgn<yy>cd` and `ctry<yy>cd` (region; Welsh and Scottish places use the country code),
`lat`, `long`. A file already in the internal form
`place_name,county,region,lat,lon` is accepted too.

## Load it

From `api/`, with `DATABASE_URL_OWNER` set (the same owner URL the worker uses):

```bash
uv run python -m app.cli load-places /path/to/IPN_GB_2024.csv --version "IPN 2024"
```

This stores the normalised file in `register_place_datasets` (version, source file name,
SHA-256, row count, load time), makes it the active dataset, and re-places every sponsor it
can match. A file with the wrong columns or no usable rows is refused and nothing changes.

## After loading

Every scheduled or manual register import (`register_ingest`) places new and still-unplaced
sponsors from the newest loaded dataset. If no dataset was ever loaded, the import still
succeeds, the worker logs `register_places_missing`, and sponsors stay unplaced until an
operator runs `load-places`. Load a new edition the same way; the newest one wins.
