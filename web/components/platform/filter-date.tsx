"use client";

import { useState } from "react";

import { DatePicker } from "@/components/ui/date-picker";

/** A UK date picker for the admin GET filter forms: the ISO date travels in a hidden field. */
export function FilterDate({
  label,
  name,
  defaultValue,
}: {
  label: string;
  name: string;
  defaultValue?: string | null | undefined;
}) {
  const [value, setValue] = useState<string | null>(defaultValue?.slice(0, 10) || null);
  return (
    <div>
      <DatePicker label={label} value={value} onChange={setValue} />
      <input type="hidden" name={name} value={value ?? ""} />
    </div>
  );
}
