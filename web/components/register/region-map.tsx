// Original, simplified schematic of the 12 UK ITL1 regions. Hand-drawn for this product (not a
// copy of any third-party map); shapes show relative position only, not true boundaries.

export const REGIONS = [
  { name: "Scotland", d: "M70 4 L130 10 L140 60 L110 100 L60 100 L40 55 Z" },
  { name: "Northern Ireland", d: "M4 90 L36 86 L40 120 L8 126 Z" },
  { name: "North East", d: "M112 104 L142 100 L146 130 L118 134 Z" },
  { name: "North West", d: "M70 104 L110 104 L116 138 L72 142 Z" },
  { name: "Yorkshire and The Humber", d: "M118 138 L148 134 L158 160 L124 164 Z" },
  { name: "Wales", d: "M44 150 L84 146 L90 190 L50 196 Z" },
  { name: "West Midlands", d: "M92 148 L120 146 L124 182 L94 186 Z" },
  { name: "East Midlands", d: "M126 168 L156 164 L160 196 L130 198 Z" },
  { name: "East of England", d: "M162 168 L196 166 L200 200 L164 200 Z" },
  { name: "London", d: "M148 206 L170 204 L172 224 L150 226 Z" },
  { name: "South East", d: "M132 204 L146 202 L152 230 L176 228 L182 246 L128 248 Z" },
  { name: "South West", d: "M28 200 L90 192 L126 204 L124 250 L60 262 L24 236 Z" },
] as const;

export type RegionCount = { count: number; delta?: number };

export function RegionMap({
  counts,
  deltaLabel = "today",
}: {
  counts: Record<string, RegionCount>;
  deltaLabel?: string;
}) {
  return (
    <figure>
      <svg
        viewBox="0 0 210 270"
        role="img"
        aria-label="Schematic map of UK regions showing sponsor counts"
        className="h-auto w-full max-w-sm"
      >
        {REGIONS.map((r) => {
          const c = counts[r.name];
          const delta = c?.delta ?? 0;
          return (
            <path
              key={r.name}
              d={r.d}
              data-region={r.name}
              fill="currentColor"
              fillOpacity={c ? 0.15 + Math.min(c.count, 1000) / 1250 : 0.05}
              stroke="currentColor"
              strokeWidth={1}
            >
              <title>
                {r.name}: {c ? c.count.toLocaleString("en-GB") : "no data"}
                {delta ? ` (${delta > 0 ? "+" : ""}${delta} ${deltaLabel})` : ""}
              </title>
            </path>
          );
        })}
      </svg>
      <figcaption className="sr-only">
        <ul>
          {REGIONS.map((r) => (
            <li key={r.name}>
              {r.name}: {counts[r.name]?.count ?? 0}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}
