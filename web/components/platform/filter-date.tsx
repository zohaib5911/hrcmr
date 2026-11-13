import { TextField } from "@/components/ui/text-field";

/** Keep admin GET filters usable before hydration, with native mobile date entry and ISO values. */
export function FilterDate({
  label,
  name,
  defaultValue,
}: {
  label: string;
  name: string;
  defaultValue?: string | null | undefined;
}) {
  return (
    <TextField
      label={label}
      name={name}
      type="date"
      defaultValue={defaultValue?.slice(0, 10) ?? ""}
      clearable={false}
    />
  );
}
