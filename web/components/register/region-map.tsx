"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

import { MAP_HEIGHT, MAP_WIDTH, REGIONS, SHETLAND_INSET } from "./uk-regions";

export { REGIONS };

export type RegionCount = { count: number; delta?: number };

/** Five calm steps of the accent over the panel surface; regions with none stay a quiet fill. */
const STEPS = [
  {
    fill: "fill-[color-mix(in_srgb,var(--accent)_18%,var(--bg-elevated))]",
    swatch: "bg-[color-mix(in_srgb,var(--accent)_18%,var(--bg-elevated))]",
  },
  {
    fill: "fill-[color-mix(in_srgb,var(--accent)_34%,var(--bg-elevated))]",
    swatch: "bg-[color-mix(in_srgb,var(--accent)_34%,var(--bg-elevated))]",
  },
  {
    fill: "fill-[color-mix(in_srgb,var(--accent)_50%,var(--bg-elevated))]",
    swatch: "bg-[color-mix(in_srgb,var(--accent)_50%,var(--bg-elevated))]",
  },
  {
    fill: "fill-[color-mix(in_srgb,var(--accent)_66%,var(--bg-elevated))]",
    swatch: "bg-[color-mix(in_srgb,var(--accent)_66%,var(--bg-elevated))]",
  },
  {
    fill: "fill-[color-mix(in_srgb,var(--accent)_82%,var(--bg-elevated))]",
    swatch: "bg-[color-mix(in_srgb,var(--accent)_82%,var(--bg-elevated))]",
  },
];
const NONE = { fill: "fill-fill-secondary", swatch: "bg-fill-secondary" };
const ZOOM_MS = 320;
const MAX_ZOOM = 3.5;

const number = (n: number) => n.toLocaleString("en-GB");
const signed = (n: number) => `${n > 0 ? "+" : ""}${number(n)}`;

function stepFor(count: number, max: number) {
  if (!count || !max) return -1;
  return Math.min(STEPS.length - 1, Math.ceil((count / max) * STEPS.length) - 1);
}

function paint(step: number) {
  return STEPS[step] ?? NONE;
}

const easeSpring = (t: number) => 1 - Math.pow(1 - t, 3);
const transformOf = (z: { scale: number; x: number; y: number }) =>
  `translate(${z.x} ${z.y}) scale(${z.scale})`;

/** Scale and centre on one region's box; identity when nothing is chosen. */
function zoomFor(name: string | null) {
  const region = REGIONS.find((r) => r.name === name);
  if (!region) return { scale: 1, x: 0, y: 0 };
  const [bx, by, bw, bh] = region.box;
  const scale = Math.min(MAP_WIDTH / (bw * 1.3), MAP_HEIGHT / (bh * 1.3), MAX_ZOOM);
  return {
    scale,
    x: MAP_WIDTH / 2 - scale * (bx + bw / 2),
    y: MAP_HEIGHT / 2 - scale * (by + bh / 2),
  };
}

function summary(name: string, c: RegionCount | undefined, deltaLabel: string) {
  const delta = c?.delta ?? 0;
  return `${name}: ${c ? `${number(c.count)} sponsors` : "no data"}${
    delta ? ` (${signed(delta)} ${deltaLabel})` : ""
  }`;
}

export function RegionMap({
  counts,
  deltaLabel = "today",
}: {
  counts: Record<string, RegionCount>;
  deltaLabel?: string;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [pointer, setPointer] = useState<string | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const active = pointer ?? focused ?? selected;
  const max = Math.max(0, ...REGIONS.map((r) => counts[r.name]?.count ?? 0));
  const zoom = zoomFor(selected);
  const shadowId = useId();
  const groupRef = useRef<SVGGElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const shown = useRef(zoom);

  // A short eased zoom between the whole UK and the chosen region, written straight to the SVG
  // transform attribute. Reduced motion jumps to the end.
  useEffect(() => {
    const group = groupRef.current;
    const from = shown.current;
    const to = zoom;
    if (!group) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? true;
    if (reduce || typeof window.requestAnimationFrame !== "function") {
      shown.current = to;
      group.setAttribute("transform", transformOf(to));
      return;
    }
    let frame = 0;
    const start = performance.now();
    const step = (now: number) => {
      const t = easeSpring(Math.min(1, (now - start) / ZOOM_MS));
      shown.current = {
        scale: from.scale + (to.scale - from.scale) * t,
        x: from.x + (to.x - from.x) * t,
        y: from.y + (to.y - from.y) * t,
      };
      group.setAttribute("transform", transformOf(shown.current));
      if (t < 1) frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frame);
  }, [zoom.scale, zoom.x, zoom.y]); // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = (name: string) => setSelected((current) => (current === name ? null : name));

  const onKey = (event: KeyboardEvent, name: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle(name);
    } else if (event.key === "Escape") {
      setSelected(null);
    }
  };

  // Where the tooltip points: the active region's label, after the zoom, as a share of the panel.
  const activeRegion = REGIONS.find((r) => r.name === active);
  const tip = activeRegion && {
    x: ((zoom.x + zoom.scale * activeRegion.label[0]) / MAP_WIDTH) * 100,
    y: ((zoom.y + zoom.scale * activeRegion.label[1]) / MAP_HEIGHT) * 100,
  };
  const activeCount = active ? counts[active] : undefined;

  // The CSP forbids style="" in server HTML, so the tooltip is placed through the CSSOM instead.
  useLayoutEffect(() => {
    const el = tipRef.current;
    if (!el || !tip) return;
    el.style.left = tip.x > 50 ? "" : `${tip.x}%`;
    el.style.right = tip.x > 50 ? `${100 - tip.x}%` : "";
    el.style.bottom = tip.y > 25 ? `calc(${100 - tip.y}% + 0.75rem)` : "";
    el.style.top = tip.y > 25 ? "" : `calc(${tip.y}% + 0.75rem)`;
  });

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <figure className="material-sheet rounded-card shadow-e2 border-separator relative overflow-hidden border p-3 sm:p-5">
        <div className="relative mx-auto max-w-md">
          <svg
            viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
            role="group"
            aria-label="Map of UK regions showing sponsor counts"
            className="block h-auto w-full touch-manipulation"
            onKeyDown={(event) => event.key === "Escape" && setSelected(null)}
          >
            <defs>
              <filter id={shadowId} x="-10%" y="-10%" width="120%" height="120%">
                <feDropShadow dx="0" dy="6" stdDeviation="8" floodColor="#000" floodOpacity="0.1" />
              </filter>
            </defs>
            <g
              ref={groupRef}
              data-zoom={selected ?? "none"}
              data-scale={zoom.scale}
              transform={transformOf({ scale: 1, x: 0, y: 0 })}
              filter={`url(#${shadowId})`}
            >
              <rect
                x={SHETLAND_INSET[0]}
                y={SHETLAND_INSET[1]}
                width={SHETLAND_INSET[2]}
                height={SHETLAND_INSET[3]}
                rx={10}
                fill="none"
                stroke="var(--separator)"
                vectorEffect="non-scaling-stroke"
                aria-hidden="true"
              />
              {REGIONS.map((r) => {
                const c = counts[r.name];
                const isActive = active === r.name;
                const dimmed = selected !== null && selected !== r.name;
                return (
                  <path
                    key={r.name}
                    d={r.d}
                    data-region={r.name}
                    role="button"
                    tabIndex={0}
                    aria-label={summary(r.name, c, deltaLabel)}
                    aria-pressed={selected === r.name}
                    fillOpacity={dimmed ? 0.45 : 1}
                    stroke={isActive ? "var(--accent)" : "var(--bg-elevated)"}
                    strokeWidth={isActive ? 2.5 : 1}
                    strokeLinejoin="round"
                    vectorEffect="non-scaling-stroke"
                    className={cn(
                      paint(stepFor(c?.count ?? 0, max)).fill,
                      "cursor-pointer outline-none motion-safe:transition-[fill-opacity,stroke] motion-safe:duration-[var(--duration-small)]",
                    )}
                    onPointerEnter={() => setPointer(r.name)}
                    onPointerLeave={() => setPointer(null)}
                    onFocus={() => setFocused(r.name)}
                    onBlur={() => setFocused(null)}
                    onClick={() => toggle(r.name)}
                    onKeyDown={(event) => onKey(event, r.name)}
                  >
                    <title>{summary(r.name, c, deltaLabel)}</title>
                  </path>
                );
              })}
              <g
                aria-hidden="true"
                className={cn(
                  "pointer-events-none max-sm:hidden motion-safe:transition-opacity",
                  selected && "opacity-0",
                )}
              >
                {REGIONS.map((r) => (
                  <text
                    key={r.name}
                    x={r.label[0]}
                    y={r.label[1]}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={22}
                    fontWeight={600}
                    fill="var(--label)"
                    stroke="var(--bg-elevated)"
                    strokeWidth={5}
                    paintOrder="stroke"
                    data-tabular
                  >
                    {number(counts[r.name]?.count ?? 0)}
                  </text>
                ))}
              </g>
            </g>
          </svg>
          {activeRegion && tip ? (
            <div
              ref={tipRef}
              aria-hidden="true"
              data-testid="region-tooltip"
              className="material-sheet rounded-popover shadow-e3 border-separator pointer-events-none absolute z-10 w-max max-w-[60%] border px-3 py-2 motion-safe:transition-[left,right,top,bottom] motion-safe:duration-[var(--duration-small)]"
            >
              <p className="text-subheadline text-label font-semibold">{activeRegion.name}</p>
              <p className="text-footnote text-label-secondary" data-tabular>
                {activeCount ? `${number(activeCount.count)} sponsors` : "No data"}
                {activeCount?.delta ? ` · ${signed(activeCount.delta)} ${deltaLabel}` : ""}
              </p>
            </div>
          ) : null}
        </div>
        <div
          className="text-footnote text-label-secondary mt-3 flex flex-wrap items-center gap-x-4 gap-y-2"
          aria-hidden="true"
        >
          <span className="flex items-center gap-1.5">
            <span className={cn("size-3 rounded-sm", NONE.swatch)} />
            None
          </span>
          <span className="flex items-center gap-1.5">
            Fewer
            {STEPS.map((step) => (
              <span key={step.fill} className={cn("size-3 rounded-sm", step.swatch)} />
            ))}
            More
          </span>
          {selected ? (
            <button
              type="button"
              className="text-accent-text ml-auto font-medium"
              onClick={() => setSelected(null)}
            >
              Show all of the UK
            </button>
          ) : (
            <span className="ml-auto">Choose a region to zoom in</span>
          )}
        </div>
        <figcaption className="text-caption text-label-secondary mt-3">
          Region boundaries: Office for National Statistics, licensed under the Open Government
          Licence v.3.0. Contains OS data © Crown copyright and database right 2025.
        </figcaption>
      </figure>
      <table className="text-subheadline w-full text-left">
        <caption className="text-title-3 mb-2 text-left">Sponsors by region</caption>
        <thead className="text-footnote text-label-secondary">
          <tr>
            <th scope="col" className="py-2 pr-3 font-medium">
              Region
            </th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">
              Sponsors
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Change
            </th>
          </tr>
        </thead>
        <tbody>
          {REGIONS.map((r) => (
            <tr
              key={r.name}
              className={cn("border-separator border-t", active === r.name && "bg-fill-secondary")}
              onPointerEnter={() => setPointer(r.name)}
              onPointerLeave={() => setPointer(null)}
            >
              <th scope="row" className="py-2 pr-3 font-normal">
                {r.name}
              </th>
              <td className="py-2 pr-3 text-right">{number(counts[r.name]?.count ?? 0)}</td>
              <td className="text-label-secondary py-2 text-right">
                {signed(counts[r.name]?.delta ?? 0)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
