"""The sponsorship rules engine (plan 8.17, T15.3). Pure Python, no AI, no database.

Given one SOC 2020 code, the job's hours, pay, nation and CoS assignment date, and the applicant's
situation, it works out eligibility, the salary options the applicant can use with the minimum for
each, the verdict against the offered salary, dependants and notes. Every figure comes from a rules
version (``RulesData``: the parsed GOV.UK pages, or the same rows read back from the database).
Rule references are to Appendix Skilled Worker (SW) and Appendix Skilled Occupations as saved.

General guidance, not legal or immigration advice: the UI says so next to every result.
"""

from __future__ import annotations

import datetime as dt  # noqa: TC003
import re
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.soc_rules.source import (
        GoingRateRow,
        IneligibleRow,
        PayScaleRow,
        RulesSource,
        SalaryRuleRow,
        ShortageRow,
    )

PENNY = Decimal("0.01")
WEEKS_PER_YEAR = Decimal(52)  # SW 14.3's worked example: £15 x 48 x 52
THRESHOLD_HOURS_CAP = Decimal(48)  # SW 14.3: only the first 48 hours' pay counts
SALARY_PER = ("year", "month", "week", "hour")
SITUATIONS = (
    "outside_uk",
    "switching_graduate",
    "switching_student",
    "switching_other",
    "extending",
    "changing_employer",
)
# SW 6.1B: care workers and senior care workers can only get permission to stay, with conditions.
CARE_CODES = ("6135", "6136")
TABLE_1_FAMILY = ("1", "1a")
TABLE_2_FAMILY = ("2", "2aa", "2a")
LISTED_TABLES = ("1", "2", "3")  # SW 6.1(a); also the SW 29.1A dependants tables
TRANSITIONAL_2025_TABLES = ("1a", "2aa", "3a")  # SW 6.1(d)
PCT_COLUMN = {100: "annual_rate", 90: "rate_90", 80: "rate_80", 70: "rate_70"}
EXCEPT_FOR = re.compile(r"Except for “(\d{4}) ")


def _money(value: Decimal) -> Decimal:
    return value.quantize(PENNY, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------------------------
# Rules data


@dataclass(frozen=True)
class RulesData:
    version_id: str | None
    version_name: str
    effective_from: dt.date
    going_rates: tuple[GoingRateRow, ...]
    pay_scales: tuple[PayScaleRow, ...]
    ineligible: tuple[IneligibleRow, ...]
    shortage: tuple[ShortageRow, ...]
    salary_rules: tuple[SalaryRuleRow, ...]
    table_notes: dict[str, str]

    @classmethod
    def from_source(
        cls, source: RulesSource, version_id: str | None = None, name: str = "draft"
    ) -> RulesData:
        return cls(
            version_id=version_id,
            version_name=name,
            effective_from=source.effective_from,
            going_rates=source.going_rates,
            pay_scales=source.pay_scales,
            ineligible=source.ineligible,
            shortage=source.shortage,
            salary_rules=source.salary_rules,
            table_notes=source.table_notes,
        )


# ---------------------------------------------------------------------------------------------
# Inputs and outputs


@dataclass(frozen=True)
class Applicant:
    situation: str = "outside_uk"
    # Granted Skilled Worker permission under the rules before this date, continuous since.
    skilled_worker_before_2024_04_04: bool = False
    skilled_worker_before_2025_07_22: bool = False
    same_sponsor: bool = False  # applying to work for the same sponsor as the last permission
    # SW 11.2: sponsored last time in an ISL job and continuing in the same job and sponsor.
    previous_isl_same_job: bool = False
    # SW 12.2 new entrant grounds.
    under_26: bool = False
    recent_uk_student_or_graduate: bool = False
    professional_training: bool = False
    postdoctoral: bool = False
    phd_relevant: bool = False
    stem_phd: bool = False

    @property
    def before_2025(self) -> bool:
        # Continuous permission since before 4 April 2024 is also since before 22 July 2025.
        return self.skilled_worker_before_2025_07_22 or self.skilled_worker_before_2024_04_04

    @property
    def new_entrant(self) -> bool:
        return (
            self.under_26
            or self.recent_uk_student_or_graduate
            or self.professional_training
            or self.postdoctoral
        )


@dataclass(frozen=True)
class CheckInput:
    soc_code: str
    weekly_hours: Decimal
    offered_salary: Decimal
    salary_per: str
    work_nation: str
    cos_assignment_date: dt.date
    applicant: Applicant = field(default_factory=Applicant)
    # Table 3/3a/4/5 codes: the band or role, and for teachers the Table 5 pay area.
    pay_scale_role: str | None = None
    pay_scale_administration: str | None = None


@dataclass(frozen=True)
class Eligibility:
    status: str  # eligible | eligible_transitional | isl | tsl | ineligible
    label: str
    routes: tuple[str, ...]  # listed, isl, tsl, transitional_2025, transitional_2024
    tables: tuple[str, ...]
    isl_until: dt.date | None
    tsl_until: dt.date | None


@dataclass(frozen=True)
class OptionResult:
    option: str
    criteria_key: str
    table: str | None
    general_threshold: Decimal
    going_rate_pct: int
    going_rate: Decimal | None  # the share of the going rate for these hours
    minimum_required: Decimal | None
    meets: bool | None  # None when the going rate needs a band or role first


@dataclass(frozen=True)
class Verdict:
    meets: bool | None
    option: str | None
    minimum_required: Decimal | None
    short_by: Decimal | None
    hours_needed: Decimal | None  # same hourly pay, more hours, if that would be enough


@dataclass(frozen=True)
class CheckResult:
    soc_code: str
    title: str
    rules_version_id: str | None
    rules_version_name: str
    rules_effective_from: dt.date
    eligibility: Eligibility
    offered_annual: Decimal  # the offered pay as a year at the stated hours
    salary_for_threshold: Decimal  # SW 14.3: only the first 48 hours' pay
    going_rate: Decimal | None  # the 100% going rate for these hours (option A, or K)
    options: tuple[OptionResult, ...]
    verdict: Verdict
    dependants_allowed: bool
    notes: tuple[str, ...]


# ---------------------------------------------------------------------------------------------
# Engine


@dataclass
class _Context:
    rules: RulesData
    check: CheckInput
    tables: dict[str, GoingRateRow]
    notes: list[str]
    isl: ShortageRow | None
    tsl: ShortageRow | None
    isl_active: bool
    tsl_active: bool


def _annual(check: CheckInput) -> Decimal:
    if check.salary_per not in SALARY_PER:
        raise ValueError(f"salary_per must be one of {SALARY_PER}")
    if check.weekly_hours <= 0 or check.offered_salary < 0:
        raise ValueError("weekly hours must be above 0 and the salary 0 or more")
    per_year = {
        "year": Decimal(1),
        "month": Decimal(12),
        "week": WEEKS_PER_YEAR,
        "hour": check.weekly_hours * WEEKS_PER_YEAR,
    }[check.salary_per]
    return _money(check.offered_salary * per_year)


def _rows_for(rules: RulesData, code: str, nation: str) -> dict[str, GoingRateRow]:
    rows: dict[str, GoingRateRow] = {}
    for row in rules.going_rates:
        if row.soc_code == code and row.administration in ("", nation):
            rows[row.table] = row
    return rows


def _list_entry(rules: RulesData, list_name: str, code: str) -> ShortageRow | None:
    return next(
        (r for r in rules.shortage if r.list_name == list_name and r.soc_code == code), None
    )


def _exempt_codes(note: str) -> set[str]:
    """Codes a table's notes name as an exception ("Except for “6131 ...”")."""
    return set(EXCEPT_FOR.findall(note))


def _eligibility(ctx: _Context) -> Eligibility:
    check, applicant = ctx.check, ctx.check.applicant
    tables = set(ctx.tables)
    routes: list[str] = []
    if tables & set(LISTED_TABLES):
        routes.append("listed")
    if ctx.isl_active:
        routes.append("isl")
    if ctx.tsl_active:
        routes.append("tsl")
    exempt_3a = _exempt_codes(ctx.rules.table_notes.get("3a", ""))
    if "3a" in tables and check.soc_code in exempt_3a:
        routes.append("listed")  # Table 3a notes: this code without the 22 July 2025 condition
    if applicant.before_2025 and tables & set(TRANSITIONAL_2025_TABLES):
        routes.append("transitional_2025")
    if "2a" in tables and applicant.skilled_worker_before_2024_04_04 and applicant.same_sponsor:
        routes.append("transitional_2024")  # SW 6.1(f)
    if check.soc_code in CARE_CODES and applicant.situation == "outside_uk":
        ctx.notes.append(
            "SW 6.1B: care worker and senior care worker jobs can only be sponsored for "
            "permission to stay, not from outside the UK."
        )
        routes = []

    ordered = tuple(dict.fromkeys(routes))
    isl_until = ctx.isl.removal_date if ctx.isl_active and ctx.isl else None
    tsl_until = ctx.tsl.removal_date if ctx.tsl_active and ctx.tsl else None
    in_table_6 = any(r.soc_code == check.soc_code for r in ctx.rules.ineligible)
    if not ordered:
        label = (
            "Not eligible (Table 6)"
            if in_table_6
            else "Not eligible for this applicant"
            if tables
            else "Not eligible (not listed in Appendix Skilled Occupations)"
        )
        status = "ineligible"
    elif "listed" in ordered:
        status, label = "eligible", "Eligible"
    elif "isl" in ordered:
        status, label = "isl", f"On ISL until {isl_until:%-d %B %Y}"
    elif "tsl" in ordered:
        status, label = "tsl", f"On TSL until {tsl_until:%-d %B %Y}"
    else:
        status, label = "eligible_transitional", "Eligible — transitional only"
    return Eligibility(status, label, ordered, tuple(sorted(tables)), isl_until, tsl_until)


def _share(row: GoingRateRow, pct: int, hours: Decimal) -> Decimal | None:
    """SW 14.4: the published column (it already has the hourly floor), pro-rated to the full
    weekly hours."""
    value = getattr(row, PCT_COLUMN[pct])
    if value is None or row.basis_hours is None:
        return None
    return _money(value * hours / row.basis_hours)


def _pay_scale_rate(ctx: _Context) -> tuple[Decimal | None, str | None]:
    """Option K: the going rate from Table 3/3a, 4 or 5 for the chosen band or role."""
    check, rules = ctx.check, ctx.rules
    row = ctx.tables.get("3") or ctx.tables.get("3a")
    if row is None:
        return None, None
    if row.annual_rate is not None:  # a single published figure for every role
        if row.basis_hours is None:
            ctx.notes.append("Table 3a gives a full-time rate with no weekly hours; not pro-rated.")
            return row.annual_rate, row.table
        return _money(row.annual_rate * check.weekly_hours / row.basis_hours), row.table
    nation = check.work_nation
    candidates = [
        r
        for r in rules.pay_scales
        if r.soc_code == check.soc_code and r.administration in ("", nation)
    ]
    see = re.search(r"See Table (\d)", row.notes)
    if see:
        area = check.pay_scale_administration or nation
        candidates += [
            r
            for r in rules.pay_scales
            if r.source_table == see.group(1) and r.administration in (area, nation)
        ]
    roles = sorted({r.band_or_role for r in candidates})
    if not check.pay_scale_role:
        ctx.notes.append(
            "Option K needs the band or role: " + "; ".join(roles) if roles else "no roles listed"
        )
        return None, None
    chosen = next((r for r in candidates if r.band_or_role == check.pay_scale_role), None)
    if chosen is None:
        ctx.notes.append(f"No pay-scale rate for {check.pay_scale_role!r} in {nation}.")
        return None, None
    band_note = ctx.rules.table_notes.get("4", "")
    if (
        chosen.source_table == "4"
        and chosen.band_or_role in ("Band 3", "Band 4")
        and not check.applicant.before_2025
        and check.soc_code not in _exempt_codes(band_note)
    ):
        ctx.notes.append(
            "Table 4: band 3 and band 4 jobs only for Skilled Workers with permission from "
            "before 22 July 2025 (continuous since)."
        )
        return None, None
    if chosen.basis_hours is None:
        ctx.notes.append(
            f"Table {chosen.source_table}: a full-time rate with no weekly hours; not pro-rated."
        )
        return chosen.annual_rate, chosen.source_table
    return _money(chosen.annual_rate * check.weekly_hours / chosen.basis_hours), chosen.source_table


def _option_tables(ctx: _Context) -> dict[str, str | None]:
    """Which going-rate table each option family may use for this applicant (SW 4.2, 6.1, 8-12)."""
    applicant, tables = ctx.check.applicant, ctx.tables
    first = "1" if "1" in tables else "1a" if "1a" in tables else None
    if first == "1a" and not (applicant.before_2025 or ctx.tsl_active):
        # Table 1a notes: only option D (an ISL job) without the 22 July 2025 condition or the TSL.
        first_general = None
    else:
        first_general = first
    second = None
    if applicant.skilled_worker_before_2024_04_04:  # SW 4.2(b)(ii)
        if "2" in tables:
            second = "2"
        elif "2aa" in tables:
            second = "2aa"
        elif "2a" in tables and applicant.same_sponsor:
            second = "2a"
    return {"first": first, "first_general": first_general, "second": second}


def _criteria_met(ctx: _Context, rule: SalaryRuleRow, row: GoingRateRow | None) -> bool:
    applicant = ctx.check.applicant
    if rule.criteria_key == "standard":
        return True
    if rule.criteria_key in ("phd", "stem_phd"):
        wanted = applicant.stem_phd if rule.criteria_key == "stem_phd" else applicant.phd_relevant
        # A STEM PhD relevant to the job also counts as a relevant PhD (SW 10.2 meets SW 9.2-9.4).
        if rule.criteria_key == "phd":
            wanted = applicant.phd_relevant or applicant.stem_phd
        return wanted and row is not None and row.phd_points_eligible is True
    if rule.criteria_key == "isl":
        return ctx.isl_active or applicant.previous_isl_same_job
    if rule.criteria_key == "new_entrant":
        return applicant.new_entrant
    if rule.criteria_key == "health_education":
        return True
    raise ValueError(f"unknown criteria {rule.criteria_key}")


def _options(ctx: _Context, eligibility: Eligibility) -> list[OptionResult]:
    if eligibility.status == "ineligible":
        return []
    check = ctx.check
    hours = check.weekly_hours
    annual = _annual(check)
    counted = _counted(annual, hours)
    tables = _option_tables(ctx)
    out: list[OptionResult] = []
    for rule in sorted(ctx.rules.salary_rules, key=lambda r: r.option):
        if rule.applies_to == "health_care":
            if not ({"3", "3a"} & set(ctx.tables)):
                continue
            if "3a" in ctx.tables and "3" not in ctx.tables:
                exempt = _exempt_codes(ctx.rules.table_notes.get("3a", ""))
                if not (check.applicant.before_2025 or check.soc_code in exempt):
                    continue
            rate, table = _pay_scale_rate(ctx)
            out.append(_result(rule, table or "3", rate, counted, annual))
            continue
        if rule.applies_to == "transitional_pre_2024":
            table = tables["second"]
        elif rule.criteria_key == "isl":
            table = tables["first"]  # option D is open on Table 1a without the 2025 condition
        else:
            table = tables["first_general"]
        if table is None:
            continue
        row = ctx.tables[table]
        if not _criteria_met(ctx, rule, row):
            continue
        share = _share(row, rule.going_rate_pct, hours)
        if share is None:  # "Not applicable" in the table
            continue
        out.append(_result(rule, table, share, counted, annual))
    return out


def _counted(annual: Decimal, hours: Decimal) -> Decimal:
    if hours <= THRESHOLD_HOURS_CAP:
        return annual
    return _money(annual * THRESHOLD_HOURS_CAP / hours)


def _result(
    rule: SalaryRuleRow, table: str, share: Decimal | None, counted: Decimal, annual: Decimal
) -> OptionResult:
    if share is None:
        return OptionResult(
            rule.option, rule.criteria_key, table, rule.general_threshold, rule.going_rate_pct,
            None, None, None,
        )  # fmt: skip
    minimum = max(rule.general_threshold, share)
    # SW 14.3: the threshold is met on the first 48 hours' pay; SW 14.4(d): the going rate on
    # the full hours.
    meets = counted >= rule.general_threshold and annual >= share
    return OptionResult(
        rule.option, rule.criteria_key, table, rule.general_threshold, rule.going_rate_pct,
        share, minimum, meets,
    )  # fmt: skip


def _verdict(options: list[OptionResult], annual: Decimal, hours: Decimal) -> Verdict:
    priced = [o for o in options if o.minimum_required is not None]
    if not priced:
        return Verdict(None, None, None, None, None)
    passing = [o for o in priced if o.meets]
    if passing:
        best = min(passing, key=lambda o: (o.minimum_required, o.option))
        return Verdict(True, best.option, best.minimum_required, None, None)
    best = min(priced, key=lambda o: (o.minimum_required or Decimal(0), o.option))
    counted = _counted(annual, hours)
    short_by = max(best.general_threshold - counted, (best.going_rate or Decimal(0)) - annual)
    hours_needed = None
    if best.going_rate is not None and annual >= best.going_rate and hours < THRESHOLD_HOURS_CAP:
        # Same hourly pay, more hours: the going-rate share grows with the hours, the threshold
        # does not, so more hours help only when the going rate is already met.
        hourly = annual / hours
        needed = (best.general_threshold / hourly).quantize(PENNY, rounding=ROUND_CEILING)
        if needed <= THRESHOLD_HOURS_CAP:
            hours_needed = needed
    return Verdict(False, best.option, best.minimum_required, _money(short_by), hours_needed)


def _dependants(ctx: _Context, eligibility: Eligibility) -> bool:
    """SW 29.1A: a partner or child only when the job is in Table 1, 2 or 3, or a Table 1a, 2aa,
    2a or 3a job held under the rules before 22 July 2025 (not 6135 or 6136)."""
    if eligibility.status == "ineligible":
        return False
    if "listed" in eligibility.routes and set(ctx.tables) & set(LISTED_TABLES):
        return True
    transitional = {"1a", "2aa", "2a", "3a"}
    if (
        ctx.check.applicant.before_2025
        and set(ctx.tables) & transitional
        and ctx.check.soc_code not in CARE_CODES
    ):
        ctx.notes.append(
            "Dependants: allowed because the applicant has held this job since before "
            "22 July 2025 (SW 29.1A(a)(ii))."
        )
        return True
    if eligibility.status == "tsl":
        ctx.notes.append(
            "Dependants: not allowed for a new Temporary Shortage List job (SW 29.1A: Table 1, "
            "2 or 3 jobs only)."
        )
    else:
        ctx.notes.append("Dependants: not allowed (SW 29.1A: Table 1, 2 or 3 jobs only).")
    return False


def _list_notes(ctx: _Context) -> None:
    check = ctx.check
    if ctx.isl is not None:
        if check.work_nation not in ctx.isl.nations:
            ctx.notes.append(
                f"Immigration Salary List: this code is listed only for "
                f"{', '.join(ctx.isl.nations)}, not {check.work_nation}."
            )
        elif not ctx.isl_active:
            ctx.notes.append(
                f"Immigration Salary List: removed on {ctx.isl.removal_date:%-d %B %Y}; the CoS "
                "assignment date decides. SW 11.2 may still allow option D or I."
            )
        if ctx.isl.condition_text and ctx.isl.condition_text != "all jobs":
            ctx.notes.append(f"Immigration Salary List condition: {ctx.isl.condition_text}")
    if ctx.tsl is not None:
        if ctx.tsl_active:
            ctx.notes.append(
                f"Temporary Shortage List: the CoS must be issued before "
                f"{ctx.tsl.removal_date:%-d %B %Y} (SW 6.1A)."
            )
            if ctx.tsl.job_types:
                ctx.notes.append("TSL: only these job types: " + "; ".join(ctx.tsl.job_types))
        else:
            ctx.notes.append(
                f"Temporary Shortage List: ends for CoS issued on or after "
                f"{ctx.tsl.removal_date:%-d %B %Y}. Any later list: pending government decision."
            )


def evaluate(rules: RulesData, check: CheckInput) -> CheckResult:
    """Runs every rule for one code. Raises ValueError on input that cannot be assessed."""
    if check.applicant.situation not in SITUATIONS:
        raise ValueError(f"situation must be one of {SITUATIONS}")
    annual = _annual(check)
    tables = _rows_for(rules, check.soc_code, check.work_nation)
    isl = _list_entry(rules, "ISL", check.soc_code)
    tsl = _list_entry(rules, "TSL", check.soc_code)
    nation = check.work_nation
    ctx = _Context(
        rules=rules,
        check=check,
        tables=tables,
        notes=[],
        isl=isl,
        tsl=tsl,
        isl_active=bool(
            isl and nation in isl.nations and check.cos_assignment_date < isl.removal_date
        ),
        tsl_active=bool(
            tsl and nation in tsl.nations and check.cos_assignment_date < tsl.removal_date
        ),
    )
    _list_notes(ctx)
    eligibility = _eligibility(ctx)
    options = _options(ctx, eligibility)
    verdict = _verdict(options, annual, check.weekly_hours)
    dependants = _dependants(ctx, eligibility)
    for row in tables.values():
        if row.notes.startswith("Note:") and row.notes not in ctx.notes:
            ctx.notes.append(row.notes.split(" See Table")[0].split(" Source:")[0])
    if check.weekly_hours > THRESHOLD_HOURS_CAP:
        ctx.notes.append(
            "SW 14.3: only the pay for the first 48 hours a week counts towards the general "
            "threshold; the going rate is pro-rated on the full hours (SW 14.4(d))."
        )
    if any(o.criteria_key == "new_entrant" for o in options):
        ctx.notes.append(
            "New entrant: at most 4 years in total as a Skilled Worker, Graduate or Tier 2 "
            "(SW 12.3)."
        )
    first = tables.get("1") or tables.get("1a")
    going_rate = (
        _share(first, 100, check.weekly_hours)
        if first is not None
        else next((o.going_rate for o in options if o.option == "K"), None)
    )
    title = next(iter(tables.values())).title if tables else _title(rules, check.soc_code)
    return CheckResult(
        soc_code=check.soc_code,
        title=title,
        rules_version_id=rules.version_id,
        rules_version_name=rules.version_name,
        rules_effective_from=rules.effective_from,
        eligibility=eligibility,
        offered_annual=annual,
        salary_for_threshold=_counted(annual, check.weekly_hours),
        going_rate=going_rate,
        options=tuple(options),
        verdict=verdict,
        dependants_allowed=dependants,
        notes=tuple(dict.fromkeys(ctx.notes)),
    )


def _title(rules: RulesData, code: str) -> str:
    for row in rules.ineligible:
        if row.soc_code == code:
            return row.title
    for entry in rules.shortage:
        if entry.soc_code == code:
            return entry.title
    return ""
