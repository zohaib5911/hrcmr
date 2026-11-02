import type { components } from "@/lib/api/schema";

export type PersonalTab = components["schemas"]["PersonalTab"];
export type Contact = components["schemas"]["ContactOut"];
export type Gender = components["schemas"]["PersonalDetails"]["gender"];
export type MaritalStatus = components["schemas"]["PersonalDetails"]["marital_status"];
export type Relationship = Contact["relationship"];

export const GENDERS: readonly { value: Gender; label: string }[] = [
  { value: "not_specified", label: "Not specified" },
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "non_binary", label: "Non-binary" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
  { value: "other", label: "Other" },
];

export const MARITAL_STATUSES: readonly { value: MaritalStatus; label: string }[] = [
  { value: "not_specified", label: "Not specified" },
  { value: "single", label: "Single" },
  { value: "married", label: "Married" },
  { value: "civil_partnership", label: "Civil partnership" },
  { value: "separated", label: "Separated" },
  { value: "divorced", label: "Divorced" },
  { value: "widowed", label: "Widowed" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
];

export const RELATIONSHIPS: readonly { value: Relationship; label: string }[] = [
  { value: "spouse", label: "Spouse" },
  { value: "civil_partner", label: "Civil partner" },
  { value: "partner", label: "Partner" },
  { value: "parent", label: "Parent" },
  { value: "child", label: "Child" },
  { value: "sibling", label: "Sibling" },
  { value: "guardian", label: "Guardian" },
  { value: "other_relative", label: "Other relative" },
  { value: "friend", label: "Friend" },
  { value: "other", label: "Other" },
];

export function labelOf<T extends string>(
  options: readonly { value: T; label: string }[],
  value: T,
): string {
  return options.find((o) => o.value === value)?.label ?? value;
}

/** The address as one line for the summary: "1 High Street, London, SW1A 1AA". */
export function addressLine(address: NonNullable<PersonalTab["address"]>): string {
  return [
    address.line1,
    address.line2,
    address.line3,
    address.city_county,
    address.postcode,
    address.country,
  ]
    .filter((part): part is string => Boolean(part))
    .join(", ");
}
