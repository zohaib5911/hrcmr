"use client";

import { ALL_STAGES, STAGE_LABEL, type Stage } from "./stages";

/** Eight clickable stages with counts. The chosen stage filters the Applications tab. */
export function PipelineBar({
  counts,
  selected,
  onSelect,
}: {
  counts: Partial<Record<Stage, number>>;
  selected: Stage | null;
  onSelect: (stage: Stage | null) => void;
}) {
  return (
    <div role="group" aria-label="Pipeline" className="flex flex-wrap gap-2">
      {ALL_STAGES.map((stage) => {
        const on = selected === stage;
        return (
          <button
            key={stage}
            type="button"
            aria-pressed={on}
            onClick={() => onSelect(on ? null : stage)}
            className={
              "text-callout rounded-full px-3 py-1.5 font-medium transition-colors " +
              (on ? "bg-accent text-on-accent" : "bg-fill-secondary text-label hover:bg-label/10")
            }
          >
            {STAGE_LABEL[stage]}{" "}
            <span className="tabular-nums opacity-80">({counts[stage] ?? 0})</span>
          </button>
        );
      })}
    </div>
  );
}
