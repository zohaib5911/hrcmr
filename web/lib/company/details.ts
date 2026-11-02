/**
 * The company details form: what it starts with, and what a save sends. Only fields that changed are
 * sent, so a save never overwrites something another person changed meanwhile.
 */
import type { components } from "@/lib/api/client";

export type CompanyDetails = components["schemas"]["CompanyDetails"];
export type CompanyUpdate = components["schemas"]["CompanyUpdate"];

export interface DetailsForm {
  name: string;
  trading_name: string;
  registered_number: string;
  type_of_organisation: string;
  trading_period: string;
  sector: string;
  contact_email: string;
  contact_phone: string;
  website: string;
  bank_holiday_region: string;
  timezone: string;
  changed_name_last_5_years: boolean;
  previous_company_name: string;
  penalty_illegal_working_last_3_years: boolean;
  penalty_illegal_working_status: string;
  ai_features_enabled: boolean;
}

export function formFrom(company: CompanyDetails): DetailsForm {
  return {
    name: company.name,
    trading_name: company.trading_name ?? "",
    registered_number: company.registered_number ?? "",
    type_of_organisation: company.type_of_organisation ?? "",
    trading_period: company.trading_period ?? "",
    sector: company.sector ?? "",
    contact_email: company.contact_email ?? "",
    contact_phone: company.contact_phone ?? "",
    website: company.website ?? "",
    bank_holiday_region: company.bank_holiday_region,
    timezone: company.timezone,
    changed_name_last_5_years: company.changed_name_last_5_years,
    previous_company_name: company.previous_company_name ?? "",
    penalty_illegal_working_last_3_years: company.penalty_illegal_working_last_3_years,
    penalty_illegal_working_status: company.penalty_illegal_working_status ?? "",
    ai_features_enabled: company.ai_features_enabled,
  };
}

/** What changed between the form as it was and as it is now, as the API's update (empty text clears). */
export function changesBetween(before: DetailsForm, after: DetailsForm): CompanyUpdate {
  const changes: Record<string, string | boolean | null> = {};
  for (const key of Object.keys(after) as (keyof DetailsForm)[]) {
    if (before[key] === after[key]) continue;
    const value = after[key];
    changes[key] = typeof value === "string" ? value.trim() || null : value;
  }
  return changes as CompanyUpdate;
}

/** Plain words for the one line a company row shows under its name. */
export function companyLine(company: CompanyDetails): string {
  const parts = [company.trading_name, company.registered_number].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "Add your details";
}
