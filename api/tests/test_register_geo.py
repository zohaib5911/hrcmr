import gzip
import hashlib
import io

import pytest

from app.modules.register.geo import (
    ITL1_REGIONS,
    build_company_index,
    geocode,
    normalise_places,
    parse_companies,
    parse_company_index,
    parse_places,
    sic_section,
)

PLACES = (
    b"place_name,county,region,lat,lon\n"
    b"Leeds,West Yorkshire,Yorkshire and The Humber,53.8,-1.55\n"
    b"London,,London,51.5,-0.12\n"
    b"Newport,Gwent,Wales,51.58,-3.0\n"
    b"Newport,Shropshire,West Midlands,52.77,-2.38\n"
    b"Nowhere,,Atlantis,1,1\n"
)


def test_geocode_precision() -> None:
    places = parse_places(PLACES)
    assert geocode(places, "Leeds", "West Yorkshire")[1] == "exact"
    assert geocode(places, " LEEDS ", "")[0].region == "Yorkshire and The Humber"  # type: ignore[union-attr]
    assert geocode(places, "Leeds", "Elsewhere")[1] == "town"
    assert geocode(places, "Newport", "")[1] == "none"  # ambiguous: never guess
    assert geocode(places, "Newport", "Gwent")[0].region == "Wales"  # type: ignore[union-attr]
    assert geocode(places, "Nowhere", "") == (None, "none")


def test_twelve_regions_and_bad_files() -> None:
    assert len(ITL1_REGIONS) == 12
    with pytest.raises(ValueError, match="columns"):
        parse_places(b"a,b\n1,2\n")
    with pytest.raises(ValueError, match="Empty"):
        parse_places(b"place_name,county,region,lat,lon\nX,,Atlantis,1,1\n")


@pytest.mark.parametrize(
    ("code", "section"),
    [
        ("62012 - Business and domestic software", "J"),
        ("86101", "Q"),
        ("01110", "A"),
        ("47110", "G"),
        ("99999", "U"),
        ("", None),
        ("4", None),
        ("00000", None),
    ],
)
def test_sic_section(code: str, section: str | None) -> None:
    assert sic_section(code) == section


def test_companies_ambiguous_names_dropped() -> None:
    data = (
        b"CompanyName,CompanyNumber,SICCode.SicText_1\n"
        b"Example Care Ltd,01234567,87100 - Residential nursing\n"
        b"Twin Ltd,1,62012\nTwin Ltd.,2,62012\n"
    )
    assert parse_companies(data) == {"example care ltd": ("01234567", "Q")}
    with pytest.raises(ValueError, match="columns"):
        parse_companies(b"x\n1\n")


def test_company_index_streams_keeps_three_fields_and_rejects_far_duplicates() -> None:
    filler = b"".join(b"Filler %d Ltd,%08d,London,62012\n" % (i, i) for i in range(2000))
    data = (
        b"\xef\xbb\xbfCompanyName, CompanyNumber,RegAddress.PostTown,SICCode.SicText_1\n"
        b"Twin Ltd,00000001,Leeds,62012\n"
        b"Example Care Ltd,01234567,Secret Street,87100 - Residential nursing\n"
        + filler
        + b"TWIN LTD.,00000002,Bath,62012\n"
    )
    wanted = {"twin ltd", "example care ltd", "late sponsor ltd"}
    for source in (data, io.BufferedReader(io.BytesIO(gzip.compress(data)))):
        index = build_company_index(source, wanted)
        assert index.companies == {"example care ltd": ("01234567", "Q")}
        assert index.rows == 2003
    assert build_company_index(data, set()).sha256 == hashlib.sha256(data).hexdigest()
    gz = gzip.compress(data)
    assert build_company_index(gz, set()).sha256 == hashlib.sha256(gz).hexdigest()
    stored = gzip.decompress(index.content)
    lines = stored.decode().splitlines()
    assert lines[:3] == [
        "name,number,section",
        "twin ltd,00000001,J",
        "example care ltd,01234567,Q",
    ]
    assert b"Secret Street" not in stored
    assert b"Leeds" not in stored
    # Read back: the duplicate stays unmatched; only the requested sponsor names are returned.
    assert parse_company_index(index.content, wanted) == {"example care ltd": ("01234567", "Q")}
    assert parse_company_index(index.content, {"filler 7 ltd"}) == {
        "filler 7 ltd": ("00000007", "J")
    }
    assert parse_company_index(gzip.compress(data), {"twin ltd", "filler 7 ltd"}) == {
        "filler 7 ltd": ("00000007", "J")
    }  # datasets stored before the index format still read


def test_ons_index_of_place_names_is_normalised() -> None:
    ons = (
        b"\xef\xbb\xbfplace23cd,PLACE23NM,ctyhistnm,ctyltnm,rgn23cd,ctry23cd,lat,long\n"
        b"1,Leeds,Yorkshire,West Yorkshire,E12000003,E92000001,53.8,-1.55\n"
        b"2,Cardiff,Glamorgan,South Glamorgan,W99999999,W92000004,51.48,-3.18\n"
        b"3,Nowhere,,,X1,X2,1,1\n"
    )
    places = parse_places(normalise_places(ons))
    assert geocode(places, "Leeds", "Yorkshire")[1] == "exact"
    assert geocode(places, "Leeds", "West Yorkshire")[1] == "exact"
    assert geocode(places, "Cardiff", "")[0].region == "Wales"  # type: ignore[union-attr]
    assert geocode(places, "Nowhere", "") == (None, "none")
    own = b"place_name,county,region,lat,lon\nLondon,,London,51.5,-0.12\n"
    assert normalise_places(own) == own
    with pytest.raises(ValueError, match="columns"):
        normalise_places(b"place23nm,lat,long\nLeeds,1,1\n")


def test_ons_index_in_windows_1252_is_read() -> None:
    # IPN_GB_2024.csv as published by the ONS is Windows-1252, not UTF-8.
    ons = (
        "place24cd,place24nm,ctyhistnm,ctyltnm,rgn24cd,ctry24cd,lat,long\n"
        "1,A' Chrìon Làraich,Perthshire,Stirling,S99999999,S92000003,56.39,-4.62\n"
        "2,Ynys Môn,Anglesey,Isle of Anglesey,W99999999,W92000004,53.28,-4.42\n"
    ).encode("cp1252")
    places = parse_places(normalise_places(ons))
    assert geocode(places, "A' Chrìon Làraich", "")[0].region == "Scotland"  # type: ignore[union-attr]
    assert geocode(places, "Ynys Môn", "Anglesey")[1] == "exact"


def test_ons_electoral_region_wins_over_a_wrong_region_code() -> None:
    # IPN_GB_2024.csv: Bristol's split rows have no rgn23cd and its locality row says North
    # East (E12000001); eer23cd says South West (E15000009) on all of them.
    ons = (
        b"place23nm,ctyhistnm,rgn23cd,eer23cd,lat,long\n"
        b"Bristol,Gloucestershire,,E15000009,51.44,-2.56\n"
        b"Bristol,Gloucestershire,E12000001,E15000009,51.45,-2.60\n"
        b"Sunderland,Durham,,E15000001,54.89,-1.40\n"
        b"Sunderland,Lancashire,E12000002,E15000002,53.99,-2.87\n"
    )
    places = parse_places(normalise_places(ons))
    assert geocode(places, "Bristol", "")[0].region == "South West"  # type: ignore[union-attr]
    assert geocode(places, "Sunderland", "Durham")[0].region == "North East"  # type: ignore[union-attr]
    assert geocode(places, "Sunderland", "") == (None, "none")  # two regions: not guessed


def test_empty_county_row_does_not_decide_an_ambiguous_town() -> None:
    # IPN_GB_2024.csv has Sheffield in Yorkshire and a Sheffield locality in Cornwall whose
    # ceremonial county column is empty.
    own = (
        b"place_name,county,region,lat,lon\n"
        b"Sheffield,South Yorkshire,Yorkshire and The Humber,53.37,-1.35\n"
        b"Sheffield,,South West,50.09,-5.55\n"
        b"Sheffield,Cornwall,South West,50.09,-5.55\n"
    )
    places = parse_places(own)
    assert geocode(places, "Sheffield", "") == (None, "none")
    assert geocode(places, "Sheffield", "South Yorkshire")[1] == "exact"


def test_a_county_that_names_the_region_places_an_ambiguous_town() -> None:
    # IPN_GB_2024.csv: the Hounslow built-up area runs into Spelthorne (Surrey, South East), so the
    # town alone is ambiguous, and register rows give the county as "London" or "Greater London".
    ons = (
        b"place23nm,ctyhistnm,cty23nm,eer23cd,lat,long\n"
        b"Hounslow,Middlesex,Outer London,E15000007,51.47,-0.36\n"
        b"Hounslow,Middlesex,Surrey,E15000008,51.45,-0.45\n"
    )
    places = parse_places(normalise_places(ons))
    assert geocode(places, "Hounslow", "") == (None, "none")  # still never guessed
    for county in ("London", "Greater London"):
        place, precision = geocode(places, "Hounslow", county)
        assert precision == "exact"
        assert place is not None
        assert place.region == "London"
    assert geocode(places, "Hounslow", "South East")[0].region == "South East"  # type: ignore[union-attr]
