import pytest

from app.modules.register.geo import (
    ITL1_REGIONS,
    geocode,
    normalise_places,
    parse_companies,
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
