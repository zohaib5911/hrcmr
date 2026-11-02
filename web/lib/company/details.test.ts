import { describe, expect, it } from "vitest";

import { changesBetween, companyLine, formFrom, type CompanyDetails } from "./details";

const company = {
  id: "c1",
  name: "Harbourside Care Ltd",
  trading_name: null,
  registered_number: "01234567",
  type_of_organisation: null,
  trading_period: null,
  sector: null,
  contact_email: null,
  contact_phone: null,
  website: null,
  has_logo: false,
  bank_holiday_region: "england-and-wales",
  timezone: "Europe/London",
  changed_name_last_5_years: false,
  previous_company_name: null,
  penalty_illegal_working_last_3_years: false,
  penalty_illegal_working_status: null,
  ai_features_enabled: true,
  status: "active",
  plan: "free",
} as CompanyDetails;

describe("the company details form", () => {
  it("starts from the company, with empty text for what is not set", () => {
    const form = formFrom(company);
    expect(form.name).toBe("Harbourside Care Ltd");
    expect(form.trading_name).toBe("");
    expect(form.bank_holiday_region).toBe("england-and-wales");
  });

  it("sends only what changed, trims it, and sends null to clear a field", () => {
    const before = formFrom(company);
    expect(changesBetween(before, before)).toEqual({});
    const after = {
      ...before,
      name: "  Harbourside Care Group ",
      registered_number: "",
      sector: "Q",
      ai_features_enabled: false,
    };
    expect(changesBetween(before, after)).toEqual({
      name: "Harbourside Care Group",
      registered_number: null,
      sector: "Q",
      ai_features_enabled: false,
    });
  });

  it("describes the company in one line", () => {
    expect(companyLine(company)).toBe("01234567");
    expect(companyLine({ ...company, trading_name: "Harbourside" })).toBe("Harbourside · 01234567");
    expect(companyLine({ ...company, registered_number: null })).toBe("Add your details");
  });
});
