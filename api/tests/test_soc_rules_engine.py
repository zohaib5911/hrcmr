"""T15.3: golden tests for the rules engine. The rules are the GOV.UK pages saved in data/raw/rules
(updated 29 Oct 2026), parsed as the importer parses them. Every expected figure is a published
rate or threshold, or that figure pro-rated as SW 14.4 says. No database, no network."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.soc_rules.engine import (
    Applicant,
    CheckInput,
    CheckResult,
    RulesData,
    evaluate,
)
from app.modules.soc_rules.source import PAGE_KINDS, load_rules_source

RULES = Path(__file__).resolve().parents[2] / "data" / "raw" / "rules"
BEFORE_TSL_END = dt.date(2026, 11, 15)
AFTER_2026 = dt.date(2027, 1, 5)


@pytest.fixture(scope="module")
def rules() -> RulesData:
    source = load_rules_source(
        {
            kind: (
                RULES / f"appendix-{kind}-2026-10-29.html",
                RULES / f"appendix-{kind}-2026-10-29.json",
            )
            for kind in PAGE_KINDS
        }
    )
    return RulesData.from_source(source, version_id="v-test", name="29 October 2026")


def _check(
    rules: RulesData,
    code: str,
    salary: str,
    *,
    hours: str = "37.5",
    per: str = "year",
    nation: str = "England",
    cos: dt.date = BEFORE_TSL_END,
    applicant: Applicant | None = None,
    role: str | None = None,
    area: str | None = None,
) -> CheckResult:
    return evaluate(
        rules,
        CheckInput(
            soc_code=code,
            weekly_hours=Decimal(hours),
            offered_salary=Decimal(salary),
            salary_per=per,
            work_nation=nation,
            cos_assignment_date=cos,
            applicant=applicant or Applicant(),
            pay_scale_role=role,
            pay_scale_administration=area,
        ),
    )


def _minimums(result: CheckResult) -> dict[str, Decimal | None]:
    return {o.option: o.minimum_required for o in result.options}


# 1
def test_2134_at_37_5_hours_needs_the_going_rate(rules: RulesData) -> None:
    result = _check(rules, "2134", "54700")
    assert result.eligibility.status == "eligible"
    assert result.going_rate == Decimal("54700.00")
    assert _minimums(result) == {"A": Decimal("54700.00")}
    assert result.verdict.meets is True
    assert result.verdict.option == "A"
    assert result.dependants_allowed is True
    assert result.rules_version_name == "29 October 2026"


# 2
def test_2134_new_entrant_uses_70_percent_with_the_33400_floor(rules: RulesData) -> None:
    result = _check(rules, "2134", "38300", applicant=Applicant(under_26=True))
    assert _minimums(result) == {"A": Decimal("54700.00"), "E": Decimal("38300.00")}
    assert result.verdict.meets is True
    assert result.verdict.option == "E"
    assert any("4 years" in n for n in result.notes)


# 3
def test_part_time_30_hours_pro_rates_the_going_rate_not_the_threshold(rules: RulesData) -> None:
    result = _check(rules, "2134", "43760", hours="30")
    assert result.going_rate == Decimal("43760.00")  # 54,700 x 30 / 37.5
    assert _minimums(result)["A"] == Decimal("43760.00")
    assert result.verdict.meets is True
    # 2462: 35,700 x 30 / 37.5 = 28,560 is below the 41,700 threshold, which is not pro-rated.
    quality = _check(rules, "2462", "36000", hours="30")
    assert _minimums(quality)["A"] == Decimal("41700")


# 4
def test_short_by_the_difference_to_the_lowest_option(rules: RulesData) -> None:
    result = _check(rules, "2134", "50000")
    assert result.verdict.meets is False
    assert result.verdict.short_by == Decimal("4700.00")
    assert result.verdict.hours_needed is None  # the going rate itself is not met


# 5
def test_more_hours_at_the_same_hourly_pay_can_meet_the_threshold(rules: RulesData) -> None:
    result = _check(rules, "2462", "36000", hours="30")
    assert result.verdict.meets is False
    assert result.verdict.short_by == Decimal("5700")
    assert result.verdict.hours_needed == Decimal("34.75")  # 41,700 / (36,000 / 30)


# 6
def test_relevant_phd_and_stem_phd_options(rules: RulesData) -> None:
    phd = _check(rules, "2134", "49200", applicant=Applicant(phd_relevant=True))
    assert _minimums(phd)["B"] == Decimal("49200.00")
    assert phd.verdict.option == "B"
    stem = _check(rules, "2134", "43700", applicant=Applicant(stem_phd=True))
    assert _minimums(stem)["C"] == Decimal("43700.00")
    assert stem.verdict.option == "C"


# 7
def test_no_phd_options_where_the_table_says_not_eligible(rules: RulesData) -> None:
    applicant = Applicant(phd_relevant=True, stem_phd=True, skilled_worker_before_2025_07_22=True)
    result = _check(rules, "1211", "40000", applicant=applicant)
    assert "B" not in _minimums(result)
    assert "C" not in _minimums(result)


# 8
def test_isl_bricklayer_before_the_removal_date(rules: RulesData) -> None:
    result = _check(rules, "5313", "33400")
    assert result.eligibility.status == "isl"
    assert result.eligibility.label == "On ISL until 31 December 2026"
    assert _minimums(result) == {"D": Decimal("33400.00")}  # only D on a Table 1a code
    assert result.verdict.meets is True
    assert result.dependants_allowed is False


# 9
def test_isl_bricklayer_after_the_removal_date_is_not_eligible(rules: RulesData) -> None:
    result = _check(rules, "5313", "40000", cos=AFTER_2026)
    assert result.eligibility.status == "ineligible"
    assert result.options == ()
    assert any("removed on 31 December 2026" in n for n in result.notes)


# 10
def test_isl_removal_with_sw_11_2_and_transitional_permission(rules: RulesData) -> None:
    applicant = Applicant(skilled_worker_before_2025_07_22=True, previous_isl_same_job=True)
    result = _check(rules, "5313", "33400", cos=AFTER_2026, applicant=applicant)
    assert result.eligibility.status == "eligible_transitional"
    assert _minimums(result) == {"A": Decimal("41700"), "D": Decimal("33400.00")}
    assert result.verdict.option == "D"
    assert result.dependants_allowed is True  # SW 29.1A(a)(ii)


# 11
def test_a_table_6_code_is_not_eligible(rules: RulesData) -> None:
    result = _check(rules, "1112", "90000")
    assert result.eligibility.label == "Not eligible (Table 6)"
    assert result.title == "Elected officers and representatives"
    assert result.verdict.meets is None
    assert result.dependants_allowed is False


# 12
def test_table_2a_needs_pre_2024_permission_and_the_same_sponsor(rules: RulesData) -> None:
    other_sponsor = _check(
        rules, "6116", "31300", applicant=Applicant(skilled_worker_before_2024_04_04=True)
    )
    assert other_sponsor.eligibility.label == "Not eligible (Table 6)"
    same = _check(
        rules,
        "6116",
        "31300",
        applicant=Applicant(skilled_worker_before_2024_04_04=True, same_sponsor=True),
    )
    assert same.eligibility.status == "eligible_transitional"
    assert _minimums(same)["F"] == Decimal("31300.00")
    assert same.verdict.meets is True


# 13
def test_tsl_code_with_a_dependants_note(rules: RulesData) -> None:
    result = _check(rules, "3544", "41700")
    assert result.eligibility.status == "tsl"
    assert result.eligibility.label == "On TSL until 31 December 2026"
    assert _minimums(result) == {"A": Decimal("41700")}  # going rate 34,900; no salary discount
    assert result.dependants_allowed is False
    assert any("Temporary Shortage List job" in n for n in result.notes)


# 14
def test_tsl_after_2026_is_pending_a_government_decision(rules: RulesData) -> None:
    result = _check(rules, "3544", "41700", cos=AFTER_2026)
    assert result.eligibility.status == "ineligible"
    assert any("pending government decision" in n for n in result.notes)


# 15
def test_tsl_job_type_limits_are_noted(rules: RulesData) -> None:
    result = _check(rules, "3429", "41700")
    assert any(
        n.startswith("TSL: only these job types: Industrial and product designers")
        for n in result.notes
    )


# 16
def test_isl_code_also_in_table_1_gets_option_d_and_dependants(rules: RulesData) -> None:
    result = _check(rules, "2112", "40300")
    assert result.eligibility.status == "eligible"
    assert _minimums(result) == {"A": Decimal("41700"), "D": Decimal("40300.00")}
    assert result.verdict.option == "D"
    assert result.dependants_allowed is True


# 17
def test_isl_nation_limits(rules: RulesData) -> None:
    england = _check(rules, "1212", "33400", nation="England")
    assert england.eligibility.status == "ineligible"
    assert any("listed only for Scotland" in n for n in england.notes)
    scotland = _check(rules, "1212", "33400", nation="Scotland")
    assert scotland.eligibility.status == "isl"
    assert any("fishing boat masters" in n for n in scotland.notes)


# 18
def test_care_workers_cannot_come_from_outside_the_uk(rules: RulesData) -> None:
    outside = _check(rules, "6135", "33400")
    assert outside.eligibility.status == "ineligible"
    assert any("SW 6.1B" in n for n in outside.notes)
    inside = _check(
        rules, "6135", "33400", cos=AFTER_2026, applicant=Applicant(situation="extending")
    )
    assert inside.eligibility.label == "On ISL until 22 July 2028"
    assert inside.verdict.option == "D"
    assert inside.dependants_allowed is False


# 19
def test_transitional_options_f_to_j_use_table_2(rules: RulesData) -> None:
    applicant = Applicant(skilled_worker_before_2024_04_04=True, under_26=True)
    result = _check(rules, "2134", "28000", applicant=applicant)
    minimums = _minimums(result)
    assert minimums["F"] == Decimal("40000.00")
    assert minimums["J"] == Decimal("28000.00")
    assert result.verdict.option == "J"


# 20
def test_nurse_on_agenda_for_change_band_5(rules: RulesData) -> None:
    result = _check(rules, "2231", "29970", role="Band 5")
    assert result.eligibility.status == "eligible"
    assert _minimums(result) == {"K": Decimal("29970.00")}
    assert result.verdict.meets is True
    # Scotland's Table 4 rates are for a 37-hour week: 31,892 x 37.5 / 37.
    scotland = _check(rules, "2231", "33000", nation="Scotland", role="Band 5")
    assert _minimums(scotland)["K"] == Decimal("32322.97")


# 21
def test_band_3_needs_pre_2025_permission_except_6131(rules: RulesData) -> None:
    nurse = _check(rules, "2231", "26000", role="Band 3")
    assert nurse.verdict.meets is None
    auxiliary = _check(rules, "6131", "25000", role="Band 3")
    assert auxiliary.eligibility.status == "eligible"
    assert _minimums(auxiliary)["K"] == Decimal("25000")  # band 3 is 24,071: the floor wins
    assert auxiliary.dependants_allowed is False  # Table 3a is not Table 1, 2 or 3


# 22
def test_doctors_pro_rate_from_a_40_hour_week(rules: RulesData) -> None:
    result = _check(
        rules, "2211", "43939.20", hours="48", role="Foundation year 1 (F1) and equivalent"
    )
    assert _minimums(result)["K"] == Decimal("43939.20")  # 36,616 x 48 / 40
    assert result.verdict.meets is True


# 23
def test_teachers_use_the_table_5_pay_area(rules: RulesData) -> None:
    result = _check(rules, "2314", "38766", role="Qualified teachers", area="Inner London")
    assert _minimums(result)["K"] == Decimal("38766")
    assert any("not pro-rated" in n for n in result.notes)


# 24
def test_a_table_3_code_without_a_role_lists_the_roles(rules: RulesData) -> None:
    result = _check(rules, "2231", "30000")
    k = next(o for o in result.options if o.option == "K")
    assert k.minimum_required is None
    assert result.verdict.meets is None
    assert any(n.startswith("Option K needs the band or role: Band 3") for n in result.notes)


# 25
def test_table_3a_teaching_assistant_needs_pre_2025_permission(rules: RulesData) -> None:
    new = _check(rules, "6112", "25000")
    assert new.eligibility.status == "ineligible"
    held = _check(
        rules, "6112", "25000", applicant=Applicant(skilled_worker_before_2025_07_22=True)
    )
    assert _minimums(held) == {"K": Decimal("25000")}  # 23,656 full-time; the floor wins


# 26
def test_over_48_hours_only_the_first_48_count_towards_the_threshold(rules: RulesData) -> None:
    # SW 14.3's own example: 60 hours at £15 an hour counts as £37,440 a year.
    result = _check(rules, "2134", "15", hours="60", per="hour")
    assert result.offered_annual == Decimal("46800.00")
    assert result.salary_for_threshold == Decimal("37440.00")
    assert result.going_rate == Decimal("87520.00")  # SW 14.4(d): full hours
    assert result.verdict.meets is False
    assert any("first 48 hours" in n for n in result.notes)


# 27
def test_bad_input_is_refused(rules: RulesData) -> None:
    with pytest.raises(ValueError, match="salary_per"):
        _check(rules, "2134", "1", per="fortnight")
    with pytest.raises(ValueError, match="weekly hours"):
        _check(rules, "2134", "1", hours="0")
