import pytest

from app.modules.register.geo import (
    ITL1_REGIONS,
    geocode,
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
