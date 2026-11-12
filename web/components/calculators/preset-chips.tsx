"use client";

import type { CalculatorPreset } from "@/lib/calculators/frame";

/** Example scenario chips above a calculator form. Choosing one fills in the form. */
export function PresetChips<Values>({
  presets,
  onSelect,
}: {
  presets: readonly CalculatorPreset<Values>[];
  onSelect: (preset: CalculatorPreset<Values>) => void;
}) {
  if (presets.length === 0) return null;
  return (
    <div role="group" aria-label="Example scenarios" className="flex flex-wrap gap-2">
      {presets.map((preset) => (
        <button
          key={preset.id}
          type="button"
          onClick={() => onSelect(preset)}
          className="text-footnote text-label border-separator hover:bg-elevated rounded-full border px-3 py-1.5"
        >
          {preset.label}
        </button>
      ))}
    </div>
  );
}
