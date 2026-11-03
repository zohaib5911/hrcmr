import type { components } from "@/lib/api/schema";
import { shortDate } from "@/lib/employees/profile";

export type Reminder = components["schemas"]["ReminderOut"];
export type ReminderSlot = components["schemas"]["ReminderSlot"];
export const REMINDER_STATUS = {
  scheduled: { label: "Scheduled", tone: "neutral" },
  due: { label: "Due", tone: "warning" },
  sent: { label: "Sent", tone: "success" },
  snoozed: { label: "Snoozed", tone: "info" },
  cancelled: { label: "Cancelled", tone: "neutral" },
} as const;
export const EMAIL_STATUS = {
  pending: "Email queued",
  sent: "Email delivered",
  failed: "Email could not be delivered",
} as const;
export const REGISTER_TYPES = [
  { value: "visa", label: "Visa" },
  { value: "passport", label: "Passport" },
  { value: "dbs", label: "DBS" },
  { value: "euss", label: "EUSS" },
  { value: "other", label: "Other" },
  { value: "rtw", label: "Right to Work" },
] as const;
export type RegisterType = (typeof REGISTER_TYPES)[number]["value"];
export const sentTime = (value: string) =>
  shortDate(value.slice(0, 10)) + " · " + value.slice(11, 16) + " UTC";
