"""T15.2: the saved GOV.UK Immigration Rules pages parse into rules-data rows, and a page that has
changed shape stops the parse. Runs on the pages saved in data/raw/rules (the fixtures); no network,
no database. Expected figures are the ones printed on those pages."""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.soc_rules.source import (
    PAGE_KINDS,
    RulesSource,
    load_rules_source,
    parse_salary_list,
    parse_salary_rules,
    parse_skilled_occupations,
    parse_temporary_shortage_list,
)

RULES = Path(__file__).resolve().parents[2] / "data" / "raw" / "rules"
RELEASE = "2026-10-29"


def _page(kind: str) -> Path:
    return RULES / f"appendix-{kind}-{RELEASE}.html"


def _pages() -> dict[str, tuple[Path, Path]]:
    return {kind: (_page(kind), _page(kind).with_suffix(".json")) for kind in PAGE_KINDS}


def _html(kind: str) -> str:
    return _page(kind).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def source() -> RulesSource:
    return load_rules_source(_pages())


def test_every_table_is_read_with_the_page_row_counts(source: RulesSource) -> None:
    assert Counter(r.table for r in source.going_rates) == {
        "1": 91,
        "1a": 170,
        "2": 91,
        "2aa": 170,
        "2a": 9,
        "2b": 17,
        "3": 42,  # 2211, 2253 and 2312 once per nation; 2212 copies 2211's four
        "3a": 8,
    }
    assert Counter(r.source_table for r in source.pay_scales) == {
        "3": 103,
        "3a": 2,
        "4": 40,
        "5": 33,
    }
    assert len(source.ineligible) == 114
    assert Counter(r.list_name for r in source.shortage) == {"ISL": 25, "TSL": 52}
    assert source.effective_from == dt.date(2026, 10, 29)
    assert [p.kind for p in source.pages] == list(PAGE_KINDS)
    assert all(len(p.sha256) == 64 for p in source.pages)


def test_table_1_rates_are_the_published_figures(source: RulesSource) -> None:
    row = next(r for r in source.going_rates if r.table == "1" and r.soc_code == "2134")
    assert row.title == "Programmers and software development professionals"
    assert (row.annual_rate, row.hourly_rate) == (Decimal("54700"), Decimal("28.05"))
    assert (row.rate_90, row.rate_80, row.rate_70) == (
        Decimal("49200"),
        Decimal("43700"),
        Decimal("38300"),
    )
    assert row.phd_points_eligible is True
    assert row.basis_hours == Decimal("37.5")
    assert "Software developers" in row.related_titles


def test_not_applicable_is_stored_as_no_rate(source: RulesSource) -> None:
    row = next(r for r in source.going_rates if r.table == "1a" and r.soc_code == "1211")
    assert row.annual_rate == Decimal("35900")
    assert row.rate_90 is None
    assert row.rate_80 is None
    assert row.rate_70 == Decimal("33400")
    assert row.phd_points_eligible is False


def test_table_2_keeps_the_soc_2010_codes(source: RulesSource) -> None:
    row = next(r for r in source.going_rates if r.table == "2" and r.soc_code == "1111")
    assert row.soc2010_codes == ("1115", "1172")
    assert row.annual_rate == Decimal("60000")


def test_table_3_roles_carry_their_nation_and_weekly_hours(source: RulesSource) -> None:
    roles = {
        (r.soc_code, r.administration, r.band_or_role): r
        for r in source.pay_scales
        if r.source_table == "3"
    }
    f1 = roles[("2211", "England", "Foundation year 1 (F1) and equivalent")]
    assert (f1.annual_rate, f1.basis_hours) == (Decimal("36616"), Decimal("40"))
    # A bullet's own "(37.5 hour week)" beats the cell's 40-hour default.
    consultant = roles[("2211", "Wales", "Consultant and equivalent")]
    assert (consultant.annual_rate, consultant.basis_hours) == (Decimal("106000"), Decimal("37.5"))
    # 2212 is "As SOC 2020 occupation code 2211": the same figures under its own code.
    assert roles[("2212", "England", "Foundation year 1 (F1) and equivalent")].annual_rate == (
        Decimal("36616")
    )
    # 2226 points to Table 4, except Scottish educational psychologists.
    assert roles[("2226", "Scotland", "Educational Psychologist")].annual_rate == Decimal("56763")
    # FE lecturers: a full-time teacher, no weekly hours stated.
    assert roles[("2312", "Wales", "Main grade lecturer")].basis_hours is None


def test_table_3_references_and_single_rates(source: RulesSource) -> None:
    rows = {(r.table, r.soc_code, r.administration): r for r in source.going_rates}
    nurse = rows[("3", "2231", "")]
    assert nurse.annual_rate is None
    assert "See Table 4" in nurse.notes
    assert "See Table 5" in rows[("3", "2314", "")].notes
    assistant = rows[("3a", "6112", "")]
    assert (assistant.annual_rate, assistant.hourly_rate) == (Decimal("23656"), Decimal("12.26"))
    assert rows[("3a", "6131", "")].notes.startswith("Note: For Skilled Worker purposes")


def test_tables_4_and_5_are_read_by_administration(source: RulesSource) -> None:
    bands = {
        (r.administration, r.band_or_role): r for r in source.pay_scales if r.source_table == "4"
    }
    assert bands[("England", "Band 5")].annual_rate == Decimal("29970")
    assert bands[("England", "Band 5")].basis_hours == Decimal("37.5")
    assert bands[("Scotland", "Band 5")].basis_hours == Decimal(
        "37"
    )  # "in Scotland, a 37-hour week"
    assert all(r.soc_code is None for r in source.pay_scales if r.source_table in ("4", "5"))
    teachers = {
        (r.administration, r.band_or_role): r.annual_rate
        for r in source.pay_scales
        if r.source_table == "5"
    }
    assert teachers[("Inner London", "Qualified teachers")] == Decimal("38766")
    # "-" cells are skipped, not stored as zero.
    assert ("Northern Ireland", "Unqualified teachers / Probationers") not in teachers


def test_table_6_lists_ineligible_codes(source: RulesSource) -> None:
    first = source.ineligible[0]
    assert (first.soc_code, first.title) == ("1112", "Elected officers and representatives")
    assert first.related_titles == ("Councillor (local government)", "Member of Parliament")
    assert "not eligible for the Skilled Worker" in first.reason


def test_immigration_salary_list_entries() -> None:
    rows = {r.soc_code: r for r in parse_salary_list(_html("immigration-salary-list"))}
    assert len(rows) == 25
    bricklayers = rows["5313"]
    assert bricklayers.title == "Bricklayers"
    assert bricklayers.condition_text == "all jobs"
    assert bricklayers.nations == ("England", "Scotland", "Wales", "Northern Ireland")
    assert bricklayers.removal_date == dt.date(2026, 12, 31)
    assert rows["6135"].removal_date == dt.date(2028, 7, 22)
    assert rows["6136"].removal_date == dt.date(2028, 7, 22)
    assert rows["1212"].nations == ("Scotland",)
    assert rows["1212"].condition_text == "only “fishing boat masters”"


def test_temporary_shortage_list_from_sw_6_1a() -> None:
    rows = {r.soc_code: r for r in parse_temporary_shortage_list(_html("skilled-worker"))}
    assert len(rows) == 52
    assert rows["3544"].title == "Data analysts"
    assert rows["3544"].condition_text == "all jobs"
    assert {r.removal_date for r in rows.values()} == {dt.date(2026, 12, 31)}
    design = rows["3429"]
    assert design.condition_text == "only the following job types:"
    assert design.job_types == (
        "Industrial and product designers",
        "Packaging designers",
        "Performance make-up artists",
        "Set designers",
        "Visual merchandising managers and designers",
    )
    assert len(rows["5319"].job_types) == 6


def test_salary_rules_a_to_k_from_the_points_table() -> None:
    rules = {r.option: r for r in parse_salary_rules(_html("skilled-worker"))}
    assert list(rules) == list("ABCDEFGHIJK")
    expected = {
        "A": ("41700", 100, "standard", "new"),
        "B": ("37500", 90, "phd", "new"),
        "C": ("33400", 80, "stem_phd", "new"),
        "D": ("33400", 100, "isl", "new"),
        "E": ("33400", 70, "new_entrant", "new"),
        "F": ("31300", 100, "standard", "transitional_pre_2024"),
        "G": ("28200", 90, "phd", "transitional_pre_2024"),
        "H": ("25000", 80, "stem_phd", "transitional_pre_2024"),
        "I": ("25000", 100, "isl", "transitional_pre_2024"),
        "J": ("25000", 70, "new_entrant", "transitional_pre_2024"),
        "K": ("25000", 100, "health_education", "health_care"),
    }
    for option, (threshold, pct, key, applies) in expected.items():
        rule = rules[option]
        assert (rule.general_threshold, rule.going_rate_pct) == (Decimal(threshold), pct), option
        assert (rule.criteria_key, rule.applies_to) == (key, applies), option


# --- a changed page stops the parse ------------------------------------------------------------


def test_a_missing_table_stops_the_parse() -> None:
    html = _html("skilled-occupations").replace("Table 6: SOC 2020", "Table six: SOC 2020")
    with pytest.raises(ValueError, match="tables missing: 6"):
        parse_skilled_occupations(html)


def test_a_rate_in_a_new_format_stops_the_parse() -> None:
    html = _html("skilled-occupations").replace("£88,100<br>(£45.18 per hour)", "£88,100 a year")
    with pytest.raises(ValueError, match="unrecognised rate"):
        parse_skilled_occupations(html)


def test_a_new_column_stops_the_parse() -> None:
    html = _html("skilled-occupations").replace(
        "Eligible for PhD points (SW)?", "Eligible for doctorate points?", 1
    )
    with pytest.raises(ValueError, match="unknown column"):
        parse_skilled_occupations(html)


def test_changed_option_wording_stops_the_parse() -> None:
    html = _html("skilled-worker").replace("has a PhD in a STEM subject", "has a doctorate in STEM")
    with pytest.raises(ValueError, match="option C"):
        parse_salary_rules(html)


def test_a_missing_tsl_end_date_stops_the_parse() -> None:
    html = _html("skilled-worker").replace("to an applicant before 31 December 2026", "")
    with pytest.raises(ValueError, match=r"SW 6\.1A\(b\)"):
        parse_temporary_shortage_list(html)


def test_a_page_that_differs_from_its_sidecar_is_refused(tmp_path: Path) -> None:
    pages = _pages()
    html, sidecar = pages["immigration-salary-list"]
    copy = tmp_path / html.name
    copy.write_bytes(html.read_bytes() + b"\n")
    pages["immigration-salary-list"] = (copy, sidecar)
    with pytest.raises(ValueError, match="does not match its sidecar"):
        load_rules_source(pages)


def test_sidecars_record_the_gov_uk_source() -> None:
    for kind in PAGE_KINDS:
        record = json.loads(_page(kind).with_suffix(".json").read_text(encoding="utf-8"))
        assert record["source_url"].startswith("https://www.gov.uk/guidance/immigration-rules/")
        assert record["govuk_updated_at"].startswith(RELEASE)
